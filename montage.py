import glob
import json
import math
import os
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
import random
import secrets
import shutil
import subprocess
import sys
import tempfile
import uuid
import wave
from render_settings import read_options, validate_roi
from mp4_metadata import ENCODER_KEY, finalize_encoder_tag

OUT_DIR = "ready"
FAILED_DIR = "failed"
_whisper = None
_whisper_missing_reported = False
SUBS_ENABLED = os.environ.get("CLIP_SUBTITLES", "0") == "1"


def tool(name):
    override = os.environ.get(name.upper() + "_PATH")
    if override:
        if not Path(override).is_file():
            raise FileNotFoundError(f"Invalid {name.upper()}_PATH: {override}")
        return override
    suffix = ".exe" if os.name == "nt" else ""
    roots = [Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "bin",
             Path(sys.executable).parent / "bin", Path.cwd() / "bin"]
    for root in roots:
        candidate = root / (name + suffix)
        if candidate.is_file():
            return str(candidate)
    result = shutil.which(name)
    if not result:
        raise FileNotFoundError(f"{name} not found. Put {name}{suffix} in bin/ or add it to PATH.")
    return result


class MediaToolError(subprocess.CalledProcessError):
    def __str__(self):
        diagnostics = self.stderr or ""
        if isinstance(diagnostics, bytes):
            diagnostics = diagnostics.decode("utf-8", errors="replace")
        name = Path(self.cmd[0]).name if isinstance(self.cmd, (list, tuple)) else str(self.cmd)
        return f"{name} exited with code {self.returncode}:\n{diagnostics[-12000:].strip() or '(stderr is empty)'}"


def run_tool(args, **kwargs):
    if os.name == "nt":
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    # Explicitly collect stderr: inherited Windows handles did not put FFmpeg's
    # actual reason into the worker log. Spool to disk to keep memory bounded.
    if kwargs.get("capture_output") or "stderr" in kwargs:
        try:
            return subprocess.run(args, check=True, **kwargs)
        except subprocess.CalledProcessError as error:
            raise MediaToolError(error.returncode, error.cmd, output=error.output,
                                 stderr=error.stderr) from error
    with tempfile.TemporaryFile() as diagnostics:
        try:
            return subprocess.run(args, check=True, stderr=diagnostics, **kwargs)
        except subprocess.CalledProcessError as error:
            diagnostics.seek(0, os.SEEK_END)
            diagnostics.seek(max(0, diagnostics.tell() - 12000))
            raise MediaToolError(error.returncode, error.cmd, output=error.output,
                                 stderr=diagnostics.read()) from error


def _default_font_path():
    if os.environ.get("FONT_PATH"):
        return os.environ["FONT_PATH"]
    if sys.platform.startswith("win"):
        return str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arialbd.ttf")
    if sys.platform == "darwin":
        return "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    return "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _ffq(path):
    # Quoted ffmpeg filter values still need backslash and colon escaping.
    # Generated temporary names contain no quotes; reject ambiguous asset paths.
    if "'" in str(path) or "\n" in str(path) or "\r" in str(path):
        raise ValueError("FFmpeg asset paths must not contain quotes or newlines")
    return str(path).replace("\\", "/").replace(":", "\\:")


SPONSOR = {"banner": "sponsor.mp4", "width": 900, "top_margin": 650,
           "key_color": "0x00FF00", "similarity": 0.15, "blend": 0.08, "ad_tag": "#ad"}
NOISE = {"enabled": True, "highpass": 80, "nr": 10, "nf": -35}
MUSIC = {"enabled": True, "dir": "music", "volume": 0.35, "threshold": 0.02,
         "ratio": 10, "attack": 15, "release": 400}
SUBS = {"enabled": SUBS_ENABLED, "model": "small", "language": "ru",
        "font": os.environ.get("SUB_FONT") or (
            "Arial" if sys.platform.startswith(("win", "darwin")) else "DejaVu Sans"),
        "size": 64, "outline": 5, "margin_v": 420, "margin_h": 80,
        "max_words": 4, "max_dur": 2.5, "max_gap": 0.6}
STREAMERS = {}


def probe_size(path):
    result = run_tool([tool("ffprobe"), "-v", "error", "-select_streams", "v:0",
                       "-show_entries", "stream=width,height", "-of", "json", str(path)],
                      capture_output=True, text=True, encoding="utf-8")
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise ValueError(f"No video stream: {path}")
    return streams[0]["width"], streams[0]["height"]


def probe_fps(path):
    """Prefer average source FPS; fall back to nominal rate for sparse metadata."""
    result = run_tool([tool("ffprobe"), "-v", "error", "-select_streams", "v:0",
                       "-show_entries", "stream=avg_frame_rate,r_frame_rate", "-of", "json", str(path)],
                      capture_output=True, text=True, encoding="utf-8")
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise ValueError(f"No video stream: {path}")
    for key in ("avg_frame_rate", "r_frame_rate"):
        try:
            value = Fraction(str(streams[0].get(key, "0/0")))
            if 0 < value <= 1000:
                return value
        except (ValueError, ZeroDivisionError):
            pass
    print(f"FPS: source rate unavailable for {path}; using 30 FPS as base", flush=True)
    return Fraction(30)


def choose_output_fps(source_fps, enabled=True):
    """Stable CFR with bounded time base, including irregular live-stream rates."""
    source = Fraction(str(source_fps))
    if not 0 < source <= 1000:
        raise ValueError("Source FPS must be positive and at most 1000")
    if not enabled:
        # Keep common exact rates (30000/1001, etc.), but not huge HLS ratios.
        return source if source.denominator <= 100000 else max(Fraction(1, 1000), Fraction(round(source * 1000), 1000))
    deltas = [Fraction(n, 10) for n in range(-20, 21) if n and source + Fraction(n, 10) > 0]
    delta = random.choice(deltas)
    target = source + delta
    if target.denominator <= 100000:
        return target
    # Average HLS FPS can have millions in its denominator. Use millifps for
    # these rates, clamped inward so rounding never violates the 0.1..2 bounds.
    low, high = ((source + Fraction(1, 10), source + 2) if delta > 0 else
                 (source - 2, source - Fraction(1, 10)))
    minimum, maximum = max(1, math.ceil(low * 1000)), math.floor(high * 1000)
    return Fraction(max(minimum, min(maximum, round(target * 1000))), 1000)


def probe_duration(path):
    result = run_tool([tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                       "-of", "json", str(path)], capture_output=True, text=True,
                      encoding="utf-8")
    value = float(json.loads(result.stdout)["format"]["duration"])
    if value <= 0:
        raise ValueError(f"Invalid media duration: {path}")
    return value


def denoise_chain():
    return (f"highpass=f={NOISE['highpass']},afftdn=nr={NOISE['nr']}:nf={NOISE['nf']}"
            if NOISE["enabled"] else "")


def pick_music(duration, location=None):
    if not MUSIC["enabled"]:
        return None, 0.0
    location = MUSIC["dir"] if location is None else location
    if not location:
        return None, 0.0
    root = Path(location)
    extensions = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
    files = ([str(root)] if root.is_file() else
             [str(path) for path in root.iterdir() if path.is_file() and path.suffix.lower() in extensions]
             if root.is_dir() else [])
    if not files:
        return None, 0.0
    path = random.choice(files)
    total = probe_duration(path)
    return path, random.uniform(0, max(0, total - duration - 1))


def build_audio_filter(music_idx, duration):
    fade = f"afade=t=out:st={max(0, duration - 0.5):.3f}:d=0.5"
    finish = f"loudnorm=I=-16:TP=-1.5,{fade}"
    denoise = denoise_chain()
    voice = (f"[0:a:0]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS,"
             f"{denoise + ',' if denoise else ''}"
             "aformat=sample_rates=48000:channel_layouts=stereo")
    if music_idx is None:
        return f"{voice},{finish}[a]"
    music = MUSIC
    return (
        f"{voice},asplit=2[vm][vs];"
        f"[{music_idx}:a:0]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS,"
        f"aformat=sample_rates=48000:channel_layouts=stereo,"
        f"volume={music['volume']},afade=t=in:d=0.5[mus];"
        f"[mus][vs]sidechaincompress=threshold={music['threshold']}:ratio={music['ratio']}:"
        f"attack={music['attack']}:release={music['release']}:makeup=1[duck];"
        "[vm][duck]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
        f"{finish}[a]"
    )


def load_whisper_audio(path):
    """FFmpeg already decoded WAV; do not ask faster-whisper/PyAV to decode it again."""
    import numpy as np
    with wave.open(str(path), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1, 2, 16000, "NONE"):
            raise ValueError("Subtitles require mono 16-bit PCM WAV at 16000 Hz")
        samples = audio.readframes(audio.getnframes())
    return np.frombuffer(samples, dtype="<i2").astype(np.float32) / 32768.0


def transcribe_words(source, offset, duration, language, wav_path):
    global _whisper, _whisper_missing_reported
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        if not _whisper_missing_reported:
            print("Subtitles unavailable: build with WITH_SUBTITLES=1 or install faster-whisper.", flush=True)
            _whisper_missing_reported = True
        return []
    command = [tool("ffmpeg"), "-loglevel", "error", "-y", "-ss", f"{offset:.3f}",
               "-i", source, "-t", f"{duration:.3f}", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le"]
    if denoise_chain():
        command += ["-af", denoise_chain()]
    run_tool(command + [wav_path])
    audio = load_whisper_audio(wav_path)
    if not audio.size:
        return []
    if _whisper is None:
        # CPU/int8 is a predictable default on ordinary Windows PCs.
        _whisper = WhisperModel(SUBS["model"], device="cpu", compute_type="int8")
    segments, _ = _whisper.transcribe(audio, language=language, vad_filter=True,
                                      word_timestamps=True, condition_on_previous_text=False)
    return [(word.start, word.end, word.word.strip()) for segment in segments
            for word in (segment.words or []) if word.word.strip()]


def chunk_words(words):
    chunks, current = [], []
    for word in words:
        if current and (len(current) >= SUBS["max_words"] or
                        word[0] - current[-1][1] > SUBS["max_gap"] or
                        word[1] - current[0][0] > SUBS["max_dur"]):
            chunks.append(current)
            current = []
        current.append(word)
    if current:
        chunks.append(current)
    return chunks


def _ass_time(value):
    centiseconds = max(0, round(value * 100))
    return (f"{centiseconds // 360000}:{centiseconds // 6000 % 60:02d}:"
            f"{centiseconds // 100 % 60:02d}.{centiseconds % 100:02d}")


def write_ass(chunks, path, duration):
    settings = SUBS
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n"
        "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{settings['font']},{settings['size']},&H00FFFFFF,&H00FFFFFF,"
        f"&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{settings['outline']},0,2,"
        f"{settings['margin_h']},{settings['margin_h']},{settings['margin_v']},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = []
    for index, chunk in enumerate(chunks):
        start = max(0, chunk[0][0])
        end = min(duration, chunk[-1][1] + 0.15)
        if index + 1 < len(chunks):
            end = min(end, chunks[index + 1][0][0])
        if end - start < 0.1:
            continue
        text = " ".join(word[2] for word in chunk)
        text = text.replace("\\", "／").replace("{", "(").replace("}", ")").replace("\n", " ")
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}")
    Path(path).write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def crop_pixels(width, height, roi):
    x, y, w, h = validate_roi(roi)
    cw = min(width // 2 * 2, max(2, int(width * w) // 2 * 2))
    ch = min(height // 2 * 2, max(2, int(height * h) // 2 * 2))
    cx = min(int(width * x) // 2 * 2, width - cw)
    cy = min(int(height * y) // 2 * 2, height - ch)
    return cw, ch, cx, cy


def choose_video_effects(enabled=True):
    """One stable sample per clip. Sponsor assets never use these effects."""
    if not enabled:
        return {}
    return {"mirror": True, "brightness": random.uniform(-0.012, 0.012),
            "contrast": random.uniform(0.98, 1.02),
            "saturation": random.uniform(0.97, 1.03),
            "camera_zoom": random.uniform(1.02, 1.06)}


def build_filter(width, height, textfile, has_banner, ass_path=None,
                 camera_roi=None, content_roi=None, banner_roi=None, video_effects=None,
                 output_fps=None):
    # Crop source coordinates BEFORE mirroring. Never mirror the finished composition.
    effects = video_effects or {}
    transform = "hflip," if effects.get("mirror", False) else ""
    if effects:
        transform += (f"eq=brightness={effects.get('brightness', 0):.6f}:"
                      f"contrast={effects.get('contrast', 1):.6f}:"
                      f"saturation={effects.get('saturation', 1):.6f},")
    # textfile is retained only for compatibility. No nickname/text overlay.
    crop = ""
    if content_roi is not None:
        cw, ch, cx, cy = crop_pixels(width, height, content_roi)
        crop = f"crop={cw}:{ch}:{cx}:{cy},"
    if camera_roi is not None:
        cw, ch, cx, cy = crop_pixels(width, height, camera_roi)
        zoom = float(effects.get("camera_zoom", 1.0))
        if not 1.0 <= zoom <= 1.1:
            raise ValueError("Camera zoom must be between 1.0 and 1.1")
        zw, zh = max(2, int(cw / zoom) // 2 * 2), max(2, int(ch / zoom) // 2 * 2)
        cx, cy = cx + (cw - zw) // 4 * 2, cy + (ch - zh) // 4 * 2
        cw, ch = zw, zh
        parts = [
            "[0:v:0]setpts=PTS-STARTPTS,split=2[cam_src][screen_src]",
            f"[cam_src]crop={cw}:{ch}:{cx}:{cy},{transform}"
            "scale=1080:640:force_original_aspect_ratio=decrease,"
            "pad=1080:640:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[cam]",
            f"[screen_src]{crop}{transform}split=2[bg][fg]",
            "[bg]scale=216:256:force_original_aspect_ratio=increase,"
            "crop=216:256,boxblur=6:2,scale=1080:1280,setsar=1,eq=brightness=-0.08[b]",
            "[fg]scale=1080:1280:force_original_aspect_ratio=decrease,setsar=1[f]",
            "[b][f]overlay=(W-w)/2:(H-h)/2[screen]",
            "[cam][screen]vstack=inputs=2[v0]",
        ]
    else:
        # Safe fallback before the user has selected a camera: full frame, no guessed crop.
        parts = [
            f"[0:v:0]setpts=PTS-STARTPTS,{crop}{transform}split=2[bg][fg]",
            "[bg]scale=216:384:force_original_aspect_ratio=increase,"
            "crop=216:384,boxblur=6:2,scale=1080:1920,setsar=1,eq=brightness=-0.08[b]",
            "[fg]scale=1080:1920:force_original_aspect_ratio=decrease,setsar=1[f]",
            "[b][f]overlay=(W-w)/2:(H-h)/2[v0]",
        ]
    current = "v0"
    if has_banner:
        sponsor = SPONSOR
        if banner_roi is not None:
            bw, bh, bx, by = crop_pixels(1080, 1920, banner_roi)
            banner_scale = f"scale={bw}:{bh}:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1"
            banner_position = f"{bx}+({bw}-w)/2:{by}+({bh}-h)/2"
        else:
            banner_scale = f"scale={sponsor['width']}:-2,setsar=1"
            banner_position = f"(W-w)/2:{sponsor['top_margin']}"
        parts += [
            f"[1:v:0]setpts=PTS-STARTPTS,format=rgba,chromakey={sponsor['key_color']}:"
            f"{sponsor['similarity']}:{sponsor['blend']},despill=type=green,"
            f"{banner_scale}[bn]",
            f"[{current}][bn]overlay={banner_position}:shortest=1[v1]",
        ]
        current = "v1"
    if ass_path:
        parts.append(f"[{current}]ass='{_ffq(ass_path)}'[v2]")
        current = "v2"
    # The fps filter defines CFR on the original timeline across FFmpeg 4..9;
    # the removed global -vsync option must never be required for export.
    finish = f"fps=fps={Fraction(str(output_fps))}:round=near" if output_fps is not None else "null"
    parts.append(f"[{current}]{finish}[v]")
    return ";".join(parts)


def choose_clip_metadata(enabled=True):
    """CapCut application tags are fixed; unrelated descriptive tags are optional."""
    metadata = {
        "format": {"encoding_tool": "CapCut", "producer": "CapCut", "encoder": "CapCut"},
        # Explicit encoder values prevent inherited/default Lavc compressor tags.
        "video": {"encoder": "CapCut"}, "audio": {"encoder": "CapCut"},
    }
    if not enabled:
        return metadata
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    seconds = max(1, int((datetime.now(timezone.utc) - start).total_seconds()))
    created = (start + timedelta(seconds=secrets.randbelow(seconds))).strftime("%Y-%m-%dT%H:%M:%SZ")

    def label(prefix):
        return f"{prefix}_{uuid.uuid4().hex}"

    metadata["format"].update(title=label("Clip"), artist=label("Creator"),
                              album=label("Collection"), comment=label("Note"), creation_time=created)
    metadata["video"].update(creation_time=created, handler_name=label("Video"))
    metadata["audio"].update(creation_time=created, handler_name=label("Audio"))
    return metadata


def clip_metadata_args(metadata):
    if not metadata:
        return []
    # Prevent FFmpeg from inserting its application tags; encoder is written via
    # a reserved, equal-length mdta key renamed by finalize_encoder_tag().
    args = ["-map_metadata", "-1", "-map_metadata:s", "-1", "-map_chapters", "-1",
            "-fflags", "+bitexact"]
    for scope, option in (("format", "-metadata"), ("video", "-metadata:s:v:0"),
                          ("audio", "-metadata:s:a:0")):
        for key, value in metadata[scope].items():
            if scope == "format" and key == "encoder":
                key = ENCODER_KEY
            args += [option, f"{key}={value}"]
    return args


def reserve_clip_path(job, randomized=True):
    """Reserve random output exclusively so FFmpeg -y cannot clobber a clip."""
    if not randomized:
        return str(Path(OUT_DIR) / f"{job['channel']}_{int(job['ts'] * 1000)}.mp4")
    for _ in range(20):
        path = Path(OUT_DIR) / f"clip_{uuid.uuid4().hex}.mp4"
        if any(Path(str(path) + suffix).exists() for suffix in (".json", ".ass", ".wav")):
            continue
        try:
            with path.open("xb"):
                pass
            return str(path)
        except FileExistsError:
            continue
    raise FileExistsError("Could not reserve a unique random clip filename")


def make_vertical(job):
    os.makedirs(OUT_DIR, exist_ok=True)
    channel, source = job["channel"], job["path"]
    config = STREAMERS.get(channel, {"title": f"@{channel}", "hashtags": "#стрим #fyp"})
    render = read_options()
    random_metadata = render.get("random_metadata", True)
    clip_metadata = choose_clip_metadata(random_metadata)
    regions = render.get("crops", {}).get(channel, {})
    camera_roi = validate_roi(regions.get("camera")) if render.get("split_camera", True) else None
    content_roi = validate_roi(regions.get("content"))
    banner_roi = validate_roi(regions.get("banner"))
    effects = choose_video_effects(render.get("video_variation", True))
    job["render"] = {"video_effects": effects, "camera_roi": camera_roi,
                     "content_roi": content_roi, "banner_roi": banner_roi,
                     "random_metadata": bool(random_metadata), "metadata": clip_metadata}
    if effects:
        zoom_note = f"{effects['camera_zoom'] * 100:.1f}%" if camera_roi is not None else "not applied (no separate camera)"
        print(f"[{channel}] VIDEO: mirrored; camera zoom={zoom_note}; "
              f"brightness={effects['brightness']:+.4f} contrast={effects['contrast']:.4f} "
              f"saturation={effects['saturation']:.4f}; banner unchanged", flush=True)
    if render.get("split_camera", True) and camera_roi is None:
        print(f"[{channel}] MONTAGE: webcam area not set; using full frame without nickname. Select it in the GUI.", flush=True)
    elif camera_roi is not None:
        print(f"[{channel}] MONTAGE: webcam top / stream bottom; camera={camera_roi} content={content_roi or 'full frame'}; no nickname", flush=True)
    else:
        print(f"[{channel}] MONTAGE: single video area; content={content_roi or 'full frame'}; no nickname", flush=True)
    banner_path = render.get("banner", SPONSOR["banner"])
    out = reserve_clip_path(job, random_metadata)
    ass_path, wav_path = out + ".ass", out + ".wav"
    try:
        if random_metadata:
            print(f"[{channel}] METADATA: randomized tags and filename={Path(out).name}; "
                  f"creation_time={clip_metadata['format']['creation_time']}", flush=True)
        width, height = probe_size(source)
        source_fps = probe_fps(source)
        output_fps = choose_output_fps(source_fps, render.get("random_fps", True))
        job["render"].update(source_fps=float(source_fps), output_fps=float(output_fps),
                             output_fps_ratio=str(output_fps), random_fps=render.get("random_fps", True))
        print(f"[{channel}] FPS: {float(source_fps):.6f} -> {float(output_fps):.6f} "
              f"({float(output_fps - source_fps):+.1f}); speed unchanged; metadata=CapCut", flush=True)
        duration, offset = float(job["duration"]), float(job["offset"])
        has_banner = bool(banner_path) and Path(banner_path).is_file()
        use_ass = False
        if SUBS["enabled"] and config.get("subs", True):
            try:
                words = transcribe_words(source, offset, duration,
                                         config.get("lang", SUBS["language"]), wav_path)
                use_ass = bool(words and write_ass(chunk_words(words), ass_path, duration))
            except Exception as error:
                print(f"Subtitles skipped: {error}", flush=True)
        try:
            music_path, music_start = pick_music(duration, render.get("music")) if config.get("music", True) else (None, 0)
        except Exception as error:
            print(f"Music skipped: {error}", flush=True)
            music_path, music_start = None, 0
        command = [tool("ffmpeg"), "-loglevel", "error", "-y", "-ss", f"{offset:.3f}", "-i", source]
        index = 1
        if has_banner:
            command += ["-stream_loop", "-1", "-i", banner_path]
            index += 1
        music_index = None
        if music_path:
            command += ["-stream_loop", "-1", "-ss", f"{music_start:.3f}", "-i", music_path]
            music_index = index
        filters = (build_filter(width, height, None, has_banner, ass_path if use_ass else None,
                                camera_roi=camera_roi, content_roi=content_roi,
                                banner_roi=banner_roi, video_effects=effects, output_fps=output_fps)
                   + ";" + build_audio_filter(music_index, duration))
        command += ["-t", f"{duration:.3f}", "-filter_complex", filters,
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "23", "-r", str(output_fps), "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-b:a", "128k", "-ar", "48000"]
        command += clip_metadata_args(clip_metadata)
        command += ["-movflags", "+faststart+use_metadata_tags", out]
        run_tool(command)
        finalize_encoder_tag(out)
        actual_duration = probe_duration(out)
        if actual_duration < min(8, duration - 0.5):
            raise ValueError(f"Rendered clip is unexpectedly short: {actual_duration:.2f}s")
        caption = config["hashtags"]
        if has_banner and SPONSOR.get("ad_tag"):
            caption += " " + SPONSOR["ad_tag"]
        return out, caption, has_banner
    except Exception:
        Path(out).unlink(missing_ok=True)
        raise
    finally:
        for path in (ass_path, wav_path):
            Path(path).unlink(missing_ok=True)


def montage_worker(in_queue, stop_event):
    import queue
    while not stop_event.is_set():
        try:
            job = in_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            out, caption, sponsored = make_vertical(job)
            metadata = {"channel": job["channel"], "path": str(Path(out).resolve()),
                        "caption": caption, "sponsored": sponsored, "trigger_ts": job["ts"],
                        "status": "ready_for_manual_publication", "trigger": job.get("trigger", {}),
                        "render": job.get("render", {})}
            Path(out + ".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
            Path(job["path"]).unlink(missing_ok=True)
            print(f"READY: {Path(out).resolve()}", flush=True)
        except Exception as error:
            print(f"Montage failed: {error}", flush=True)
            # Keep a bounded set of failed source clips for diagnosis/retry.
            try:
                os.makedirs(FAILED_DIR, exist_ok=True)
                source = Path(job["path"])
                if source.exists():
                    shutil.move(str(source), str(Path(FAILED_DIR) / source.name))
                failed = sorted(Path(FAILED_DIR).glob("*.mp4"), key=lambda p: p.stat().st_mtime)
                for path in failed[:-10]:
                    path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                print(f"Failed-clip cleanup: {cleanup_error}", flush=True)
        finally:
            in_queue.task_done()
