"""Windows GUI and PyInstaller entry point. Source: python launcher.py"""
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import webbrowser

from i18n import I18n
from version import __version__

GITHUB_URL = "https://github.com/ilusha1900/TwitchAutoClipper"

def default_root():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TwitchClipper"


def save_settings(path, settings):
    """Save language immediately without risking the existing settings file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump(settings, output, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def parse_number(value, lower, upper, message):
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        raise ValueError(message) from None
    if not math.isfinite(number) or not lower <= number <= upper:
        raise ValueError(message)
    return number


def worker(args):
    directory = Path(args.data_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    os.chdir(directory)
    os.environ["CLIP_SUBTITLES"] = "1" if args.subtitles else "0"
    os.environ["CLIP_VIDEO_DELAY"] = str(args.video_delay)
    os.environ["CLIP_LANGUAGE"] = args.language
    if args.render_config:
        os.environ["CLIP_RENDER_CONFIG"] = str(Path(args.render_config).resolve())
    if args.chat_config:
        os.environ["CLIP_CHAT_CONFIG"] = str(Path(args.chat_config).resolve())
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    lock = open(directory / "worker.lock", "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            lock.seek(0, 2)
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                print("FATAL: another recorder is already using this data folder.", flush=True)
                return 1
        from main import main
        main([args.channels], threshold=args.threshold,
             single_threshold=args.single_threshold, cooldown=args.cooldown)
        return 0
    except Exception as error:
        import traceback
        print(f"FATAL: {error}", file=sys.stderr, flush=True)
        traceback.print_exc()
        return 1
    finally:
        lock.close()


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
    if os.name == "nt" and getattr(sys, "frozen", False):
        import ctypes
        window = ctypes.windll.kernel32.GetConsoleWindow()
        if window:
            ctypes.windll.user32.ShowWindow(window, 0)
    settings_file = default_root() / "settings.json"
    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            settings = {}
    except (OSError, ValueError):
        settings = {}
    i18n = I18n(settings.get("language", "ru"))
    root = tk.Tk()
    root.title(i18n.t("window.title"))
    root.geometry("1020x880")
    root.minsize(960, 780)
    container = ttk.Frame(root, padding=16)
    container.pack(fill="both", expand=True)
    container.columnconfigure(1, weight=1)
    container.rowconfigure(10, weight=1)
    channels_var = tk.StringVar(value=str(settings.get("channels", "")))
    directory_var = tk.StringVar(value=str(settings.get("data_dir", default_root() / "data")))
    subtitles_var = tk.BooleanVar(value=bool(settings.get("subtitles", False)))
    delay_var = tk.StringVar(value=str(settings.get("video_delay", 0)))
    threshold_var = tk.StringVar(value=str(settings.get("threshold", 1.2)))
    single_var = tk.StringVar(value=str(settings.get("single_threshold", 4.0)))
    cooldown_var = tk.StringVar(value=str(settings.get("cooldown", 40)))
    status_var = tk.StringVar(value=i18n.t("status.stopped"))
    status_state = {"key": "status.stopped", "args": {}}

    def set_status(key, **args):
        status_state.update(key=key, args=args)
        status_var.set(i18n.t(key, **args))

    title_label = ttk.Label(container, text=f"Twitchautoclipper {__version__}", font=("Segoe UI", 19, "bold"))
    title_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
    language_label = ttk.Label(container, text=i18n.t("language"))
    language_label.grid(row=0, column=2, sticky="e", padx=(12, 6), pady=(0, 12))
    language_var = tk.StringVar(value=i18n.language_names()[0 if i18n.language == "ru" else 1])
    language_combo = ttk.Combobox(container, textvariable=language_var,
                                  values=i18n.language_names(), state="readonly", width=11)
    language_combo.grid(row=0, column=3, sticky="e", pady=(0, 12))
    channels_label = ttk.Label(container, text=i18n.t("label.channels"))
    channels_label.grid(row=1, column=0, sticky="w", padx=(0, 12))
    channel_entry = ttk.Entry(container, textvariable=channels_var)
    channel_entry.grid(row=1, column=1, columnspan=3, sticky="ew", pady=4)
    channels_hint = ttk.Label(container, text=i18n.t("hint.channels"))
    channels_hint.grid(row=2, column=1, columnspan=3, sticky="w", pady=(0, 8))
    data_folder_label = ttk.Label(container, text=i18n.t("label.data_folder"))
    data_folder_label.grid(row=3, column=0, sticky="w")
    directory_entry = ttk.Entry(container, textvariable=directory_var)
    directory_entry.grid(row=3, column=1, columnspan=2, sticky="ew", pady=4)

    def choose_directory():
        selected = filedialog.askdirectory(title=i18n.t("dialog.data_folder"))
        if selected:
            directory_var.set(selected)

    browse = ttk.Button(container, text=i18n.t("button.browse"), command=choose_directory)
    browse.grid(row=3, column=3, padx=(8, 0))
    subtitle_check = ttk.Checkbutton(container, text=i18n.t("check.subtitles"),
                                     variable=subtitles_var)
    subtitle_check.grid(row=4, column=1, columnspan=3, sticky="w", pady=6)
    delay_frame = ttk.Frame(container)
    delay_frame.grid(row=5, column=1, columnspan=3, sticky="w", pady=4)
    video_shift_label = ttk.Label(delay_frame, text=i18n.t("label.video_shift"))
    video_shift_label.pack(side="left")
    delay_entry = ttk.Entry(delay_frame, textvariable=delay_var, width=7)
    delay_entry.pack(side="left", padx=8)
    tuning = ttk.Frame(container)
    tuning.grid(row=6, column=1, columnspan=3, sticky="w", pady=6)
    thresholds_label = ttk.Label(tuning, text=i18n.t("label.thresholds"))
    thresholds_label.pack(side="left")
    threshold_entry = ttk.Entry(tuning, textvariable=threshold_var, width=5)
    threshold_entry.pack(side="left", padx=4)
    chat_label = ttk.Label(tuning, text=i18n.t("label.chat"))
    chat_label.pack(side="left")
    single_entry = ttk.Entry(tuning, textvariable=single_var, width=5)
    single_entry.pack(side="left", padx=4)
    cooldown_label = ttk.Label(tuning, text=i18n.t("label.cooldown"))
    cooldown_label.pack(side="left")
    cooldown_entry = ttk.Entry(tuning, textvariable=cooldown_var, width=5)
    cooldown_entry.pack(side="left", padx=4)
    lower_more_label = ttk.Label(container, text=i18n.t("hint.lower_more"))
    lower_more_label.grid(row=6, column=0, sticky="w")
    controls = ttk.Frame(container)
    controls.grid(row=8, column=0, columnspan=4, sticky="ew", pady=8)
    log_box = scrolledtext.ScrolledText(container, wrap="word", state="disabled",
                                        font=("Consolas", 10), height=17)
    log_box.grid(row=10, column=0, columnspan=4, sticky="nsew")
    github_button = ttk.Button(container, text="GitHub: ilusha1900/TwitchAutoClipper",
                               cursor="hand2", command=lambda: webbrowser.open(GITHUB_URL, new=2))
    github_button.grid(row=11, column=0, columnspan=4, sticky="e", pady=(8, 0))
    ttk.Label(container, textvariable=status_var).grid(row=9, column=0, columnspan=4,
                                                      sticky="w", pady=(0, 6))
    events = queue.Queue(maxsize=2000)
    state = {"process": None, "stopping": False, "closing": False}

    def persist_language():
        settings["language"] = i18n.language
        try:
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            save_settings(settings_file, settings)
        except OSError as error:
            messagebox.showerror(i18n.t("dialog.language_save"), str(error), parent=root)

    def select_language(event=None):
        language = "ru" if language_var.get() == "Русский" else "en"
        i18n.set_language(language)
        persist_language()

    language_combo.bind("<<ComboboxSelected>>", select_language)

    def append(text):
        log_box.configure(state="normal")
        log_box.insert("end", text)
        if int(log_box.index("end-1c").split(".")[0]) > 2500:
            log_box.delete("1.0", "501.0")
        log_box.see("end")
        log_box.configure(state="disabled")

    from render_settings import RenderPanel
    render_path = settings_file.with_name("render.json")
    render_panel = RenderPanel(container, render_path, channels_var.get, directory_var.get, append, i18n)
    render_panel.frame.grid(row=7, column=0, columnspan=4, sticky="ew", pady=5)
    chat_path = settings_file.with_name("chat.json")
    chat_editor = {"instance": None}

    def edit_chat_phrases():
        from chat_settings import ChatPhraseEditor
        current = chat_editor["instance"]
        if current is not None and current.window.winfo_exists():
            current.window.lift()
            current.window.focus_set()
            return
        try:
            chat_editor["instance"] = ChatPhraseEditor(root, chat_path, append, i18n)
        except (OSError, ValueError) as error:
            messagebox.showerror(i18n.t("dialog.chat_phrases"), i18n.error(str(error)), parent=root)

    def emit(kind, data):
        try:
            events.put_nowait((kind, data))
        except queue.Full:
            # The complete log is still written to disk by the reader thread.
            if kind == "exit":
                events.put((kind, data))

    def set_running(running):
        start_button.configure(state="disabled" if running else "normal")
        stop_button.configure(state="normal" if running else "disabled")
        for widget in (channel_entry, directory_entry, browse, subtitle_check, delay_entry,
                       threshold_entry, single_entry, cooldown_entry):
            widget.configure(state="disabled" if running else "normal")

    def start():
        if state["process"] is not None:
            return
        try:
            values = []
            for value in re.split(r"[,;\s]+", channels_var.get().strip().lower()):
                if not value:
                    continue
                value = re.sub(r"^(?:https?://)?(?:www\.)?twitch\.tv/", "", value).strip("/")
                if not re.fullmatch(r"[a-z0-9_]{1,25}", value):
                    raise ValueError(i18n.t("error.channel", channel=value))
                if value not in values:
                    values.append(value)
            if not values:
                raise ValueError(i18n.t("error.channel_required"))
            delay = parse_number(delay_var.get(), -60, 60, i18n.t("error.delay"))
            threshold = parse_number(threshold_var.get(), 0.1, 8, i18n.t("error.threshold"))
            single_threshold = parse_number(single_var.get(), 0.1, 8, i18n.t("error.threshold"))
            cooldown = parse_number(cooldown_var.get(), 1, 600, i18n.t("error.cooldown"))
            directory = Path(directory_var.get()).expanduser().resolve()
            directory.mkdir(parents=True, exist_ok=True)
            log_dir = directory / "logs"
            log_dir.mkdir(exist_ok=True)
            for old in sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)[:-9]:
                old.unlink(missing_ok=True)
            log_path = log_dir / (datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".log")
            render_panel.store()
            settings_file.parent.mkdir(parents=True, exist_ok=True)
            settings.update({
                "channels": ", ".join(values), "data_dir": str(directory),
                "subtitles": subtitles_var.get(), "video_delay": delay,
                "threshold": threshold, "single_threshold": single_threshold, "cooldown": cooldown,
                "language": i18n.language,
            })
            save_settings(settings_file, settings)
            command = [sys.executable]
            if not getattr(sys, "frozen", False):
                command.append(str(Path(__file__).resolve()))
            command += ["--worker", "--channels", ",".join(values),
                        "--data-dir", str(directory), "--video-delay", str(delay),
                        "--threshold", str(threshold), "--single-threshold", str(single_threshold),
                        "--cooldown", str(cooldown), "--render-config", str(render_path),
                        "--chat-config", str(chat_path), "--language", i18n.language]
            if subtitles_var.get():
                command.append("--subtitles")
            environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            process = subprocess.Popen(command, cwd=str(directory), stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                       errors="replace", bufsize=1, env=environment, creationflags=flags)
            state["process"], state["stopping"] = process, False
            set_running(True)
            set_status("status.starting")
            append(i18n.t("log.path", path=log_path))

            def read_output():
                try:
                    with open(log_path, "w", encoding="utf-8", buffering=1) as log:
                        for line in process.stdout:
                            log.write(line)
                            emit("log", line)
                except Exception as error:
                    emit("log_error", str(error))
                finally:
                    process.stdout.close()
                    emit("exit", process.wait())

            threading.Thread(target=read_output, daemon=True).start()
        except Exception as error:
            messagebox.showerror(i18n.t("dialog.start_error"), i18n.error(str(error)), parent=root)

    def stop():
        process = state["process"]
        if process is None or state["stopping"]:
            return
        state["stopping"] = True
        stop_button.configure(state="disabled")
        set_status("status.stopping")

        def terminate():
            if process.poll() is None:
                if os.name == "nt":
                    # Kill the entire worker tree, not just Python, to avoid orphan ffmpeg processes.
                    result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
                    if result.returncode and process.poll() is None:
                        process.kill()
                else:
                    process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

        threading.Thread(target=terminate, daemon=True).start()

    def open_ready():
        directory = Path(directory_var.get()).expanduser().resolve() / "ready"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(directory))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(directory)])
            else:
                subprocess.Popen(["xdg-open", str(directory)])
        except OSError as error:
            messagebox.showerror(i18n.t("dialog.ready_folder"), str(error), parent=root)

    start_button = ttk.Button(controls, text=i18n.t("button.start"), command=start)
    start_button.pack(side="left")
    stop_button = ttk.Button(controls, text=i18n.t("button.stop"), command=stop, state="disabled")
    stop_button.pack(side="left", padx=8)
    ready_button = ttk.Button(controls, command=open_ready)
    ready_button.pack(side="left")
    chat_button = ttk.Button(controls, command=edit_chat_phrases)
    chat_button.pack(side="left", padx=8)

    for widget, key in (
        (language_label, "language"), (channels_label, "label.channels"),
        (channels_hint, "hint.channels"), (data_folder_label, "label.data_folder"),
        (browse, "button.browse"), (subtitle_check, "check.subtitles"),
        (video_shift_label, "label.video_shift"), (thresholds_label, "label.thresholds"),
        (chat_label, "label.chat"), (cooldown_label, "label.cooldown"),
        (lower_more_label, "hint.lower_more"), (start_button, "button.start"),
        (stop_button, "button.stop"), (ready_button, "button.open_ready"),
        (chat_button, "button.chat_phrases"),
    ):
        i18n.bind_text(widget, key)
    i18n.bind_title(root, "window.title")
    i18n.subscribe(lambda: set_status(status_state["key"], **status_state["args"]))

    def close():
        current = chat_editor["instance"]
        if current is not None and current.window.winfo_exists():
            current.close()
            if current.window.winfo_exists():
                return
        if state["process"] is not None:
            if not messagebox.askyesno(i18n.t("dialog.exit"), i18n.t("dialog.exit_prompt"), parent=root):
                return
            state["closing"] = True
            stop()
        else:
            root.destroy()

    def poll():
        for _ in range(200):
            try:
                kind, value = events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                append(value)
                if "recording started" in value:
                    set_status("status.recording")
                elif "READY:" in value:
                    set_status("status.ready")
                elif "FATAL:" in value:
                    set_status("status.fatal")
            elif kind == "log_error":
                append(i18n.t("log.error", error=value))
            elif kind == "exit":
                stopped = state["stopping"]
                state["process"], state["stopping"] = None, False
                set_running(False)
                set_status("status.stopped" if stopped or value == 0 else "status.exit_error", code=value)
                append(i18n.t("log.process_exit", code=value))
                if state["closing"]:
                    root.destroy()
                    return
        root.after(100, poll)

    root.protocol("WM_DELETE_WINDOW", close)
    append(i18n.t("log.setup"))
    root.after(100, poll)
    root.mainloop()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version=f"Twitchautoclipper {__version__}")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--channels", default="")
    parser.add_argument("--data-dir", default=str(default_root() / "data"))
    parser.add_argument("--subtitles", action="store_true")
    parser.add_argument("--video-delay", type=float, default=0)
    parser.add_argument("--threshold", type=float, default=1.2)
    parser.add_argument("--single-threshold", type=float, default=4.0)
    parser.add_argument("--cooldown", type=float, default=40)
    parser.add_argument("--render-config", default="")
    parser.add_argument("--chat-config", default="")
    parser.add_argument("--language", choices=("ru", "en"), default="ru")
    arguments = parser.parse_args()
    if arguments.worker:
        raise SystemExit(worker(arguments))
    gui()
