"""Literal chat reactions, atomic configuration and the optional Tkinter editor."""
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata

MAX_GROUPS, MAX_VARIANTS, MAX_LENGTH, MAX_BYTES = 200, 30, 160, 256 * 1024


def normalize_text(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def validate_config(data):
    if not isinstance(data, dict) or not isinstance(data.get("enabled", True), bool):
        raise ValueError("Настройки чата должны содержать переключатель enabled")
    groups = data.get("phrases", [])
    if not isinstance(groups, list) or len(groups) > MAX_GROUPS:
        raise ValueError(f"Можно добавить не более {MAX_GROUPS} групп фраз")
    result, seen = [], set()
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("phrase"), str):
            raise ValueError("У каждой группы должна быть основная фраза")
        variants = group.get("variants", [])
        if not isinstance(variants, list) or len(variants) > MAX_VARIANTS:
            raise ValueError(f"У фразы может быть не более {MAX_VARIANTS} вариантов")
        cleaned = []
        for value in [group["phrase"], *variants]:
            if not isinstance(value, str) or not value.strip() or len(value) > MAX_LENGTH:
                raise ValueError(f"Фраза и каждый вариант: от 1 до {MAX_LENGTH} символов")
            value = " ".join(value.split())
            key = normalize_text(value)
            if not key:
                raise ValueError("Фраза не может быть пустой")
            if key not in seen:
                cleaned.append(value)
                seen.add(key)
            elif not cleaned:
                raise ValueError(f"Фраза уже добавлена как фраза или вариант: {value}")
        result.append({"phrase": cleaned[0], "variants": cleaned[1:]})
    return {"enabled": data.get("enabled", True), "phrases": result}


def read_config(path):
    path = Path(path)
    if not path.exists():
        return {"enabled": True, "phrases": []}
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Слишком большой файл настроек чата")
    return validate_config(json.loads(path.read_text(encoding="utf-8")))


def save_config(path, data):
    data = validate_config(data)
    content = json.dumps(data, ensure_ascii=False, indent=2)
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Слишком много текста в настройках чата")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            file.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return data


class PhraseMatcher:
    def __init__(self, data=None):
        self.config = validate_config(data if data is not None else {})
        self.patterns = []
        if self.config["enabled"]:
            for group in self.config["phrases"]:
                alternatives = []
                for value in [group["phrase"], *group["variants"]]:
                    value = normalize_text(value)
                    start = r"(?<!\w)" if re.match(r"\w", value[0]) else ""
                    end = r"(?!\w)" if re.match(r"\w", value[-1]) else ""
                    alternatives.append(start + re.escape(value) + end)
                self.patterns.append((group["phrase"], re.compile("|".join(alternatives))))

    def match(self, text):
        text = normalize_text(text)
        return next((label for label, pattern in self.patterns if pattern.search(text)), None)


class ChatConfigReloader:
    """Poll once per detector tick. Failed edits keep the last valid matcher."""
    def __init__(self, path, notify=print):
        self.path = Path(path) if path else None
        self.notify = notify
        self.stamp = object()
        self.error = None

    def poll(self):
        if self.path is None:
            return None
        try:
            try:
                stat = self.path.stat()
                stamp = (stat.st_mtime_ns, stat.st_size)
            except FileNotFoundError:
                stamp = None
            if stamp == self.stamp:
                return None
            self.stamp = stamp
            matcher = PhraseMatcher(read_config(self.path))
            self.notify(f"CHAT: loaded {len(matcher.config['phrases'])} phrase groups; "
                        f"enabled={matcher.config['enabled']}")
            self.error = None
            return matcher
        except (OSError, ValueError) as error:
            if str(error) != self.error:
                self.notify(f"CHAT: settings not applied; keeping previous phrases: {error}")
                self.error = str(error)
            return None


class ChatPhraseEditor:
    """Native separate window: group list, phrase/variants, and message preview."""
    def __init__(self, parent, path, notify, i18n=None):
        import tkinter as tk
        from tkinter import ttk, messagebox
        from i18n import I18n
        self.tk, self.ttk, self.messagebox = tk, ttk, messagebox
        self.i18n = i18n if i18n is not None else I18n()
        self.path, self.notify = Path(path), notify
        self.data = read_config(self.path)
        self.selected = None
        self.dirty = False
        self.loading = False
        self.window = tk.Toplevel(parent)
        self.i18n.bind_title(self.window, "chat.title")
        self.window.geometry("820x640")
        self.window.minsize(720, 560)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(2, weight=1)
        self.enabled = tk.BooleanVar(value=self.data["enabled"])
        self.phrase = tk.StringVar()
        self.preview = tk.StringVar()
        self.feedback = tk.StringVar()
        self.i18n.bind_variable(self.feedback, "chat.feedback.initial")
        self._text(ttk.Label(self.window, font=("Segoe UI", 15, "bold")), "chat.header").grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 6))
        self._text(ttk.Checkbutton(self.window, variable=self.enabled, command=self.changed),
                   "chat.enabled").grid(row=1, column=0, sticky="w", padx=16)
        self.build_body()
        bottom = ttk.Frame(self.window, padding=(16, 6, 16, 14))
        bottom.grid(row=3, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.feedback, wraplength=740).grid(row=0, column=0, columnspan=3, sticky="w", pady=6)
        self._text(ttk.Label(bottom), "chat.explanation").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self._text(ttk.Button(bottom, command=self.save), "chat.save").grid(row=2, column=1, padx=6)
        self._text(ttk.Button(bottom, command=self.close), "chat.close").grid(row=2, column=2)
        self.window.bind("<Control-s>", lambda event: self.save())
        self.refresh()

    def _text(self, widget, key):
        self.i18n.bind_text(widget, key)
        return widget

    def _translate_heading(self):
        # Update only interface chrome: never refresh the list or reload drafts.
        try:
            if self.window.winfo_exists():
                self.tree.heading("phrase", text=self.i18n.t("chat.primary"))
        except self.tk.TclError:
            pass

    def build_body(self):
        tk, ttk = self.tk, self.ttk
        body = ttk.Frame(self.window, padding=16)
        body.grid(row=2, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        self._text(ttk.Label(left), "chat.groups").grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.tree = ttk.Treeview(left, columns=("phrase",), show="headings", selectmode="browse", height=9)
        self._translate_heading()
        self.i18n.subscribe(self._translate_heading)
        self.tree.column("phrase", width=220, minwidth=120)
        self.tree.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        buttons = ttk.Frame(left)
        buttons.grid(row=2, column=0, sticky="w", pady=7)
        self._text(ttk.Button(buttons, command=self.new), "chat.new").pack(side="left")
        self._text(ttk.Button(buttons, command=self.delete), "chat.delete").pack(side="left", padx=5)
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)
        self._text(ttk.Label(right), "chat.primary_example").grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.entry = ttk.Entry(right, textvariable=self.phrase)
        self.entry.grid(row=1, column=0, sticky="ew")
        self._text(ttk.Label(right), "chat.variants").grid(row=2, column=0, sticky="w", pady=(12, 5))
        self.variants = tk.Text(right, height=7, width=35, wrap="word", undo=True)
        self.variants.grid(row=3, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.variants.yview)
        scrollbar.grid(row=3, column=1, sticky="ns")
        self.variants.configure(yscrollcommand=scrollbar.set)
        self._text(ttk.Button(right, command=self.commit), "chat.commit").grid(row=4, column=0, sticky="w", pady=8)
        self._text(ttk.Label(right), "chat.check_label").grid(row=5, column=0, sticky="w", pady=(8, 5))
        ttk.Entry(right, textvariable=self.preview).grid(row=6, column=0, sticky="ew")
        self._text(ttk.Button(right, command=self.check), "chat.check").grid(row=7, column=0, sticky="w", pady=8)
        self.phrase.trace_add("write", lambda *args: self.changed())
        self.variants.bind("<<Modified>>", self.text_changed)

    def changed(self):
        if not self.loading:
            self.dirty = True

    def text_changed(self, event=None):
        if self.variants.edit_modified():
            self.dirty = True
            self.variants.edit_modified(False)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for index, group in enumerate(self.data["phrases"]):
            self.tree.insert("", "end", iid=str(index), values=(group["phrase"],))

    def load_fields(self, group=None):
        group = group or {"phrase": "", "variants": []}
        self.loading = True
        try:
            self.phrase.set(group["phrase"])
            self.variants.delete("1.0", "end")
            self.variants.insert("1.0", "\n".join(group["variants"]))
            self.variants.edit_modified(False)
        finally:
            self.loading = False

    def select(self, event=None):
        selection = self.tree.selection()
        if selection:
            index = int(selection[0])
            if index == self.selected:
                return
            if self.fields_changed() and not self.commit():
                self.tree.selection_set(str(self.selected)) if self.selected is not None else self.tree.selection_remove(*selection)
                return
            self.selected = index
            self.tree.selection_set(str(index))
            self.load_fields(self.data["phrases"][index])

    def fields_changed(self):
        draft = self.draft()
        if self.selected is None:
            return bool(draft["phrase"] or draft["variants"])
        return draft != self.data["phrases"][self.selected]

    def draft(self):
        return {"phrase": self.phrase.get().strip(),
                "variants": [line.strip() for line in self.variants.get("1.0", "end-1c").splitlines() if line.strip()]}

    def commit(self):
        groups = list(self.data["phrases"])
        draft = self.draft()
        if self.selected is None:
            groups.append(draft)
            index = len(groups) - 1
        else:
            index = self.selected
            groups[index] = draft
        try:
            self.data = validate_config({"enabled": self.enabled.get(), "phrases": groups})
        except ValueError as error:
            self.messagebox.showerror(self.i18n.t("chat.title_short"), self.i18n.error(str(error)), parent=self.window)
            return False
        self.selected = index
        self.refresh()
        self.tree.selection_set(str(index))
        self.load_fields(self.data["phrases"][index])
        self.dirty = True
        self.i18n.bind_variable(self.feedback, "chat.feedback.updated")
        return True

    def new(self):
        if self.fields_changed() and not self.commit():
            return
        self.selected = None
        self.tree.selection_remove(*self.tree.selection())
        self.load_fields()
        self.entry.focus_set()

    def delete(self):
        if self.selected is None:
            return
        del self.data["phrases"][self.selected]
        self.selected = None
        self.refresh()
        self.load_fields()
        self.dirty = True
        self.i18n.bind_variable(self.feedback, "chat.feedback.deleted")

    def check(self):
        if self.fields_changed() and not self.commit():
            return
        label = PhraseMatcher({**self.data, "enabled": self.enabled.get()}).match(self.preview.get())
        if label:
            self.i18n.bind_variable(self.feedback, "chat.feedback.match", label=label)
        else:
            self.i18n.bind_variable(self.feedback, "chat.feedback.no_match")

    def save(self):
        if self.fields_changed() and not self.commit():
            return
        try:
            self.data = save_config(self.path, {**self.data, "enabled": self.enabled.get()})
        except (OSError, ValueError) as error:
            self.messagebox.showerror(self.i18n.t("chat.title_short"), self.i18n.error(str(error)), parent=self.window)
            return
        self.dirty = False
        self.i18n.bind_variable(self.feedback, "chat.feedback.saved")
        self.notify(self.i18n.t("chat.notify.saved"))

    def close(self):
        if self.dirty or self.fields_changed():
            choice = self.messagebox.askyesnocancel(self.i18n.t("chat.title_short"),
                                                    self.i18n.t("chat.close_prompt"), parent=self.window)
            if choice is None:
                return
            if choice:
                self.save()
                if self.dirty or self.fields_changed():
                    return
        self.window.destroy()
