import csv
from dataclasses import dataclass
from datetime import datetime
import io
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import numpy as np
from detector import MomentDetector
from chat_settings import ChatConfigReloader
from montage import montage_worker, probe_duration, run_tool, tool

BUF_ROOT, CLIP_DIR = Path("buf"), Path("clips")
PRE, POST, KEEP = 25, 10, 180
MIN_CLIP, VOLUME_STALE, STALL_KILL = 8, 10, 25
FINALIZE_WAIT = 25
CHAT_TIMEOUT = 60
MAX_MONTAGE_QUEUE = 8


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    path: str
    session: str


def list_segments(buf_dir):
    """Read actual closed-segment intervals, never assume two-second segments."""
    segments = []
    for manifest in Path(buf_dir).glob("*/segments.csv"):
        try:
            metadata = json.loads(manifest.with_name("clock.json").read_text(encoding="utf-8"))
            anchor = float(metadata["anchor"])
            if not math.isfinite(anchor):
                continue
            # A snapshot can end in a partially written line; ignore that line.
            snapshot = manifest.read_text(encoding="utf-8", errors="replace")
            if snapshot and not snapshot.endswith("\n"):
                snapshot = snapshot.rsplit("\n", 1)[0] + "\n" if "\n" in snapshot else ""
            for row in csv.reader(io.StringIO(snapshot)):
                if len(row) != 3:
                    continue
                try:
                    start, end = float(row[1]), float(row[2])
                    if not all(map(math.isfinite, (start, end))) or end <= start:
                        continue
                    # ffmpeg's CSV stores a basename unless a prefix was requested.
                    filename = row[0].replace("\\", "/").rsplit("/", 1)[-1]
                    if not re.fullmatch(r"seg_\d+\.ts", filename):
                        continue
                    path = manifest.parent / filename
                    if path.is_file():
                        segments.append(Segment(anchor + start, anchor + end,
                                                str(path.resolve()), str(manifest.parent.resolve())))
                except (ValueError, OSError):
                    continue
        except (OSError, ValueError, KeyError, csv.Error):
            continue
    return sorted(segments, key=lambda segment: (segment.start, segment.path))


def select_run(segments, lo, hi, trigger_ts):
    candidates = [segment for segment in segments if segment.end > lo and segment.start < hi]
    candidates.sort(key=lambda segment: (segment.start, segment.path))
    runs = []
    for segment in candidates:
        if (not runs or segment.session != runs[-1][-1].session or
                segment.start > runs[-1][-1].end + 0.5):
            runs.append([])
        runs[-1].append(segment)
    if not runs:
        return []
    # Distance to the interval, not to a run's middle segment.
    return min(runs, key=lambda run: (
        max(run[0].start - trigger_ts, trigger_ts - run[-1].end, 0),
        -(min(hi, run[-1].end) - max(lo, run[0].start)),
    ))


class Recorder(threading.Thread):
    def __init__(self, channel, buf_dir, stop_event):
        super().__init__(daemon=True)
        self.channel, self.buf_dir, self.stop_event = channel, Path(buf_dir), stop_event
        self._vol, self._last_block, self._process = None, None, None
        self.restarts = 0
        self._audio_lock = threading.Lock()
        self._pending_peak = None

    def _push_volume(self, db):
        now = time.monotonic()
        with self._audio_lock:
            self._vol = (now, db)
            self._last_block = now
            self._pending_peak = db if self._pending_peak is None else max(self._pending_peak, db)

    def take_volume(self):
        """Consume one burst peak once: never repeatedly baseline the same HLS audio."""
        with self._audio_lock:
            peak, self._pending_peak = self._pending_peak, None
            value = self._vol
        if value is None or time.monotonic() - value[0] > VOLUME_STALE:
            return None
        return peak

    def _reset_audio(self):
        with self._audio_lock:
            self._vol = None
            self._pending_peak = None

    def volume(self):
        value = self._vol
        return value[1] if value and time.monotonic() - value[0] <= VOLUME_STALE else None

    def audio_age(self):
        return time.monotonic() - self._last_block if self._last_block is not None else float("inf")

    def stop(self):
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass

    def run(self):
        while not self.stop_event.is_set():
            try:
                self._run_once()
            except Exception as error:
                print(f"[{self.channel}] recorder: {error}", flush=True)
            self._reset_audio()
            if self.stop_event.wait(5):
                break
            self.restarts += 1

    def _run_once(self):
        # Use Streamlink's API, so the EXE does not need a separately installed CLI.
        from streamlink import Streamlink
        session = Streamlink()
        session.set_option("http-timeout", 15)
        session.set_option("stream-timeout", 20)
        streams = session.streams(f"https://www.twitch.tv/{self.channel}")
        if "best" not in streams:
            raise RuntimeError("Stream is offline, unavailable, or requires authentication")
        source = streams["best"].open()
        directory = self.buf_dir / (datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8])
        directory.mkdir(parents=True, exist_ok=True)
        process = None
        finished = threading.Event()
        self._last_block = time.monotonic()
        self._reset_audio()
        try:
            command = [tool("ffmpeg"), "-hide_banner", "-loglevel", "warning", "-nostdin",
                       "-i", "pipe:0", "-map", "0:v:0", "-map", "0:a:0", "-c", "copy",
                       "-f", "segment", "-segment_time", "2", "-reset_timestamps", "1",
                       "-segment_format", "mpegts", "-segment_list_type", "csv",
                       "-segment_list_size", "0", "-segment_list", "segments.csv",
                       "seg_%09d.ts", "-map", "0:a:0", "-vn", "-c:a", "pcm_s16le",
                       "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"]
            options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            process = subprocess.Popen(command, cwd=str(directory.resolve()), stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, **options)
            self._process = process

            def feed():
                try:
                    while not self.stop_event.is_set() and not finished.is_set():
                        block = source.read(65536)
                        if not block:
                            break
                        process.stdin.write(block)
                except (OSError, ValueError) as error:
                    if not finished.is_set() and not self.stop_event.is_set():
                        print(f"[{self.channel}] stream read: {error}", flush=True)
                finally:
                    try:
                        process.stdin.close()
                    except (OSError, ValueError):
                        pass
                    try:
                        source.close()
                    except Exception:
                        pass

            def watchdog():
                while not finished.wait(1):
                    if self.stop_event.is_set() or self.audio_age() > STALL_KILL:
                        if not self.stop_event.is_set():
                            print(f"[{self.channel}] no audio for {STALL_KILL}s; restarting", flush=True)
                        self.stop()
                        return

            threading.Thread(target=feed, daemon=True).start()
            threading.Thread(target=watchdog, daemon=True).start()
            chunk_size, first_block = 16000 * 2, True
            while not self.stop_event.is_set():
                data = process.stdout.read(chunk_size)
                if len(data) < chunk_size:
                    break
                if first_block:
                    # Approximate wall-clock anchor, established when audio actually arrives,
                    # rather than before Streamlink's connection/buffering delay.
                    metadata = {"anchor": time.time() - 1.0, "channel": self.channel}
                    temporary = directory / "clock.tmp"
                    temporary.write_text(json.dumps(metadata), encoding="utf-8")
                    os.replace(temporary, directory / "clock.json")
                    first_block = False
                    print(f"[{self.channel}] recording started", flush=True)
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768
                rms = max(float(np.sqrt(np.mean(samples ** 2))), 1e-4)
                self._push_volume(20 * math.log10(rms))
        finally:
            finished.set()
            self.stop()
            if process is not None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                for pipe in (process.stdin, process.stdout):
                    try:
                        pipe.close()
                    except (OSError, ValueError):
                        pass
            else:
                source.close()
            self._process = None
            self._reset_audio()


class ChatListener(threading.Thread):
    def __init__(self, channel, on_message, stop_event):
        super().__init__(daemon=True)
        self.channel, self.on_message, self.stop_event = channel, on_message, stop_event
        self._socket = None

    def stop(self):
        sock = self._socket
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()

    def run(self):
        while not self.stop_event.is_set():
            try:
                self._session()
            except Exception as error:
                if not self.stop_event.is_set():
                    print(f"[{self.channel}] chat: {error}", flush=True)
            if self.stop_event.wait(5):
                break

    def _session(self):
        import codecs
        raw = socket.create_connection(("irc.chat.twitch.tv", 6697), timeout=15)
        try:
            sock = ssl.create_default_context().wrap_socket(raw, server_hostname="irc.chat.twitch.tv")
        except Exception:
            raw.close()
            raise
        self._socket = sock
        try:
            sock.settimeout(CHAT_TIMEOUT)
            nickname = "justinfan" + str(int(uuid.uuid4().hex[:8], 16) % 90000000 + 10000000)
            sock.sendall(f"NICK {nickname}\r\nJOIN #{self.channel}\r\n".encode())
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            buffer, ping_sent = "", False
            while not self.stop_event.is_set():
                try:
                    data = sock.recv(4096)
                except socket.timeout:
                    if ping_sent:
                        raise ConnectionError("chat keepalive timed out")
                    sock.sendall(b"PING :keepalive\r\n")
                    ping_sent = True
                    continue
                if not data:
                    raise ConnectionError("server closed chat connection")
                ping_sent = False
                buffer += decoder.decode(data)
                if len(buffer) > 1024 * 1024:
                    raise ConnectionError("invalid IRC response")
                *lines, buffer = buffer.split("\r\n")
                for line in lines:
                    self._handle(sock, line)
        finally:
            sock.close()
            self._socket = None

    def _handle(self, sock, line):
        if line.startswith("@"):
            line = line.split(" ", 1)[-1]
        if line.startswith("PING "):
            sock.sendall(("PONG " + line[5:] + "\r\n").encode())
        elif " RECONNECT" in line:
            raise ConnectionError("server requested reconnect")
        elif " NOTICE " in line:
            print(f"[{self.channel}] IRC: {line}", flush=True)
            if "authentication failed" in line.lower():
                raise ConnectionError("anonymous chat login rejected")
        elif " JOIN " in line:
            print(f"[{self.channel}] chat connected", flush=True)
        elif " PRIVMSG " in line:
            try:
                user = line[1:].split("!", 1)[0] if line.startswith(":") else None
                text = line.split(" PRIVMSG ", 1)[1].split(" :", 1)[1].strip()
            except IndexError:
                return
            self.on_message(text, user)


class ChannelCtx:
    def __init__(self, channel, stop_event, detector_options=None):
        self.channel, self.stop_event = channel, stop_event
        self.buf_dir = BUF_ROOT / channel
        self.buf_dir.mkdir(parents=True, exist_ok=True)
        self.detector = MomentDetector(**(detector_options or {}))
        self.recorder = Recorder(channel, self.buf_dir, stop_event)
        self.chat = ChatListener(channel, self.detector.on_chat, stop_event)
        self.last_end = float("-inf")
        # Avoid unlimited waiting cut jobs; a slot is held until the cut finishes.
        self.cut_slots = threading.BoundedSemaphore(2)

    def plan_window(self, trigger_ts):
        lo, hi = max(trigger_ts - PRE, self.last_end), trigger_ts + POST
        self.last_end = hi
        return lo, hi


def cut_clip(ctx, trigger_ts, lo, hi, montage_queue, trigger_info=None):
    output = None
    try:
        if ctx.stop_event.wait(max(0, hi - time.time())):
            return
        deadline = time.monotonic() + FINALIZE_WAIT
        while not ctx.stop_event.is_set():
            segments = list_segments(ctx.buf_dir)
            if any(segment.start < hi <= segment.end for segment in segments):
                break
            if time.monotonic() >= deadline:
                break
            ctx.stop_event.wait(0.5)
        if ctx.stop_event.is_set():
            return
        run = select_run(segments, lo, hi, trigger_ts)
        if not run:
            print(f"[{ctx.channel}] no closed segments for clip", flush=True)
            return
        distance = max(run[0].start - trigger_ts, trigger_ts - run[-1].end, 0)
        if distance > 5:
            print(f"[{ctx.channel}] recording gap at trigger; clip skipped", flush=True)
            return
        effective_lo, effective_hi = max(lo, run[0].start), min(hi, run[-1].end)
        if effective_hi - effective_lo < MIN_CLIP:
            print(f"[{ctx.channel}] not enough continuous recording", flush=True)
            return
        CLIP_DIR.mkdir(exist_ok=True)
        output = CLIP_DIR / f"raw_{ctx.channel}_{int(trigger_ts * 1000)}_{uuid.uuid4().hex[:6]}.mp4"
        # Copy closed inputs before concatenation. Cleanup cannot remove these copies.
        with tempfile.TemporaryDirectory(prefix="cut_", dir=str(CLIP_DIR.resolve())) as work:
            listing = []
            for index, segment in enumerate(run):
                name = f"part_{index:05d}.ts"
                shutil.copy2(segment.path, str(Path(work) / name))
                listing.append(f"file '{name}'\n")
            manifest = Path(work) / "inputs.txt"
            manifest.write_text("".join(listing), encoding="ascii")
            run_tool([tool("ffmpeg"), "-loglevel", "error", "-y", "-fflags", "+genpts",
                      "-f", "concat", "-safe", "0", "-i", str(manifest),
                      "-map", "0:v:0", "-map", "0:a:0", "-c", "copy",
                      "-avoid_negative_ts", "make_zero", str(output.resolve())])
        offset = effective_lo - run[0].start
        duration = min(effective_hi - effective_lo, probe_duration(output) - offset)
        if duration < MIN_CLIP:
            raise ValueError(f"Clip too short: {duration:.2f}s")
        job = {"channel": ctx.channel, "path": str(output.resolve()), "ts": trigger_ts,
               "offset": offset, "duration": duration, "trigger": trigger_info or {}}
        try:
            montage_queue.put_nowait(job)
        except queue.Full:
            print(f"[{ctx.channel}] montage queue full; new clip dropped", flush=True)
            output.unlink(missing_ok=True)
        else:
            print(f"[{ctx.channel}] queued clip: {duration:.1f}s", flush=True)
    except Exception as error:
        print(f"[{ctx.channel}] cut failed: {error}", flush=True)
        if output:
            output.unlink(missing_ok=True)
    finally:
        ctx.cut_slots.release()


def cleanup_buffer(ctx):
    cutoff = time.time() - KEEP
    for path in ctx.buf_dir.glob("*/seg_*.ts"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass
    for directory in ctx.buf_dir.iterdir():
        try:
            if directory.is_dir() and not any(directory.glob("*.ts")):
                # Do not remove a just-created session before its first segment.
                if directory.stat().st_mtime < cutoff:
                    shutil.rmtree(directory)
        except OSError:
            pass


def normalize_channels(values):
    channels = []
    for value in values:
        for channel in re.split(r"[,;\s]+", value.strip().lower()):
            if not channel:
                continue
            channel = re.sub(r"^(?:https?://)?(?:www\.)?twitch\.tv/", "", channel).strip("/")
            if not re.fullmatch(r"[a-z0-9_]{1,25}", channel):
                raise ValueError(f"Invalid Twitch channel: {channel}")
            if channel not in channels:
                channels.append(channel)
    if not channels:
        raise ValueError("Enter at least one Twitch channel")
    return channels


def preflight(check_streamlink=True):
    if check_streamlink:
        from streamlink import Streamlink  # noqa: F401
    for name in ("ffmpeg", "ffprobe"):
        run_tool([tool(name), "-version"], stdout=subprocess.DEVNULL)
    filters = run_tool([tool("ffmpeg"), "-hide_banner", "-filters"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    available = filters.stdout + filters.stderr
    for name in ("afftdn", "sidechaincompress"):
        if not re.search(r"\s" + re.escape(name) + r"\s", available):
            raise RuntimeError(f"FFmpeg build is missing filter: {name}. Use a full build.")
    if os.environ.get("CLIP_SUBTITLES", "0") == "1" and not re.search(r"\sass\s", available):
        raise RuntimeError("FFmpeg build is missing the ass filter required for subtitles")



def describe_trigger(snapshot):
    from i18n import I18n
    language = I18n(os.environ.get("CLIP_LANGUAGE", "ru"))
    names = {key: language.t("main.trigger." + key) for key in ("plain", "laugh", "react", "vol")}
    english = language.language == "en"
    reasons = []
    thresholds = snapshot["thresholds"]
    if "single_chat" in snapshot["routes"]:
        categories = ", ".join(f"{names[key]} Z={snapshot[key]:.2f}" for key in snapshot["chat_categories"])
        reasons.append(f"chat spike ({categories}; threshold {thresholds['chat']:.2f})" if english else
                       f"всплеск чата ({categories}; порог {thresholds['chat']:.2f})")
    if "combined" in snapshot["routes"]:
        reasons.append(f"overall score={snapshot['score']:.2f} > {thresholds['score']:.2f}" if english else
                       f"общий score={snapshot['score']:.2f} > {thresholds['score']:.2f}")
    contributions = ", ".join(f"{names[key]}={value:.2f}" for key, value in snapshot["contributions"].items())
    mode = language.t("main.trigger.escalation" if snapshot["trigger_mode"] == "escalation" else "main.trigger.normal")
    if english:
        return (f"{' + '.join(reasons)}; {mode}; score contributions: {contributions}; "
                f"chatters: regular={snapshot['n_plain']}, laughter={snapshot['n_laugh']}, reactions={snapshot['n_react']}")
    return (f"{' + '.join(reasons)}; {mode}; вклад в score: {contributions}; "
            f"чаттеры: обычные={snapshot['n_plain']}, смех={snapshot['n_laugh']}, реакции={snapshot['n_react']}")


def main(channels, threshold=1.2, single_threshold=4.0, cooldown=40):
    channels = normalize_channels(channels)
    if not 0.1 <= threshold <= 8 or not 0.1 <= single_threshold <= 8 or not 1 <= cooldown <= 600:
        raise ValueError("Thresholds must be 0.1..8; cooldown must be 1..600 seconds")
    detector_options = dict(threshold=threshold, single_threshold=single_threshold,
                            cooldown=cooldown, min_gap=min(20, cooldown))
    preflight()
    for directory in (BUF_ROOT, CLIP_DIR, Path("ready"), Path("music")):
        directory.mkdir(parents=True, exist_ok=True)
    stop_event = threading.Event()
    montage_queue = queue.Queue(maxsize=MAX_MONTAGE_QUEUE)
    contexts = [ChannelCtx(channel, stop_event, detector_options) for channel in channels]
    chat_config = ChatConfigReloader(os.environ.get("CLIP_CHAT_CONFIG"))
    matcher = chat_config.poll()
    if matcher is not None:
        for ctx in contexts:
            ctx.detector.set_chat_matcher(matcher)
    delay = float(os.environ.get("CLIP_VIDEO_DELAY", "0"))
    if not math.isfinite(delay) or not -60 <= delay <= 60:
        raise ValueError("CLIP_VIDEO_DELAY must be between -60 and 60 seconds")
    for ctx in contexts:
        ctx.recorder.start()
        ctx.chat.start()
    threading.Thread(target=montage_worker, args=(montage_queue, stop_event), daemon=True).start()
    print(f"Thresholds: score>{threshold} OR chat>={single_threshold}; cooldown={cooldown}s", flush=True)
    print(f"Started: {', '.join(channels)}; ready={Path('ready').resolve()}; video shift={delay}s", flush=True)
    next_tick, last_clean, last_heartbeat = time.monotonic(), 0.0, 0.0
    try:
        while not stop_event.is_set():
            next_tick += 1
            if next_tick < time.monotonic() - 2:
                next_tick = time.monotonic() + 1
            stop_event.wait(max(0, next_tick - time.monotonic()))
            wall_now, monotonic_now = time.time(), time.monotonic()
            matcher = chat_config.poll()
            if matcher is not None:
                for ctx in contexts:
                    ctx.detector.set_chat_matcher(matcher)
            for ctx in contexts:
                volume = ctx.recorder.take_volume()
                if ctx.detector.tick(volume, wall_now):
                    snapshot = ctx.detector.last
                    snapshot["description"] = describe_trigger(snapshot)
                    print(f"[{ctx.channel}] TRIGGER: {snapshot['description']}", flush=True)
                    if ctx.cut_slots.acquire(blocking=False):
                        center = wall_now + delay
                        lo, hi = ctx.plan_window(center)
                        threading.Thread(target=cut_clip,
                                         args=(ctx, center, lo, hi, montage_queue, dict(snapshot)), daemon=True).start()
                    else:
                        print(f"[{ctx.channel}] cut backlog full; trigger skipped", flush=True)
                if monotonic_now - last_clean >= 30:
                    cleanup_buffer(ctx)
            if monotonic_now - last_clean >= 30:
                last_clean = monotonic_now
            if monotonic_now - last_heartbeat >= 5:
                last_heartbeat = monotonic_now
                for ctx in contexts:
                    peak = ctx.detector.pop_peak() or ctx.detector.last
                    volume = ctx.recorder.volume()
                    print(f"[{ctx.channel}] HB vol={volume if volume is not None else 'n/a'} "
                          f"age={ctx.recorder.audio_age():.0f}s rst={ctx.recorder.restarts} "
                          f"score={peak.get('score', 0):.2f} "
                          f"z=({peak.get('plain', 0):.1f},{peak.get('laugh', 0):.1f},"
                          f"{peak.get('react', 0):.1f},{peak.get('vol', 0):.1f}) "
                          f"n=({peak.get('n_plain', 0)},{peak.get('n_laugh', 0)},{peak.get('n_react', 0)}) "
                          f"segments={len(list_segments(ctx.buf_dir))} queue={montage_queue.qsize()}", flush=True)
    except KeyboardInterrupt:
        print("Stopping...", flush=True)
    finally:
        stop_event.set()
        for ctx in contexts:
            ctx.chat.stop()
            ctx.recorder.stop()
        for ctx in contexts:
            ctx.recorder.join(timeout=3)
            ctx.chat.join(timeout=1)


if __name__ == "__main__":
    try:
        main(sys.argv[1:] or os.environ.get("CHANNELS", "").split(","))
    except Exception as error:
        print(f"FATAL: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
