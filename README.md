# TwitchAutoClipper

### Support & Donations / Поддержать проект

If you find this tool useful, you can support its further development / Если инструмент оказался полезным, можно поддержать разработку:

- **USDT (TRC-20 / Tron):** `TJ8DBf6bGLS99zCGTUD9pkDFQWc7vkRDdd`
- **USDT (BEP-20 / BNB Smart Chain):** `0x123B2cBba8790fa7977681740eDdf16Cd526CF52`

### Contact & Custom Features / Связь и доработки

- **Discord:** `wq4` — for custom features, paid modifications, commercial licensing, or business inquiries.
- **Discord:** `wq4` — по вопросам кастомных фич, платных доработок, коммерческой лицензии и сотрудничества.

**English** | [Русский](#русский)

<!-- Add a screenshot of the window or an example clip / Добавьте скриншот окна или пример клипа:
![screenshot](docs/screenshot.png) -->

---

## English

Automatically turns Twitch stream highlights into vertical 9:16 clips.
The program records a rolling buffer of the stream, watches chat and audio for spikes, cuts the moment out and edits it into a ready-to-post vertical video.

### Features

- **Moment detection** from chat (laughter, reactions, activity) and audio loudness. Loudness alone never triggers a clip.
- **Custom chat phrases** with spelling variants, editable while recording.
- **Smart 9:16 layout**: webcam on top (640 px), main video below (1280 px) on a blurred background.
- **Banner and music**: overlay a banner (green-background video), random track from a folder, music ducked under the original sound, noise reduction, normalization.
- **Optional subtitles** via faster-whisper (off by default).
- **Video processing options**: mirroring, slight color shifts, camera zoom, random FPS, metadata settings (see below).
- **Russian and English UI.**
- No auto-publishing: finished clips are saved as MP4 + JSON next to each other.

### Requirements

- Windows 10/11 x64
- Python 3.11–3.13 x64 with pip and Tcl/Tk (Tkinter)
- Internet connection for the first run
- Runs on the CPU. GPU acceleration is not supported yet.

Other systems (Windows ARM64, 32-bit, Linux, macOS) are not guaranteed to work.

### Quick start

1. Download the latest archive from [Releases](../../releases) and extract it, for example to `C:\TwitchClipper`.
2. Run **`Roma.bat`** once. It checks Python, creates a local `.venv`, installs NumPy and Streamlink, and downloads FFmpeg/FFprobe into `bin` if they are not found.
   If the download is blocked, put `ffmpeg.exe` and `ffprobe.exe` into `bin` manually.
3. Start the program with **`TwitchClipper.exe`** (or `start.cmd`). Later launches do not reinstall anything.
4. Add a channel, set up the webcam area (below), and press **Start**.
5. Finished clips appear in the `ready` folder of the selected data folder.

Optional subtitles: `Roma.bat --subtitles` (the model is downloaded on first recognition).

> `TwitchClipper.exe` is a small launcher for the source code, not a standalone app. Do not move it out of the project folder.

### Setting up the layout

**Webcam area** (once per channel):
1. Select the channel and the area type "Webcam".
2. Press "From file…" and outline the webcam on a screenshot, or start recording, wait 15–30 seconds and press "Frame from buffer".
3. Press "Save area".

**Main frame area** (optional): select "Main frame" and outline the game part without the camera. Otherwise the whole stream is shown in the lower block, including the camera.

**Banner position**: select the channel, press "Place 9:16 banner…", draw or drag the frame on the mock-up, press "Save position".

Areas are stored relative to the frame, so they survive resolution changes. If the webcam moves on the stream, outline it again. Without a webcam area the program edits the whole frame and says so in the log.

### Tuning detection

| Setting | Default | Meaning |
|---|---|---|
| overall | 1.2 | threshold of the combined signal |
| chat | 4.0 | threshold of the chat signal |
| pause, s | 40 | minimum pause between clips |

Lower thresholds give more clips and more false positives. Change them while stopped, then start again. The "video offset" field (−60…+60 s) compensates for the delay between the stream and chat.

The `TRIGGER` line in the log shows exactly why a clip was made (score, chat category, unique chatters). The same snapshot is stored in the JSON file next to the clip.

### Custom chat phrases

Open "Chat phrases…", enter a main phrase and its spelling variants (one per line), press "Add / update group", then "Save and apply". You can test a message in the editor without connecting to Twitch.

- Case and repeated spaces are ignored; word boundaries are respected ("moment" does not match "momentik").
- Punctuation and spelling variants must be added explicitly. There is no fuzzy matching.
- Limits: 200 groups, 30 variants per group, 160 characters per phrase.
- Saved in `%LOCALAPPDATA%\TwitchClipper\chat.json`, applied to all channels, re-read about once per second.

Custom phrases supplement the built-in reactions. They do not bypass the detector thresholds, bot protection or the pause between clips.

### Video processing options

All of these can be switched on or off in the editing panel:

- **Processing** (on by default): mirrors the video, applies a small random brightness (±0.012), contrast (0.98–1.02), saturation (0.97–1.03) and camera zoom (102–106%) per clip.
- **Random FPS** (on by default): source FPS ±0.1–2, constant within a clip, no change of speed.
- **Metadata**: `encoder`, `encoding_tool` and `producer` tags are set to "CapCut". Rendering is still done by FFmpeg/libx264, so this does not prove the origin of the clip. Optional random title, author, album, date and file name.

These options do not guarantee that any platform will treat the content as unique.

### Files and folders

| Where | What |
|---|---|
| `ready` | finished MP4 and JSON |
| `buf` | rolling stream buffer |
| `clips` | raw clips waiting for editing (queue limit: 8) |
| `failed` | up to 10 raw clips whose editing failed |
| `logs` | logs |
| `%LOCALAPPDATA%\TwitchClipper\settings.json` | launch settings |
| `%LOCALAPPDATA%\TwitchClipper\render.json` | material paths and areas |

Finished clips and settings are never deleted automatically.

### Updating

Stop the program, extract the new archive over the existing folder (replace files) and do not delete `.venv`, the buffer or your clips. Run `Roma.bat` again only if `requirements.txt` changed. See [CHANGELOG.md](CHANGELOG.md).

### Known limitations

- No automatic webcam detection: you outline the area yourself.
- Text already embedded in the stream is not removed (and is mirrored when processing is on).
- English-language chats are not tested well. Please open an issue if detection works badly.
- The Tkinter interface and the live Twitch connection could not be tested in the automated test environment.

### Legal

Use streams, music and promotional materials only if you have the necessary permissions. You are responsible for following the rules of Twitch and of the platforms where you publish clips.

Licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE): free for personal and other noncommercial use. Commercial use requires a separate license from the author (Discord: `wq4`).

---

## Русский

[English](#english) | **Русский**

Автоматически превращает лучшие моменты стримов Twitch в вертикальные клипы 9:16.
Программа пишет скользящий буфер стрима, следит за чатом и звуком, вырезает момент и монтирует из него готовое вертикальное видео.

### Возможности

- **Поиск моментов** по чату (смех, реакции, активность) и громкости звука. Одна только громкость клип не запускает.
- **Свои фразы чата** с вариантами написания; можно менять прямо во время записи.
- **Раскладка 9:16**: вебкамера сверху (640 px), основной кадр снизу (1280 px) на размытой подложке.
- **Баннер и музыка**: баннер (видео на зелёном фоне), случайный трек из папки, приглушение музыки под оригинальный звук, шумоподавление, нормализация.
- **Субтитры** через faster-whisper (по умолчанию выключены).
- **Опции обработки видео**: зеркало, лёгкая коррекция цвета, увеличение камеры, случайный FPS, настройки метаданных (см. ниже).
- **Интерфейс на русском и английском.**
- Автопубликации нет: готовые клипы сохраняются в виде MP4 + JSON рядом друг с другом.

### Требования

- Windows 10/11 x64
- Python 3.11–3.13 x64 с pip и Tcl/Tk (Tkinter)
- Интернет при первом запуске
- Работает на процессоре. Поддержки видеокарт пока нет.

Другие системы (Windows ARM64, 32-бит, Linux, macOS) не гарантируются.

### Быстрый старт

1. Скачайте свежий архив в разделе [Releases](../../releases) и распакуйте, например, в `C:\TwitchClipper`.
2. Один раз запустите **`Roma.bat`**. Он проверит Python, создаст локальное `.venv`, установит NumPy и Streamlink и скачает FFmpeg/FFprobe в `bin`, если их нет.
   Если скачивание заблокировано, положите `ffmpeg.exe` и `ffprobe.exe` в `bin` вручную.
3. Запускайте **`TwitchClipper.exe`** (или `start.cmd`). При следующих запусках ничего заново не устанавливается.
4. Добавьте канал, настройте область вебкамеры (ниже) и нажмите **«Запустить»**.
5. Готовые клипы появятся в папке `ready` выбранной папки данных.

Необязательные субтитры: `Roma.bat --subtitles` (модель скачается при первом распознавании).

> `TwitchClipper.exe` — небольшой запускатель исходников, а не автономное приложение. Не переносите его отдельно от папки проекта.

### Настройка раскладки

**Область вебкамеры** (один раз для каждого канала):
1. Выберите канал и тип области «Вебкамера».
2. Нажмите «Из файла…» и обведите камеру на скриншоте либо запустите запись, подождите 15–30 секунд и нажмите «Кадр из буфера».
3. Нажмите «Сохранить область».

**Область основного кадра** (необязательно): выберите «Основной кадр» и обведите игровую часть без камеры. Иначе внизу будет весь стрим, вместе с камерой.

**Положение баннера**: выберите канал, нажмите «Разместить баннер 9:16…», нарисуйте или перетащите рамку на макете, нажмите «Сохранить положение».

Области хранятся в относительных координатах, поэтому работают при смене разрешения. Если камера на стриме переехала, выделите её заново. Без области вебкамеры программа монтирует весь кадр и сообщает об этом в логе.

### Настройка срабатывания

| Параметр | По умолчанию | Смысл |
|---|---|---|
| общий | 1.2 | порог суммарного сигнала |
| чат | 4.0 | порог сигнала чата |
| пауза, с | 40 | минимальная пауза между клипами |

Меньшие пороги дают больше клипов и больше ложных срабатываний. Менять их нужно после остановки, затем запускать запись снова. Поле «сдвиг видео» (−60…+60 с) компенсирует задержку между стримом и чатом.

Строка `TRIGGER` в логе показывает, почему создан клип (score, категория чата, число уникальных чаттеров). Тот же снимок сохраняется в JSON рядом с клипом.

### Свои фразы чата

Откройте «Фразы чата…», введите основную фразу и варианты написания (по одному на строку), нажмите «Добавить / обновить группу», затем «Сохранить и применить». Сообщение можно проверить прямо в редакторе, не подключаясь к Twitch.

- Регистр и повторные пробелы не учитываются; границы слов учитываются («момент» не совпадает с «моментик»).
- Варианты пунктуации и написания нужно добавлять явно, нечёткого поиска нет.
- Лимиты: 200 групп, 30 вариантов в группе, 160 символов на фразу.
- Хранятся в `%LOCALAPPDATA%\TwitchClipper\chat.json`, действуют на все каналы, перечитываются примерно раз в секунду.

Свои фразы дополняют встроенные реакции. Они не обходят пороги детектора, защиту от ботов и паузу между клипами.

### Опции обработки видео

Все они включаются и выключаются в панели монтажа:

- **Обработка** (включена по умолчанию): зеркало, небольшая случайная яркость (±0.012), контраст (0.98–1.02), насыщенность (0.97–1.03) и увеличение камеры (102–106%) для каждого клипа.
- **Случайный FPS** (включён по умолчанию): исходный ±0,1–2, постоянный внутри клипа, скорость не меняется.
- **Метаданные**: поля `encoder`, `encoding_tool` и `producer` получают значение «CapCut». Монтаж по-прежнему выполняет FFmpeg/libx264, так что это не доказывает происхождение ролика. Дополнительно можно включить случайные название, автора, альбом, дату и имя файла.

Эти опции не гарантируют, что какая-либо платформа сочтёт контент уникальным.

### Файлы и папки

| Где | Что |
|---|---|
| `ready` | готовые MP4 и JSON |
| `buf` | скользящий буфер стрима |
| `clips` | сырые клипы в ожидании монтажа (очередь до 8) |
| `failed` | до 10 сырых клипов, монтаж которых не удался |
| `logs` | журналы |
| `%LOCALAPPDATA%\TwitchClipper\settings.json` | настройки запуска |
| `%LOCALAPPDATA%\TwitchClipper\render.json` | пути материалов и области кадра |

Готовые клипы и настройки автоматически не удаляются.

### Обновление

Остановите программу, распакуйте новый архив поверх существующей папки с заменой файлов, не удаляя `.venv`, буфер и клипы. `Roma.bat` нужно запускать заново, только если обновился `requirements.txt`. Что изменилось — в [CHANGELOG.md](CHANGELOG.md).

### Известные ограничения

- Вебкамера не определяется автоматически: область задаёте вы сами.
- Текст, уже встроенный в стрим, не удаляется (а при включённой обработке зеркалится вместе с видео).
- Англоязычные чаты проверены слабо. Если срабатывание работает плохо, создайте issue.
- Интерфейс Tkinter и живое подключение к Twitch в автоматической тестовой среде не проверялись.

### Правовая информация

Используйте трансляции, музыку и рекламные материалы только при наличии необходимых разрешений. Соблюдать правила Twitch и площадок, где вы публикуете клипы, нужно самостоятельно.

Лицензия: [PolyForm Noncommercial 1.0.0](LICENSE): бесплатно для личного и другого некоммерческого использования. Для коммерческого использования нужна отдельная лицензия от автора (Discord: `wq4`).
