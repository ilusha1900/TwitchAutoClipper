# Changelog / История изменений

## v4 (updates after the original v4 delivery)

### Added
- Editing panel: banner, music track or folder, webcam and main-frame areas per channel.
- Banner placement editor (draw, drag, resize with eight handles, per-channel save and reset).
- Video processing switch: mirroring, small random brightness/contrast/saturation, camera zoom 102–106%.
- Random FPS switch: source ±0.1–2 FPS, constant within a clip. Without it, the source FPS is preserved instead of a fixed 30 FPS.
- MP4 metadata: `encoder`, `encoding_tool`, `producer` set to CapCut; optional random descriptive metadata and file name.
- Custom chat phrases editor with spelling variants and a built-in tester (`chat.json`, hot reload about once per second, `--chat-config` / `CLIP_CHAT_CONFIG`).
- Detailed `TRIGGER` log line with the reason for each clip; snapshot saved in the JSON next to the clip.
- `Roma.bat` / `roma_setup.py` installer: local `.venv`, NumPy, Streamlink, Tkinter check, static FFmpeg download, backup of a broken environment as `.venv.backup_DATE`.
- `TwitchClipper.exe` launcher (opens the source code through `start.cmd` and the existing `.venv`).

### Changed
- The nickname that the program used to add to clips has been removed.
- FFmpeg errors now include the tail of stderr, not only the command and exit code.
- Output FPS of fractional HLS rates with very large denominators is normalized to thousandths.

### Fixed
- **FFmpeg 9.0.2 compatibility**: removed the `-vsync cfr` option (error `Unrecognized option 'vsync'`, Windows code 2880417800). Constant FPS is now set by the `fps` filter after compositing. Tested on FFmpeg 4.4.2 and 9.0.2.
- **Subtitles**: fixed `open() got an unexpected keyword argument 'metadata_errors'` in the faster-whisper/PyAV path. FFmpeg now extracts mono 16 kHz PCM WAV, which is passed to the recognizer as a float32 array.
  To apply the fixes, replace `montage.py` in the folder that is actually launched.

---

## v4 — Русская версия (кратко)

### Добавлено
- Панель монтажа: баннер, музыка (файл или папка), области вебкамеры и основного кадра для каждого канала.
- Редактор положения баннера (рисование, перетаскивание, восемь маркеров, сохранение и сброс по каналам).
- Переключатель обработки: зеркало, небольшая случайная яркость/контраст/насыщенность, увеличение камеры 102–106%.
- Случайный FPS: исходный ±0,1–2 кадра/с, постоянный внутри клипа. При выключении сохраняется FPS исходника, а не жёсткие 30.
- Метаданные MP4: `encoder`, `encoding_tool`, `producer` = CapCut; опциональные случайные описательные метаданные и имя файла.
- Редактор своих фраз чата с вариантами написания и встроенной проверкой (`chat.json`, перечитывание примерно раз в секунду, `--chat-config` / `CLIP_CHAT_CONFIG`).
- Подробная строка `TRIGGER` с причиной каждого клипа; снимок сохраняется в JSON рядом с клипом.
- Установщик `Roma.bat` / `roma_setup.py`: локальное `.venv`, NumPy, Streamlink, проверка Tkinter, загрузка статического FFmpeg, резервная копия неработающего окружения `.venv.backup_ДАТА`.
- Запускатель `TwitchClipper.exe` (открывает исходники через `start.cmd` и существующее `.venv`).

### Изменено
- Ник, который программа раньше добавляла в клипы, удалён.
- В ошибки FFmpeg теперь включается конец stderr, а не только команда и код выхода.
- Выходной FPS для дробных частот HLS с очень большим знаменателем нормализуется до тысячных.

### Исправлено
- **Совместимость с FFmpeg 9.0.2**: удалён параметр `-vsync cfr` (ошибка `Unrecognized option 'vsync'`, код Windows 2880417800). Постоянный FPS теперь задаёт фильтр `fps` после композиции. Проверено на FFmpeg 4.4.2 и 9.0.2.
- **Субтитры**: исправлена ошибка `open() got an unexpected keyword argument 'metadata_errors'` на пути faster-whisper/PyAV. FFmpeg теперь извлекает mono PCM WAV 16 кГц, который передаётся распознавателю как массив float32.
  Для применения исправлений замените `montage.py` в реально запускаемой папке.
