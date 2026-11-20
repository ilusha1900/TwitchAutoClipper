"""Small runtime translation helper for the Tkinter interface.

Russian is intentionally the fallback language so existing installations keep
working exactly as before.  The selected language is stored by the GUI in its
settings.json file.
"""

from __future__ import annotations

import re
import weakref

from version import __version__


LANGUAGES = ("ru", "en")
LANGUAGE_NAMES = {"ru": "Русский", "en": "English"}


_STRINGS = {
    "ru": {
        "language": "Язык",
        "window.title": f"Twitchautoclipper {__version__} — запись и монтаж",
        "status.stopped": "Остановлено",
        "status.starting": "Запущено — подключение к Twitch…",
        "status.recording": "Запись идёт — ожидание интересных моментов",
        "status.ready": "Готов новый клип — папка ready",
        "status.fatal": "Ошибка запуска — подробности в журнале",
        "status.stopping": "Остановка записи и FFmpeg…",
        "status.exit_error": "Ошибка: код {code}. См. журнал.",
        "label.channels": "Каналы:",
        "hint.channels": "Ники через запятую, например: example_channel, другой_канал",
        "label.data_folder": "Папка данных:",
        "button.browse": "Выбрать…",
        "dialog.data_folder": "Папка для буфера, клипов и музыки",
        "check.subtitles": "Субтитры (нужна сборка с faster-whisper)",
        "label.video_shift": "Сдвиг окна видео относительно чата, сек:",
        "label.thresholds": "Пороги: общий",
        "label.chat": "чат",
        "label.cooldown": "пауза, с",
        "hint.lower_more": "Меньше = чаще",
        "button.start": "Запустить",
        "button.stop": "Остановить",
        "button.open_ready": "Открыть готовые клипы",
        "button.chat_phrases": "Фразы чата…",
        "dialog.chat_phrases": "Фразы чата",
        "dialog.start_error": "Не удалось запустить",
        "dialog.ready_folder": "Папка клипов",
        "dialog.language_save": "Не удалось сохранить язык",
        "dialog.exit": "Выход",
        "dialog.exit_prompt": "Остановить запись и закрыть программу? Текущий незавершённый монтаж может быть прерван.",
        "log.setup": "Монтаж: укажи баннер/музыку и выдели вебкамеру на кадре. Области можно менять во время записи.\n",
        "log.path": "\nЛог: {path}\n",
        "log.process_exit": "\nПроцесс завершён, код {code}.\n",
        "log.error": "Ошибка журнала: {error}\n",
        "error.channel": "Некорректный ник Twitch: {channel}",
        "error.channel_required": "Укажи хотя бы один канал",
        "error.delay": "Сдвиг должен быть от -60 до 60 секунд",
        "error.threshold": "Пороги должны быть от 0.1 до 8",
        "error.cooldown": "Пауза должна быть от 1 до 600 секунд",
        "render.frame_title": "Монтаж — без ника стримера",
        "render.banner": "Баннер:",
        "render.music": "Музыка:",
        "render.file": "Файл…",
        "render.remove": "Убрать",
        "render.track": "Трек…",
        "render.folder": "Папка…",
        "render.split_camera": "Вебкамера сверху, основной кадр снизу (пустые пути = без баннера/музыки)",
        "render.camera": "Вебкамера",
        "render.content": "Основной кадр",
        "render.frame_from_buffer": "Кадр из буфера",
        "render.frame_from_file": "Из файла…",
        "render.reset_roi": "Сброс области",
        "render.apply": "Применить монтаж",
        "render.banner_position": "Разместить баннер 9:16…",
        "render.variation": "Обработка: зеркало видео, мягкий цвет, камера 102–106%",
        "render.random_fps": "Случайный FPS: исходный ±0,1–2 (без изменения скорости)",
        "render.metadata": "Метаданные: CapCut",
        "render.random_metadata": "Случайные описательные метаданные и имя MP4",
        "render.info.empty": "Выделите вебкамеру на кадре для каждого канала",
        "render.info.roi": "{channel} / {kind}: x={x:.1f}%, y={y:.1f}%, ширина={width:.1f}%, высота={height:.1f}%",
        "render.info.default": "{channel} / {kind}: не задана; основной кадр по умолчанию целиком",
        "render.dialog.banner_file": "Баннер на зелёном фоне",
        "render.dialog.music_file": "Фоновая музыка",
        "render.dialog.music_folder": "Папка с музыкой",
        "render.dialog.frame_file": "Кадр стрима: видео или снимок",
        "render.dialog.frame": "Кадр",
        "render.dialog.area": "Область",
        "render.dialog.buffer": "Буфер",
        "render.dialog.save": "Сохранение",
        "render.dialog.draw_area": "Обведите нужную область мышью",
        "render.dialog.start_channel": "Сначала укажите канал",
        "render.dialog.wait_buffer": "Запустите запись и подождите 15–30 секунд, затем повторите.",
        "render.info.getting_frame": "Получение кадра…",
        "render.selection_title": "{channel}: выделите {kind} мышью",
        "render.save_area": "Сохранить область",
        "render.banner_title": "{channel}: положение баннера на готовом видео",
        "render.banner_help": "Размер: потяните за маркеры по углам или сторонам рамки.\nПеремещение: потяните внутри. Новая область: Shift + мышь.\nПропорции баннера сохраняются.",
        "render.banner_label": "Баннер",
        "render.banner_dimensions": "x={x:.0f}, y={y:.0f}; область {width:.0f}×{height:.0f}",
        "render.banner_reset_info": "Будет восстановлен стандартный размер и положение баннера",
        "render.reset": "Сбросить",
        "render.save_position": "Сохранить положение",
        "render.notify_saved": "Настройки монтажа сохранены — применятся к следующим заданиям.\n",
        "render.notify_roi": "Область {kind} для {channel} сохранена.\n",
        "render.notify_banner": "Положение баннера для {channel} сохранено.\n",
        "render.error.path": "{label}: путь не найден: {value}",
        "render.error.banner_file": "Баннер должен быть файлом",
        "chat.title": "Сигналы чата — фразы и варианты",
        "chat.title_short": "Фразы чата",
        "chat.header": "Свои реакции зрителей",
        "chat.enabled": "Учитывать мои фразы как сигналы интересного момента",
        "chat.feedback.initial": "Добавьте фразу и варианты её написания.",
        "chat.explanation": "Совпадение усиливает реакции чата, но не создаёт клип само по себе.\nРегистр не важен; варианты задаются явно, без регулярных выражений.",
        "chat.save": "Сохранить и применить",
        "chat.close": "Закрыть",
        "chat.groups": "Группы фраз",
        "chat.primary": "Основная фраза",
        "chat.new": "Новая",
        "chat.delete": "Удалить",
        "chat.primary_example": "Основная фраза, например: вот это момент",
        "chat.variants": "Варианты — по одному на строке",
        "chat.commit": "Добавить / обновить группу",
        "chat.check_label": "Проверить сообщение на текущем списке",
        "chat.check": "Проверить",
        "chat.feedback.updated": "Группа обновлена. Нажмите «Сохранить и применить», чтобы включить изменения.",
        "chat.feedback.deleted": "Группа удалена из списка. Сохраните изменения.",
        "chat.feedback.match": "Совпадение с группой: {label}",
        "chat.feedback.no_match": "Совпадений с вашими включёнными фразами нет.",
        "chat.feedback.saved": "Сохранено. Во время записи список обновится в течение следующего тика (~1 с).",
        "chat.notify.saved": "Фразы чата сохранены — будут учтены как реакции зрителей.\n",
        "chat.close_prompt": "Сохранить изменения перед закрытием?",
        "chat.error.enabled": "Настройки чата должны содержать переключатель enabled",
        "chat.error.groups": "Можно добавить не более {count} групп фраз",
        "chat.error.primary": "У каждой группы должна быть основная фраза",
        "chat.error.variants": "У фразы может быть не более {count} вариантов",
        "chat.error.length": "Фраза и каждый вариант: от 1 до {count} символов",
        "chat.error.empty": "Фраза не может быть пустой",
        "chat.error.duplicate": "Фраза уже добавлена как фраза или вариант: {value}",
        "chat.error.file_large": "Слишком большой файл настроек чата",
        "chat.error.text_large": "Слишком много текста в настройках чата",
        "main.trigger.plain": "активность",
        "main.trigger.laugh": "смех",
        "main.trigger.react": "реакции",
        "main.trigger.vol": "громкость",
        "main.trigger.escalation": "эскалация, сокращённая пауза",
        "main.trigger.normal": "обычный триггер",
    },
    "en": {
        "language": "Language",
        "window.title": f"Twitchautoclipper {__version__} — recording and editing",
        "status.stopped": "Stopped",
        "status.starting": "Started — connecting to Twitch…",
        "status.recording": "Recording — waiting for interesting moments",
        "status.ready": "New clip ready — ready folder",
        "status.fatal": "Startup error — see the log for details",
        "status.stopping": "Stopping recording and FFmpeg…",
        "status.exit_error": "Error: code {code}. See the log.",
        "label.channels": "Channels:",
        "hint.channels": "Usernames separated by commas, e.g. example_channel, another_channel",
        "label.data_folder": "Data folder:",
        "button.browse": "Browse…",
        "dialog.data_folder": "Folder for the buffer, clips, and music",
        "check.subtitles": "Subtitles (requires a faster-whisper build)",
        "label.video_shift": "Video window offset from chat, sec:",
        "label.thresholds": "Thresholds: overall",
        "label.chat": "chat",
        "label.cooldown": "cooldown, sec",
        "hint.lower_more": "Lower = more often",
        "button.start": "Start",
        "button.stop": "Stop",
        "button.open_ready": "Open finished clips",
        "button.chat_phrases": "Chat phrases…",
        "dialog.chat_phrases": "Chat phrases",
        "dialog.start_error": "Could not start",
        "dialog.ready_folder": "Clips folder",
        "dialog.language_save": "Could not save the language",
        "dialog.exit": "Exit",
        "dialog.exit_prompt": "Stop recording and close the program? The unfinished montage may be interrupted.",
        "log.setup": "Editing: choose a banner/music and select the webcam in a frame. Areas can be changed while recording.\n",
        "log.path": "\nLog: {path}\n",
        "log.process_exit": "\nProcess finished, code {code}.\n",
        "log.error": "Log error: {error}\n",
        "error.channel": "Invalid Twitch username: {channel}",
        "error.channel_required": "Enter at least one channel",
        "error.delay": "The offset must be between -60 and 60 seconds",
        "error.threshold": "Thresholds must be between 0.1 and 8",
        "error.cooldown": "The cooldown must be between 1 and 600 seconds",
        "render.frame_title": "Editing — without streamer name",
        "render.banner": "Banner:",
        "render.music": "Music:",
        "render.file": "File…",
        "render.remove": "Remove",
        "render.track": "Track…",
        "render.folder": "Folder…",
        "render.split_camera": "Webcam on top, main frame below (empty paths = no banner/music)",
        "render.camera": "Webcam",
        "render.content": "Main frame",
        "render.frame_from_buffer": "Frame from buffer",
        "render.frame_from_file": "From file…",
        "render.reset_roi": "Reset area",
        "render.apply": "Apply editing",
        "render.banner_position": "Place 9:16 banner…",
        "render.variation": "Processing: mirror video, soft color, camera 102–106%",
        "render.random_fps": "Random FPS: source ±0.1–2 (speed unchanged)",
        "render.metadata": "Metadata: CapCut",
        "render.random_metadata": "Random descriptive metadata and MP4 name",
        "render.info.empty": "Select the webcam in a frame for each channel",
        "render.info.roi": "{channel} / {kind}: x={x:.1f}%, y={y:.1f}%, width={width:.1f}%, height={height:.1f}%",
        "render.info.default": "{channel} / {kind}: not set; the whole frame is used by default",
        "render.dialog.banner_file": "Banner on green screen",
        "render.dialog.music_file": "Background music",
        "render.dialog.music_folder": "Music folder",
        "render.dialog.frame_file": "Stream frame: video or image",
        "render.dialog.frame": "Frame",
        "render.dialog.area": "Area",
        "render.dialog.buffer": "Buffer",
        "render.dialog.save": "Save",
        "render.dialog.draw_area": "Draw the required area with the mouse",
        "render.dialog.start_channel": "Enter a channel first",
        "render.dialog.wait_buffer": "Start recording and wait 15–30 seconds, then try again.",
        "render.info.getting_frame": "Getting a frame…",
        "render.selection_title": "{channel}: select the {kind} with the mouse",
        "render.save_area": "Save area",
        "render.banner_title": "{channel}: banner position in the finished video",
        "render.banner_help": "Size: drag the handles at the corners or sides of the frame.\nMove: drag inside. New area: Shift + mouse.\nThe banner aspect ratio is preserved.",
        "render.banner_label": "Banner",
        "render.banner_dimensions": "x={x:.0f}, y={y:.0f}; area {width:.0f}×{height:.0f}",
        "render.banner_reset_info": "The default banner size and position will be restored",
        "render.reset": "Reset",
        "render.save_position": "Save position",
        "render.notify_saved": "Editing settings saved — they will apply to the next jobs.\n",
        "render.notify_roi": "The {kind} area for {channel} was saved.\n",
        "render.notify_banner": "The banner position for {channel} was saved.\n",
        "render.error.path": "{label}: path not found: {value}",
        "render.error.banner_file": "The banner must be a file",
        "chat.title": "Chat signals — phrases and variants",
        "chat.title_short": "Chat phrases",
        "chat.header": "Custom viewer reactions",
        "chat.enabled": "Use my phrases as interesting-moment signals",
        "chat.feedback.initial": "Add a phrase and its variants.",
        "chat.explanation": "A match boosts chat reactions but does not create a clip by itself.\nCase does not matter; variants are entered explicitly, without regular expressions.",
        "chat.save": "Save and apply",
        "chat.close": "Close",
        "chat.groups": "Phrase groups",
        "chat.primary": "Primary phrase",
        "chat.new": "New",
        "chat.delete": "Delete",
        "chat.primary_example": "Primary phrase, for example: this is the moment",
        "chat.variants": "Variants — one per line",
        "chat.commit": "Add / update group",
        "chat.check_label": "Check a message against the current list",
        "chat.check": "Check",
        "chat.feedback.updated": "Group updated. Click “Save and apply” to enable the changes.",
        "chat.feedback.deleted": "The group was removed. Save the changes.",
        "chat.feedback.match": "Matched group: {label}",
        "chat.feedback.no_match": "No matches for your enabled phrases.",
        "chat.feedback.saved": "Saved. The list will refresh during the next tick (~1 sec) while recording.",
        "chat.notify.saved": "Chat phrases saved — they will be used as viewer reactions.\n",
        "chat.close_prompt": "Save changes before closing?",
        "chat.error.enabled": "Chat settings must contain the enabled switch",
        "chat.error.groups": "You can add no more than {count} phrase groups",
        "chat.error.primary": "Each group must have a primary phrase",
        "chat.error.variants": "A phrase can have no more than {count} variants",
        "chat.error.length": "The phrase and each variant must be 1–{count} characters",
        "chat.error.empty": "The phrase cannot be empty",
        "chat.error.duplicate": "The phrase is already added as a phrase or variant: {value}",
        "chat.error.file_large": "The chat settings file is too large",
        "chat.error.text_large": "There is too much text in the chat settings",
        "main.trigger.plain": "activity",
        "main.trigger.laugh": "laughter",
        "main.trigger.react": "reactions",
        "main.trigger.vol": "volume",
        "main.trigger.escalation": "escalation, shorter cooldown",
        "main.trigger.normal": "normal trigger",
    },
}


class I18n:
    """Translation state shared by the main window and its child panels."""

    def __init__(self, language="ru"):
        self._language = language if language in LANGUAGES else "ru"
        self._listeners = []
        self._variable_bindings = {}

    @property
    def language(self):
        return self._language

    def t(self, key, **values):
        text = _STRINGS[self._language].get(key, _STRINGS["ru"].get(key, key))
        return text.format(**values) if values else text

    def language_names(self):
        return tuple(LANGUAGE_NAMES[language] for language in LANGUAGES)

    def subscribe(self, listener):
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def bind_text(self, widget, key, **values):
        self._bind_widget(widget, key, values, title=False)

    def bind_title(self, window, key, **values):
        self._bind_widget(window, key, values, title=True)

    def _bind_widget(self, widget, key, values, title):
        reference = weakref.ref(widget)

        def update():
            target = reference()
            if target is None:
                self.unsubscribe(update)
                return
            try:
                if not target.winfo_exists():
                    self.unsubscribe(update)
                    return
                text = self.t(key, **values)
                if title:
                    target.title(text)
                else:
                    target.configure(text=text)
            except Exception as error:
                # Closing a Tk child destroys its Tcl command before its Python
                # object disappears. Do not let that block other translations.
                if type(error).__name__ != "TclError":
                    raise
                self.unsubscribe(update)

        update()
        self.subscribe(update)

    def bind_variable(self, variable, key, **values):
        identifier = id(variable)
        binding = self._variable_bindings.get(identifier)
        if binding is None or binding["reference"]() is not variable:
            binding = {"reference": weakref.ref(variable), "key": key, "values": values}
            self._variable_bindings[identifier] = binding

            def update():
                target = binding["reference"]()
                if target is None:
                    self.unsubscribe(update)
                    self._variable_bindings.pop(identifier, None)
                    return
                try:
                    target.set(self.t(binding["key"], **binding["values"]))
                except Exception as error:
                    if type(error).__name__ != "TclError":
                        raise
                    self.unsubscribe(update)
                    self._variable_bindings.pop(identifier, None)

            binding["update"] = update
            self.subscribe(update)
        binding.update(key=key, values=values)
        binding["update"]()

    def set_language(self, language):
        if language not in LANGUAGES or language == self._language:
            return
        self._language = language
        for listener in tuple(self._listeners):
            listener()

    def error(self, message):
        """Translate validation errors that are produced by the data layer."""
        if self._language == "ru":
            return message
        exact = {
            "Настройки чата должны содержать переключатель enabled": "chat.error.enabled",
            "У каждой группы должна быть основная фраза": "chat.error.primary",
            "Фраза не может быть пустой": "chat.error.empty",
            "Слишком большой файл настроек чата": "chat.error.file_large",
            "Слишком много текста в настройках чата": "chat.error.text_large",
        }
        if message in exact:
            return self.t(exact[message])
        patterns = (
            (r"^Можно добавить не более (\d+) групп фраз$", "chat.error.groups"),
            (r"^У фразы может быть не более (\d+) вариантов$", "chat.error.variants"),
            (r"^Фраза и каждый вариант: от 1 до (\d+) символов$", "chat.error.length"),
            (r"^Фраза уже добавлена как фраза или вариант: (.*)$", "chat.error.duplicate"),
        )
        for pattern, key in patterns:
            match = re.match(pattern, message)
            if match:
                value = match.group(1)
                return self.t(key, count=value, value=value)
        return message


__all__ = ["I18n", "LANGUAGES", "LANGUAGE_NAMES"]
