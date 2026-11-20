"""Saved render options and optional normalized crop rectangles (no extra dependencies)."""
import json
import math
import os
from pathlib import Path


def validate_roi(value):
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("Crop must be [x, y, width, height]")
    x, y, w, h = map(float, value)
    if (not all(map(math.isfinite, (x, y, w, h))) or min(x, y) < 0 or
            min(w, h) <= 0 or x + w > 1.000001 or y + h > 1.000001):
        raise ValueError("Crop must fit inside the source frame")
    return [x, y, w, h]


def read_options(path=None):
    path = path or os.environ.get("CLIP_RENDER_CONFIG")
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid render configuration")
    return data


def save_options(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


class RenderPanel:
    def __init__(self, parent, config_path, channels, directory, notify, i18n=None):
        import tkinter as tk
        from tkinter import ttk
        from i18n import I18n
        self.tk, self.ttk = tk, ttk
        self.i18n = i18n if i18n is not None else I18n()
        self.path, self.channels, self.directory, self.notify = Path(config_path), channels, directory, notify
        try:
            self.data = read_options(self.path)
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("crops", {})
        self.banner = tk.StringVar(value=self.data.get("banner", ""))
        self.music = tk.StringVar(value=self.data.get("music", ""))
        self.enabled = tk.BooleanVar(value=self.data.get("split_camera", True))
        self.variation = tk.BooleanVar(value=self.data.get("video_variation", True))
        self.random_fps = tk.BooleanVar(value=self.data.get("random_fps", True))
        self.random_metadata = tk.BooleanVar(value=self.data.get("random_metadata", True))
        self.channel = tk.StringVar()
        # The selected crop is an internal key, never a translated label.
        self._kind_key = "camera"
        self.kind = tk.StringVar()
        self.info = tk.StringVar()
        self.i18n.bind_variable(self.info, "render.info.empty")
        self.frame = self._text(ttk.LabelFrame(parent, padding=8), "render.frame_title")
        self.frame.columnconfigure(1, weight=1)
        self._text(ttk.Label(self.frame), "render.banner").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.frame, textvariable=self.banner).grid(row=0, column=1, sticky="ew", padx=6)
        self._text(ttk.Button(self.frame, command=self.choose_banner), "render.file").grid(row=0, column=2)
        self._text(ttk.Button(self.frame, command=lambda: self.banner.set("")), "render.remove").grid(row=0, column=3, padx=4)
        self._text(ttk.Label(self.frame), "render.music").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(self.frame, textvariable=self.music).grid(row=1, column=1, sticky="ew", padx=6)
        self._text(ttk.Button(self.frame, command=self.choose_music), "render.track").grid(row=1, column=2)
        self._text(ttk.Button(self.frame, command=self.choose_music_dir), "render.folder").grid(row=1, column=3, padx=4)
        self._text(ttk.Checkbutton(self.frame, variable=self.enabled), "render.split_camera").grid(
            row=2, column=0, columnspan=4, sticky="w")
        bar = ttk.Frame(self.frame)
        bar.grid(row=3, column=0, columnspan=4, sticky="ew", pady=6)
        self.combo = ttk.Combobox(bar, textvariable=self.channel, width=16, state="readonly",
                                  postcommand=self.refresh_channels)
        self.combo.pack(side="left")
        self.combo.bind("<<ComboboxSelected>>", lambda event: self.show_info())
        self.kinds = ttk.Combobox(bar, textvariable=self.kind, width=17, state="readonly")
        self.kinds.pack(side="left", padx=5)
        self.kinds.bind("<<ComboboxSelected>>", self._select_kind)
        self._translate_kind()
        self.i18n.subscribe(self._translate_kind)
        self._text(ttk.Button(bar, command=lambda: self.select_frame(True)), "render.frame_from_buffer").pack(side="left")
        self._text(ttk.Button(bar, command=lambda: self.select_frame(False)), "render.frame_from_file").pack(side="left", padx=5)
        self._text(ttk.Button(bar, command=self.clear_roi), "render.reset_roi").pack(side="left")
        self._text(ttk.Button(bar, command=self.apply), "render.apply").pack(side="left", padx=5)
        actions = ttk.Frame(self.frame)
        actions.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(0, 5))
        self._text(ttk.Button(actions, command=self.banner_window), "render.banner_position").pack(side="left")
        self._text(ttk.Checkbutton(actions, variable=self.variation), "render.variation").pack(side="left", padx=10)
        fps_bar = ttk.Frame(self.frame)
        fps_bar.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(0, 5))
        self._text(ttk.Checkbutton(fps_bar, variable=self.random_fps), "render.random_fps").pack(side="left")
        self._text(ttk.Label(fps_bar), "render.metadata").pack(side="right")
        self._text(ttk.Checkbutton(self.frame, variable=self.random_metadata), "render.random_metadata").grid(
            row=6, column=0, columnspan=4, sticky="w", pady=(0, 5))
        ttk.Label(self.frame, textvariable=self.info, wraplength=850).grid(row=7, column=0, columnspan=4, sticky="w")
        self.refresh_channels()

    def _text(self, widget, key):
        self.i18n.bind_text(widget, key)
        return widget

    def _watch_window(self, window, update):
        def translate():
            try:
                if window.winfo_exists():
                    update()
            except self.tk.TclError:
                pass
        translate()
        self.i18n.subscribe(translate)

    def _local(self, ru, en):
        """Small labels not present in the shared catalogue."""
        return en if self.i18n.language == "en" else ru

    def _kind_label(self, key):
        return self.i18n.t("render.camera" if key == "camera" else "render.content")

    def _translate_kind(self):
        try:
            if self.frame.winfo_exists():
                self.kinds.configure(values=(self._kind_label("camera"), self._kind_label("content")))
                self.kinds.current(0 if self._kind_key == "camera" else 1)
                # Keep the current feedback, including an in-progress frame request.
                self._translate_info()
        except self.tk.TclError:
            pass

    def _select_kind(self, event=None):
        self._kind_key = "camera" if self.kinds.current() == 0 else "content"
        self.show_info()

    def _translate_info(self):
        # Rebind the dynamic kind label without changing the feedback state.
        state = getattr(self, "_info_state", None)
        if state is not None:
            key, values = state
            values = {**values, "kind": self._kind_label(self.key())}
            self.i18n.bind_variable(self.info, key, **values)

    def _error(self, error):
        message = str(error)
        translations = {
            "Crop must be [x, y, width, height]": "Область должна содержать [x, y, ширину, высоту]",
            "Crop must fit inside the source frame": "Область должна находиться внутри исходного кадра",
            "Invalid render configuration": "Некорректные настройки монтажа",
        }
        if self.i18n.language == "ru" and message in translations:
            return translations[message]
        return self.i18n.error(message)

    def refresh_channels(self):
        import re
        values = []
        for value in re.split(r"[,;\s]+", self.channels().strip().lower()):
            value = re.sub(r"^(?:https?://)?(?:www\.)?twitch\.tv/", "", value).strip("/")
            if re.fullmatch(r"[a-z0-9_]{1,25}", value) and value not in values:
                values.append(value)
        self.combo.configure(values=values)
        if self.channel.get() not in values:
            self.channel.set(values[0] if values else "")
        self.show_info()

    def key(self):
        return self._kind_key

    def show_info(self):
        channel = self.channel.get()
        if not channel:
            self._info_state = None
            self.i18n.bind_variable(self.info, "render.info.empty")
            return
        roi = self.data["crops"].get(channel, {}).get(self.key())
        values = {"channel": channel}
        if roi:
            values.update(zip(("x", "y", "width", "height"), (v * 100 for v in roi)))
        self._info_state = ("render.info.roi" if roi else "render.info.default", values)
        self._translate_info()


    def choose_banner(self):
        from tkinter import filedialog
        result = filedialog.askopenfilename(parent=self.frame, title=self.i18n.t("render.dialog.banner_file"),
                                            filetypes=[(self._local("Видео", "Video"), "*.mp4 *.mov *.mkv *.webm"),
                                                       (self._local("Все файлы", "All files"), "*.*")])
        if result:
            self.banner.set(result)

    def choose_music(self):
        from tkinter import filedialog
        result = filedialog.askopenfilename(parent=self.frame, title=self.i18n.t("render.dialog.music_file"),
                                            filetypes=[(self._local("Аудио", "Audio"), "*.mp3 *.wav *.m4a *.ogg *.flac"),
                                                       (self._local("Все файлы", "All files"), "*.*")])
        if result:
            self.music.set(result)

    def choose_music_dir(self):
        from tkinter import filedialog
        result = filedialog.askdirectory(parent=self.frame, title=self.i18n.t("render.dialog.music_folder"))
        if result:
            self.music.set(result)

    def store(self):
        for label, value in (("render.banner", self.banner.get()), ("render.music", self.music.get())):
            if value.strip() and not Path(value.strip()).exists():
                raise ValueError(self.i18n.t("render.error.path", label=self.i18n.t(label).rstrip(":"), value=value))
        if self.banner.get().strip() and not Path(self.banner.get().strip()).is_file():
            raise ValueError(self.i18n.t("render.error.banner_file"))
        self.data.update(banner=str(Path(self.banner.get().strip()).resolve()) if self.banner.get().strip() else "",
                         music=str(Path(self.music.get().strip()).resolve()) if self.music.get().strip() else "",
                         split_camera=self.enabled.get(), video_variation=self.variation.get(),
                         random_fps=self.random_fps.get(), random_metadata=self.random_metadata.get())
        for regions in self.data["crops"].values():
            for roi in regions.values():
                validate_roi(roi)
        save_options(self.path, self.data)

    def apply(self):
        from tkinter import messagebox
        try:
            self.store()
            self.notify(self.i18n.t("render.notify_saved"))
        except Exception as error:
            messagebox.showerror(self._local("Монтаж", "Editing"), self._error(error), parent=self.frame)

    def clear_roi(self):
        self.data["crops"].get(self.channel.get(), {}).pop(self.key(), None)
        self.show_info()

    def select_frame(self, use_buffer):
        import tempfile
        from tkinter import filedialog, messagebox
        from montage import tool, run_tool
        channel, key = self.channel.get(), self.key()
        if not channel:
            messagebox.showinfo(self.i18n.t("render.dialog.area"),
                                self.i18n.t("render.dialog.start_channel"), parent=self.frame)
            return
        if use_buffer:
            from main import list_segments
            candidates = list_segments(Path(self.directory()).expanduser() / "buf" / channel)
            if not candidates:
                messagebox.showinfo(self.i18n.t("render.dialog.buffer"),
                                    self.i18n.t("render.dialog.wait_buffer"), parent=self.frame)
                return
            source = candidates[-1].path
        else:
            source = filedialog.askopenfilename(parent=self.frame, title=self.i18n.t("render.dialog.frame_file"),
                                                filetypes=[(self._local("Видео и изображения", "Video and images"),
                                                            "*.mp4 *.mkv *.ts *.mov *.png *.jpg *.jpeg *.webp"),
                                                           (self._local("Все файлы", "All files"), "*.*")])
            if not source:
                return
        try:
            self._info_state = None
            self.i18n.bind_variable(self.info, "render.info.getting_frame")
            self.frame.update_idletasks()
            with tempfile.TemporaryDirectory(prefix="clipper_frame_") as work:
                image_path = str(Path(work) / "frame.png")
                run_tool([tool("ffmpeg"), "-loglevel", "error", "-y", "-i", str(source),
                          "-frames:v", "1", "-vf", "scale=960:540:force_original_aspect_ratio=decrease",
                          image_path], capture_output=True, timeout=20)
                image = self.tk.PhotoImage(file=image_path)
            self.selection_window(image, channel, key)
        except Exception as error:
            messagebox.showerror(self.i18n.t("render.dialog.frame"), self._error(error), parent=self.frame)
            self.show_info()

    def selection_window(self, image, channel, key):
        from tkinter import messagebox
        tk, ttk = self.tk, self.ttk
        window = tk.Toplevel(self.frame)
        self._watch_window(window, lambda: window.title(self.i18n.t(
            "render.selection_title", channel=channel,
            kind=self._local("вебкамеру", "webcam") if key == "camera" else self._local("основной кадр", "main frame"))))
        window.transient(self.frame.winfo_toplevel())
        width, height = image.width(), image.height()
        canvas = tk.Canvas(window, width=width, height=height, highlightthickness=0)
        canvas.pack()
        canvas.image = image
        canvas.create_image(0, 0, anchor="nw", image=image)
        selected = {"start": None, "roi": None, "rect": None}

        def position(event):
            return max(0, min(width, event.x)), max(0, min(height, event.y))

        def down(event):
            selected["start"] = position(event)
            selected["roi"] = None
            if selected["rect"] is not None:
                canvas.delete(selected["rect"])
            x, y = selected["start"]
            selected["rect"] = canvas.create_rectangle(x, y, x, y, outline="#ff3333", width=3)

        def drag(event):
            if selected["start"] is None:
                return
            x0, y0 = selected["start"]
            x1, y1 = position(event)
            canvas.coords(selected["rect"], x0, y0, x1, y1)
            x, y, w, h = min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)
            selected["roi"] = [x / width, y / height, w / width, h / height] if w >= 8 and h >= 8 else None

        def accept():
            if selected["roi"] is None:
                messagebox.showinfo(self.i18n.t("render.dialog.area"),
                                    self.i18n.t("render.dialog.draw_area"), parent=window)
                return
            self.data["crops"].setdefault(channel, {})[key] = validate_roi(selected["roi"])
            try:
                self.store()
            except Exception as error:
                messagebox.showerror(self.i18n.t("render.dialog.save"), self._error(error), parent=window)
                return
            self.show_info()
            self.notify(self.i18n.t("render.notify_roi", kind=self._kind_label(key), channel=channel))
            window.destroy()

        canvas.bind("<Button-1>", down)
        canvas.bind("<B1-Motion>", drag)
        canvas.bind("<ButtonRelease-1>", drag)
        self._text(ttk.Button(window, command=accept), "render.save_area").pack(pady=8)

    def banner_window(self):
        """Place a banner in output coordinates, never in source-stream coordinates."""
        from tkinter import messagebox
        channel = self.channel.get()
        if not channel:
            messagebox.showinfo(self.i18n.t("render.banner_label"),
                                self.i18n.t("render.dialog.start_channel"), parent=self.frame)
            return
        tk, ttk = self.tk, self.ttk
        window = tk.Toplevel(self.frame)
        self.i18n.bind_title(window, "render.banner_title", channel=channel)
        window.transient(self.frame.winfo_toplevel())
        self._text(ttk.Label(window, padding=8), "render.banner_help").pack()
        width, height = 288, 512
        canvas = tk.Canvas(window, width=width, height=height, bg="#20252b", highlightthickness=0)
        canvas.pack(padx=12)
        split = self.enabled.get() and bool(self.data["crops"].get(channel, {}).get("camera"))
        camera_label = None
        if split:
            canvas.create_rectangle(0, 0, width, height / 3, fill="#364553", outline="")
            camera_label = canvas.create_text(width / 2, height / 6, text=self.i18n.t("render.camera"), fill="white")
            canvas.create_line(0, height / 3, width, height / 3, fill="#748390")
        content_label = canvas.create_text(width / 2, height * (2 / 3 if split else 1 / 2),
                                          text=self.i18n.t("render.content"), fill="#d8e0e6")
        saved = self.data["crops"].get(channel, {}).get("banner")
        state = {"roi": list(saved) if saved else [1 / 12, 650 / 1920, 5 / 6, 0.16],
                 "start": None, "origin": None, "moving": False, "resize": None, "reset": False}
        rect = canvas.create_rectangle(0, 0, 0, 0, outline="#ffca66", width=2, dash=(5, 3))
        label = canvas.create_text(0, 0, text=self.i18n.t("render.banner_label"), fill="#ffca66")
        handles = {key: canvas.create_rectangle(0, 0, 0, 0, fill="#ffca66", outline="#20252b")
                   for key in ("nw", "ne", "sw", "se", "n", "e", "s", "w")}
        cursors = {"nw": "top_left_corner", "ne": "top_right_corner",
                   "sw": "bottom_left_corner", "se": "bottom_right_corner",
                   "n": "sb_v_double_arrow", "s": "sb_v_double_arrow",
                   "w": "sb_h_double_arrow", "e": "sb_h_double_arrow"}
        info = tk.StringVar()
        ttk.Label(window, textvariable=info, padding=6).pack()

        def handle_points():
            x, y, w, h = state["roi"]
            return {"nw": (x, y), "ne": (x + w, y), "sw": (x, y + h),
                    "se": (x + w, y + h), "n": (x + w / 2, y),
                    "e": (x + w, y + h / 2), "s": (x + w / 2, y + h),
                    "w": (x, y + h / 2)}

        def hit_handle(px, py):
            for key, (hx, hy) in handle_points().items():
                if abs(px - hx) * width <= 7 and abs(py - hy) * height <= 7:
                    return key
            return None

        def draw():
            x, y, w, h = state["roi"]
            canvas.coords(rect, x * width, y * height, (x + w) * width, (y + h) * height)
            canvas.coords(label, (x + w / 2) * width, (y + h / 2) * height)
            for key, (hx, hy) in handle_points().items():
                canvas.coords(handles[key], hx * width - 4, hy * height - 4,
                              hx * width + 4, hy * height + 4)
            if state["reset"]:
                self.i18n.bind_variable(info, "render.banner_reset_info")
            else:
                self.i18n.bind_variable(info, "render.banner_dimensions", x=x * 1080, y=y * 1920,
                                        width=w * 1080, height=h * 1920)

        def translate_canvas():
            if camera_label is not None:
                canvas.itemconfigure(camera_label, text=self.i18n.t("render.camera"))
            canvas.itemconfigure(content_label, text=self.i18n.t("render.content"))
            canvas.itemconfigure(label, text=self.i18n.t("render.banner_label"))


        def position(event):
            return max(0, min(1, event.x / width)), max(0, min(1, event.y / height))

        def hover(event):
            if state["start"] is not None:
                return
            px, py = position(event)
            handle = None if getattr(event, "state", 0) & 1 else hit_handle(px, py)
            x, y, w, h = state["roi"]
            inside = x <= px <= x + w and y <= py <= y + h
            canvas.configure(cursor=cursors[handle] if handle else
                             "crosshair" if getattr(event, "state", 0) & 1 else
                             "fleur" if inside else "crosshair")

        def down(event):
            px, py = position(event)
            x, y, w, h = state["roi"]
            shift = getattr(event, "state", 0) & 1
            handle = None if shift else hit_handle(px, py)
            state.update(start=(px, py), origin=list(state["roi"]), resize=handle,
                         moving=not handle and not shift and x <= px <= x + w and y <= py <= y + h,
                         reset=False)
            canvas.configure(cursor=cursors[handle] if handle else "fleur" if state["moving"] else "crosshair")

        def drag(event):
            if state["start"] is None:
                return
            px, py = position(event)
            sx, sy = state["start"]
            if state["resize"]:
                x, y, w, h = state["origin"]
                left, top, right, bottom = x, y, x + w, y + h
                min_w, min_h = min(4 / width, w), min(4 / height, h)
                handle = state["resize"]
                if "w" in handle:
                    left = max(0, min(right - min_w, x + (px - sx)))
                if "e" in handle:
                    right = min(1, max(left + min_w, x + w + (px - sx)))
                if "n" in handle:
                    top = max(0, min(bottom - min_h, y + (py - sy)))
                if "s" in handle:
                    bottom = min(1, max(top + min_h, y + h + (py - sy)))
                state["roi"] = [left, top, right - left, bottom - top]
            elif state["moving"]:
                x, y, w, h = state["origin"]
                state["roi"] = [max(0, min(1 - w, x + px - sx)),
                                max(0, min(1 - h, y + py - sy)), w, h]
            elif abs(px - sx) * width >= 4 and abs(py - sy) * height >= 4:
                state["roi"] = [min(sx, px), min(sy, py), abs(px - sx), abs(py - sy)]
            draw()

        def release(event):
            drag(event)
            state["start"] = None
            state["resize"] = None
            hover(event)

        def reset():
            state.update(roi=[1 / 12, 650 / 1920, 5 / 6, 0.16], reset=True,
                         start=None, resize=None, moving=False)
            draw()
            self.i18n.bind_variable(info, "render.banner_reset_info")

        def accept():
            regions = self.data["crops"].setdefault(channel, {})
            previous = regions.get("banner")
            if state["reset"]:
                regions.pop("banner", None)
            else:
                regions["banner"] = validate_roi(state["roi"])
            try:
                self.store()
            except Exception as error:
                if previous is None:
                    regions.pop("banner", None)
                else:
                    regions["banner"] = previous
                messagebox.showerror(self.i18n.t("render.banner_label"), self._error(error), parent=window)
                return
            self.notify(self.i18n.t("render.notify_banner", channel=channel))
            window.destroy()

        canvas.bind("<Motion>", hover)
        canvas.bind("<Leave>", lambda event: canvas.configure(cursor="") if state["start"] is None else None)
        canvas.bind("<Button-1>", down)
        canvas.bind("<B1-Motion>", drag)
        canvas.bind("<ButtonRelease-1>", release)
        buttons = ttk.Frame(window, padding=8)
        buttons.pack()
        self._text(ttk.Button(buttons, command=reset), "render.reset").pack(side="left", padx=4)
        self._text(ttk.Button(buttons, command=accept), "render.save_position").pack(side="left", padx=4)
        self._watch_window(window, translate_canvas)
        draw()
