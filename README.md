# Twitchautoclipper v4

**English** | [Русский](#twitchautoclipper-v4--русская-версия)

> Note: Chat & Audio spike detection, Smart 9:16 Webcam + Gameplay layout, Anti-detect video uniqueizer + CapCut metadata spoofing Full English & Russian UI supported. It might not work well with English-language chats. I haven’t tested it. Runs on the user's PC using the processor. Support for graphics cards has not yet been added.

## First run via Roma.bat

On a new computer, run `Roma.bat`. `roma_setup.py` and the rest of the project files must be located next to it. The batch file checks for Python 3.11–3.13 x64, creates a local `.venv`, installs NumPy and Streamlink, checks Tkinter, and then downloads static FFmpeg/FFprobe builds into `bin` if working copies are not found. Administrator rights are usually not required; you need an internet connection, a writable folder, and a pre-installed Python with pip and Tcl/Tk. If Python is missing, the batch file stops and shows the official download link. Windows 10/11 x64 is supported; support for arbitrary PCs, Windows ARM64, 32-bit systems, and other operating systems is not guaranteed.

If FFmpeg is missing, it is downloaded over HTTPS from the Gyan.dev Windows x64 "essentials" build. If the download is blocked, place static `ffmpeg.exe` and `ffprobe.exe` into `bin` manually. Before using them, make sure that downloading these programs is permitted in your environment. After installation, the libraries, Tkinter startup, the FFmpeg executables, and the required editing filters are verified. If anything fails, the window stays open with the error and the program does not start.

To move to another computer, copy the entire project folder, but not `.venv`: it is created in place by `Roma.bat`. If a copied environment does not work, it is kept as `.venv.backup_DATE` and a new one is created in its place. Videos and user settings are not deleted. After the first run you can use `TwitchClipper.exe` or `start.cmd`: they use the prepared `.venv` and do not reinstall packages. `Roma.bat` can be run again after `requirements.txt` is updated. To install the optional subtitles, run `Roma.bat --subtitles`; faster-whisper downloads its model separately on first recognition.

## Updating and launching

Stop the program. Extract the archive over the existing `C:\TwitchClipper` folder, replacing files. Do not delete your `.venv`, buffer, or clips. For the first launch on a new computer, use `Roma.bat`; for regular launches, use `TwitchClipper.exe`. The EXE opens the program through `start.cmd` and the existing `.venv`: during a regular launch there are no library installations, no PowerShell, and no tests. This update requires no new third-party Python libraries.

The EXE remains a small Windows x64 launcher for the source code, not a standalone application. It must not be moved separately from the project. If `.venv` is missing, `start.cmd` tries the installed Python; it must have NumPy, Streamlink, and standard Tkinter. FFmpeg/FFprobe must be in `bin` next to the project or in PATH. For subtitles, faster-whisper is installed separately; subtitles are off by default.

## Editing and webcam setup

An editing panel has been added to the window. Specify a banner file and a music track, or a music folder. An empty path disables the corresponding material. The banner is designed for video with a green background. A random track is chosen from the music folder; a single selected file is used directly. To apply the paths, click "Apply editing" or "Start".

Select a channel and the "Webcam" area type. You can click "From file…", open a video or a stream screenshot, and outline the webcam with the mouse. Alternatively, start recording first, wait 15–30 seconds, and click "Frame from buffer". After selecting the area, click "Save area". This needs to be done once per channel; settings are stored separately for each channel.

When the area is configured, the webcam occupies the top 640 pixels of the vertical frame, and the bottom 1280 pixels hold the main video. The webcam is shown without stretching; when processing is enabled, its edges are slightly cropped for a 102–106% zoom, and black bars are added if necessary. The main frame keeps its proportions and is shown in full on a blurred background. By default, the banner is placed at the top edge of the lower block; its position can be changed. The nickname that the program used to add has been removed. Text already embedded in the original stream is not removed automatically.

To prevent the webcam from being duplicated in the lower block, select the "Main frame" area type and outline the game/main part of the stream without the camera. If this area is not set, the entire original stream appears below. The settings are relative, so the same layout works when the resolution changes. If the webcam position in the broadcast changes, outline it again.

You can change editing and area parameters while recording. They are applied to jobs whose editing has not yet started. If the webcam has not been outlined, the program does not guess its position: it temporarily edits the whole frame without the nickname and reports this in the log. Unchecking "Webcam on top" also enables this mode.

## Banner position and video processing

Select a channel and click "Place 9:16 banner…". On the mock-up of the finished vertical frame, outline the banner's location with the mouse; an existing frame can be dragged. To resize it, drag any of the eight handles at the corners or sides of the frame; inside the frame, you can move it as a whole. The cursor indicates the resize direction. The frame cannot leave the bounds of the picture and cannot collapse. A new area can also be selected outside the frame or while holding Shift. Click "Save position". The banner is fitted centered into the selected area without stretching; position and size are saved separately for each channel. "Reset" followed by "Save position" restores the default placement. An empty banner path still disables it.

The "Processing: video mirror, soft color, camera 102–106%" switch is on by default. For each clip, the following are chosen independently: camera zoom from 102 to 106%, brightness from −0.012 to +0.012, contrast from 0.98 to 1.02, and saturation from 0.97 to 1.03. Values are constant throughout the clip, with no jumps. The camera video and the main frame are mirrored after the source areas are cut out; the camera zoom is done by center-cropping its edges. If a separate camera is not set or is disabled, there is no camera zoom. The banner is overlaid after processing: its orientation and color do not change, and added subtitles are not mirrored either. Text already embedded in the source video is mirrored along with it. Processing does not guarantee that any platform will consider the content unique.

To apply the switch, click "Apply editing" or "Start". The settings apply to jobs whose editing has not yet started. The selected effects and areas are written to the `render` field of the JSON file next to the finished clip. No new libraries or rebuild of the existing EXE launcher are needed: just restart the program.

## Random FPS and CapCut metadata

The editing panel has a "Random FPS: source ±0.1–2" switch enabled. For each new clip, the frame rate of the source video is determined and a single deviation is chosen, from −2 to −0.1 or from +0.1 to +2 frames per second, in steps of 0.1. For example, a source of 30 FPS may become 28.7 or 31.4 FPS. The rate is constant within a single clip; it does not have to be unique among all previous exports. There is no speeding up or slowing down of the video or audio: FFmpeg duplicates/drops frames on the same timeline. The duration may be off by rounding to a whole frame. If the switch is off, the source FPS is preserved instead of the previous hard-coded 30 FPS. If the source does not report a usable frame rate, a base of 30 FPS is used with a warning in the log.

For fractional average HLS frame rates with a very large denominator, the output FPS is normalized to thousandths so that the codec is not given an excessively fine time base. Rounding stays within the 0.1–2 deviation range; for such sources, an adjustment of up to 0.001 to the deviation step is possible. With variation disabled, such a rate is preserved to within 0.0005 FPS. Ordinary exact rates such as 30000/1001 are preserved without rounding.

Click "Apply editing" or "Start". The setting applies to the following jobs. The log shows the source and selected FPS; the JSON next to the clip stores `source_fps`, `output_fps`, `output_fps_ratio`, and `random_fps`.

In the metadata of new MP4 files, the `encoder`, `encoding_tool`, and `producer` fields are set to CapCut. This applies even when randomization of the other metadata is turned off. The "Random descriptive metadata and MP4 name" checkbox controls the random title, author, album, comment, date, track names, and file name, but not the CapCut signature. Source metadata and chapters are not copied. Technical parameters — codecs, resolution, duration — remain the actual ones.

FFmpeg overwrites the service `encoder` tag on its own. Therefore the program first exports an equal-length placeholder MP4 tag, then renames only that key to `encoder` inside the metadata table. MP4 atom sizes, media data, and offsets are not changed. Processing is still done by FFmpeg/libx264, not by the CapCut application; the signature does not prove the origin of the clip and does not remove all technical information from the video stream. Videos that are already finished are not rewritten.

## FFmpeg 9.0.2 compatibility fix

In the original version of these changes, the export used the `-vsync cfr` parameter. FFmpeg 9.0.2 no longer recognizes it: the error "Unrecognized option 'vsync'" was reproduced on this version. On Windows, the code 2880417800 from the log corresponds to AVERROR_OPTION_NOT_FOUND. The parameter has been removed; a constant FPS is now set by the `fps` filter after compositing, without changing the speed of the video and audio. FFmpeg 4.4.2 and 9.0.2 were tested. Error messages now include the tail of FFmpeg's stderr, not just the command and exit code.

A separate subtitle error, "open() got an unexpected keyword argument 'metadata_errors'", occurred on the re-decoding path through faster-whisper/PyAV. Now FFmpeg explicitly extracts mono 16 kHz PCM WAV, and the standard `wave` module and NumPy convert it into a float32 array that is passed to the recognizer directly. The incompatible PyAV call for opening this WAV is no longer needed. These changes do not require installing new libraries. Model recognition itself was not run in this test environment; passing the array was verified by an automated test.

Stop recording, close the program, and replace `montage.py` in the folder that is actually run with the file from `TwitchClipper_montage_hotfix.zip`. The new tests and the instructions in the archive are not needed for regular use. In the selected folder, `montage.py` is already fixed; if a different copy is launched, update it too. The EXE launcher and user settings do not need to be changed. Raw clips whose editing failed are still saved by the program to the `failed` data folders until they are pushed out by the limit of ten files; they are not re-edited automatically.

## Custom chat phrases and variants

Click "Chat phrases…" next to the launch buttons. In the separate window, enter a main phrase, for example "that's the moment", and spelling variants, one per line. Click "Add / update group" to add it to the list, then "Save and apply". The last unfinished group is also added on save. The "New" button starts a new group; selecting a row lets you edit an existing one, and "Delete" removes it. Changes take effect only after saving. When closing, the window offers to save unsaved changes.

At the bottom of the editor, you can test a message against the current list without connecting to Twitch. Matching ignores case and repeated spaces, takes Unicode normalization and word boundaries into account: "moment" does not match "momentik". A phrase may appear inside a longer message. Characters such as +, parentheses, or a period are treated literally, not as a regular expression. Punctuation and spelling variants must be added explicitly; there is no automatic fuzzy guessing. Up to 200 groups, up to 30 variants in each, and up to 160 characters per phrase/variant are allowed.

Custom phrases supplement the built-in reactions and are counted in the "reactions" category. They do not trigger a clip on every individual match: the detector thresholds, bot protection, per-user counting, and the pause between clips remain in effect. Laughter still takes priority if a message fits both categories. The switch in the editor disables only custom phrases, not the built-in reactions.

The list is saved in `%LOCALAPPDATA%\TwitchClipper\chat.json` and applies to all specified channels. It can be changed during recording: the worker process re-reads changes about once per second. If the file is corrupted, the last valid list is kept and a warning is shown. When launching directly through `main.py`, you can pass the path in the `CLIP_CHAT_CONFIG` variable; `launcher.py` has a `--chat-config` argument. The new modules `chat_settings.py` and `mp4_metadata.py` must stay next to the other source files. The existing EXE launcher does not need to be rebuilt.

## Trigger reasons

The TRIGGER line now states exactly which conditions were met: the overall score exceeded the threshold and/or a particular chat category (laughter, reactions, activity) reached its own threshold. The line also contains the weighted contribution of each component, the number of unique chatters, and whether it is a regular trigger or an escalation. A snapshot with the reason is saved in the JSON next to the finished MP4.

TRIGGER means the detector's decision to save a moment. The buffer is written continuously regardless of triggers. If the queue is full or there is a gap in the recording, the next message explicitly says that the clip was skipped.

## Thresholds, audio, and files

The "overall", "chat", and "pause, s" fields are saved at launch. The initial values are 1.2, 4.0, and 40 seconds. Lower thresholds produce more clips but increase false positives. These are thresholds of a normalized signal, not a number of messages. They should be changed after stopping, and then recording should be started again. With strong escalation, a repeat is allowed earlier than the cooldown, but not earlier than min(20, cooldown) seconds. Loudness alone without a positive chat signal does not trigger a clip.

HLS delivers audio in packets: an `age` of several seconds does not by itself mean the audio has dropped out. The analysis counts the maximum RMS loudness of new blocks between ticks once, without losing it on a subsequent quiet block. The detector's analysis does not change the audio track of the source recording. Editing applies noise reduction, music ducked under the original sound, and normalization.

The wall-clock alignment of video to chat is approximate. The video offset field, from −60 to +60 seconds, lets you tune the shift against the actual broadcast. A positive value selects a later part of the video.

Finished MP4 and JSON files are located in `ready` of the selected data folder; the buffer is in `buf`, pending raw clips are in `clips`, logs are in `logs`. There is no auto-publishing. Finished clips are not deleted automatically. The editing queue is limited to eight pending jobs. Up to ten failed raw clips are kept in `failed`.

Launch settings are in `%LOCALAPPDATA%\TwitchClipper\settings.json`. Material paths and frame areas are in `render.json` next to it. Recorded videos and these settings are not deleted when the project is updated.

## Tests

On Linux, 111 automated tests passed on FFmpeg 4.4.2 and again on FFmpeg 9.0.2; `smoke_test.py` with a real synthetic edit also passed on both versions. The syntax of all Python files was checked. In addition, the FPS parameters and the camera/banner layout from the error log, the absence of `-vsync`, the normalization of large FPS fractions, the recording of stderr, and the passing of the PCM array to the subtitle recognizer were checked. Also verified were source FPS values of 25, 30000/1001, and 60 with output values of 23, about 30.07003, and 62 FPS; duration and track synchronization; decoding of all frames and audio; the CapCut values in metadata; saving/updating of phrases; and the editor logic without a display. Pixel colors were used to verify cutting out of areas before mirroring, camera zoom, mirroring of the main video, banner position, and preservation of its orientation and color. Music, the 1080×1920 size, segment intervals, and the actual cutting were checked. The banner editor logic (selection, Shift selection, resizing with all eight handles, size and boundary limits, dragging, cursors, saving, and reset) was verified without a graphical display.

The Tkinter interface visually, the installer on a real Windows machine, and a live Twitch connection were not run in this environment. For the installer, the following were tested: backing up the old environment, reusing a working one, extracting only the two EXE files from the ZIP, cleaning up temporary files, and download errors; the network and Windows commands in these tests were replaced with mocks. The batch file was checked statically, including CRLF and label jumps. There is no automatic webcam detection: the area is set by the user. For reproducible checks, `test_detector.py`, `test_pipeline.py`, `test_render.py`, `test_setup.py`, `test_metadata.py`, `test_features.py`, `test_montage_compat.py`, and `smoke_test.py` are included; they are not run during regular launch. `TEST_RESULTS_v4.txt` and `SHA256SUMS_v4.txt` refer to the original v4 delivery, before these improvements.

Use streams, music, and promotional materials only if you have the necessary permissions.

---

# Twitchautoclipper v4 — Русская версия

[English](#twitchautoclipper-v4) | **Русский**

## Первый запуск через Roma.bat

Для нового компьютера запусти `Roma.bat`. Рядом должны находиться `roma_setup.py` и остальные файлы проекта. Батник проверит Python 3.11–3.13 x64, создаст локальное `.venv`, установит NumPy и Streamlink, проверит Tkinter и затем скачает статические FFmpeg/FFprobe в `bin`, если рабочие программы не найдены. Права администратора обычно не нужны; нужен интернет, папка с правом записи и заранее установленный Python с pip и Tcl/Tk. Если Python отсутствует, батник остановится и покажет официальную ссылку для установки. Поддерживаются Windows 10/11 x64; поддержка любого ПК, Windows ARM64, 32-битных систем и других ОС не гарантируется.

FFmpeg при отсутствии скачивается по HTTPS из Windows x64 essentials-сборки Gyan.dev. Если скачивание заблокировано, положи статические `ffmpeg.exe` и `ffprobe.exe` в `bin` вручную. Перед использованием проверь, что скачивание программ разрешено в твоей среде. После установки проверяются библиотеки, запуск Tkinter, исполняемые файлы FFmpeg и необходимые фильтры монтажа. При неудаче окно остаётся открытым с ошибкой; программа не запускается.

На другой компьютер переноси всю папку проекта, но не `.venv`: оно создаётся на месте через `Roma.bat`. Если перенесённое окружение не работает, оно сохраняется в `.venv.backup_ДАТА`, а вместо него создаётся новое. Видео и пользовательские настройки не удаляются. После первого запуска можно пользоваться `TwitchClipper.exe` или `start.cmd`: они используют подготовленное `.venv` и не устанавливают пакеты заново. `Roma.bat` можно запускать повторно после обновления `requirements.txt`. Для установки необязательных субтитров выполни `Roma.bat --subtitles`; faster-whisper скачивает модель отдельно при первом распознавании.

## Обновление и запуск

Остановите программу. Распакуйте архив поверх существующей папки C:\TwitchClipper с заменой файлов. Не удаляйте свою .venv, буфер или ролики. Для первого запуска нового компьютера используйте `Roma.bat`; для обычного запуска — `TwitchClipper.exe`. EXE открывает программу через start.cmd и существующую .venv: установки библиотек, PowerShell и тестов при обычном запуске нет. Новых сторонних Python-библиотек это обновление не требует.

EXE остаётся небольшим Windows x64 запускателем исходников, а не автономным приложением. Его нельзя переносить отдельно от проекта. Если .venv отсутствует, start.cmd пробует установленный Python; в нём должны быть NumPy, Streamlink и стандартный Tkinter. FFmpeg/FFprobe должны находиться в bin рядом с проектом либо в PATH. Для субтитров faster-whisper устанавливается отдельно; по умолчанию они выключены.

## Монтаж и настройка вебкамеры

В окне добавлена панель монтажа. Укажите файл баннера и трек либо папку с музыкой. Пустой путь отключает соответствующий материал. Баннер рассчитан на видео с зелёным фоном. Из папки музыки выбирается случайный трек; выбранный отдельный файл используется напрямую. Для применения путей нажмите «Применить монтаж» либо «Запустить».

Выберите канал и тип области «Вебкамера». Можно нажать «Из файла…», открыть видео или снимок стрима и мышью обвести вебкамеру. Либо сначала запустите запись, подождите 15–30 секунд и нажмите «Кадр из буфера». После выделения нажмите «Сохранить область». Это нужно сделать один раз для каждого канала; настройки сохраняются отдельно по каналам.

При настроенной области вебкамера занимает верхние 640 пикселей вертикального кадра, нижние 1280 — основной видеоряд. Вебкамера показывается без растяжения; при включённой обработке её края слегка обрезаются для увеличения 102–106%, при необходимости добавляются чёрные поля. Основной кадр сохраняет пропорции и показывается полностью на размытой подложке. По умолчанию баннер размещается у верхней границы нижнего блока; его положение можно изменить. Добавляемый программой ник удалён. Текст, уже встроенный в исходный стрим, автоматически не удаляется.

Чтобы вебкамера не дублировалась в нижнем блоке, выберите тип области «Основной кадр» и выделите игровую/основную часть стрима без камеры. Если эту область не задавать, снизу будет весь исходный стрим. Настройки относительные, поэтому одинаковое расположение работает при смене разрешения. Если расположение вебкамеры в трансляции изменится, выделите её заново.

Изменять параметры монтажа и области можно во время записи. Они применяются к заданиям, монтаж которых ещё не начался. Если вебкамера пока не выделена, программа не угадывает её положение: временно монтирует весь кадр без ника и сообщает об этом в логе. Снятая галочка «Вебкамера сверху» также включает этот режим.

## Положение баннера и обработка видео

Выберите канал и нажмите «Разместить баннер 9:16…». На макете готового вертикального кадра обведите место баннера мышью; существующую рамку можно перетаскивать. Для изменения размера потяните за любой из восьми маркеров на углах или сторонах рамки; внутри рамки можно перемещать её целиком. Курсор подсказывает направление изменения размера. Рамка не выходит за границы кадра и не может схлопнуться. Новую область также можно выделить вне рамки или с удержанием Shift. Нажмите «Сохранить положение». Баннер вписывается в выбранную область по центру без растяжения; положение и размер сохраняются отдельно для каждого канала. «Сбросить» и затем «Сохранить положение» возвращают стандартное размещение. Пустой путь баннера по-прежнему отключает его.

Переключатель «Обработка: зеркало видео, мягкий цвет, камера 102–106%» включён по умолчанию. Для каждого клипа независимо выбираются увеличение камеры от 102 до 106%, яркость от −0.012 до +0.012, контраст от 0.98 до 1.02 и насыщенность от 0.97 до 1.03. Значения постоянны на протяжении клипа, без скачков. Видео камеры и основного кадра зеркалится после вырезания исходных областей; увеличение камеры выполняется центральной обрезкой её краёв. Если отдельная камера не задана или выключена, увеличения камеры нет. Баннер накладывается после обработки: его ориентация и цвет не меняются, добавленные субтитры также не зеркалятся. Текст, уже встроенный в исходное видео, зеркалится вместе с ним. Обработка не гарантирует признание контента уникальным какой-либо платформой.

Для применения переключателя нажмите «Применить монтаж» либо «Запустить». Настройки действуют на задания, монтаж которых ещё не начался. Выбранные эффекты и области записываются в поле render JSON-файла рядом с готовым клипом. Новые библиотеки и пересборка существующего EXE-запускателя не нужны: перезапустите программу.

## Случайный FPS и метаданные CapCut

В панели монтажа включён переключатель «Случайный FPS: исходный ±0,1–2». Для каждого нового клипа определяется частота исходного видео и выбирается одно отклонение от −2 до −0,1 или от +0,1 до +2 кадра/с с шагом 0,1. Например, исходные 30 FPS могут превратиться в 28,7 или 31,4 FPS. Внутри одного клипа частота постоянная; она не обязана быть уникальной среди всех предыдущих экспортов. Ускорения/замедления видео или звука нет: FFmpeg добавляет/пропускает кадры на прежней временной шкале. Возможна погрешность длительности на округление до целого кадра. Если переключатель выключен, сохраняется FPS исходника, а не прежние жёсткие 30 FPS. Если исходник не сообщает пригодную частоту, используется база 30 FPS с предупреждением в логе.

Для дробных средних частот HLS с очень большим знаменателем выходной FPS нормализуется до тысячных, чтобы не задавать кодеку чрезмерно мелкую временную базу. Округление остаётся внутри диапазона отклонения 0,1–2; для таких исходников возможна поправка до 0,001 к шагу отклонения. При выключенной вариации такая частота сохраняется с точностью до 0,0005 FPS. Обычные точные частоты вроде 30000/1001 сохраняются без округления.

Нажмите «Применить монтаж» либо «Запустить». Настройка действует на следующие задания. В логе выводятся исходный и выбранный FPS; в JSON рядом с клипом сохраняются source_fps, output_fps, output_fps_ratio и random_fps.

В метаданных новых MP4 поля encoder, encoding_tool и producer имеют значение CapCut. Это действует и при выключенной рандомизации остальных метаданных. Галочка «Случайные описательные метаданные и имя MP4» управляет случайными названием, автором, альбомом, комментарием, датой, именами дорожек и именем файла, но не подписью CapCut. Исходные метаданные и главы не копируются. Технические параметры — кодеки, разрешение, длительность — остаются фактическими.

FFmpeg перезаписывает служебный encoder самостоятельно. Поэтому программа сначала экспортирует равный по длине резервный MP4-тег, затем меняет только имя этого ключа на encoder внутри таблицы метаданных. Размеры MP4-атомов, медиаданные и смещения не изменяются. Обработка по-прежнему выполняется FFmpeg/libx264, а не приложением CapCut; подпись не доказывает происхождение ролика и не удаляет все технические сведения из видеопотока. Уже готовые видео не переписываются.

## Исправление совместимости FFmpeg 9.0.2

В первоначальной версии этих изменений экспорт использовал параметр -vsync cfr. В FFmpeg 9.0.2 он больше не распознаётся: на этой версии воспроизведена ошибка «Unrecognized option 'vsync'». В Windows из журнала код 2880417800 соответствует AVERROR_OPTION_NOT_FOUND. Параметр удалён; постоянный FPS теперь задаётся фильтром fps после композиции, без изменения скорости видео и звука. Проверены FFmpeg 4.4.2 и 9.0.2. В сообщения ошибок теперь включается конец stderr FFmpeg, а не только команда и код выхода.

Отдельная ошибка субтитров «open() got an unexpected keyword argument 'metadata_errors'» возникала на пути повторного декодирования через faster-whisper/PyAV. Теперь FFmpeg явно извлекает mono PCM WAV 16 кГц, стандартный модуль wave и NumPy преобразуют его в float32-массив, который передаётся распознавателю напрямую. Несовместимый вызов PyAV для открытия этого WAV больше не нужен. Изменения не требуют установки новых библиотек. Само распознавание моделью в этой проверочной среде не запускалось; передача массива проверена автоматическим тестом.

Остановите запись, закройте программу и замените montage.py в реально запускаемой папке файлом из TwitchClipper_montage_hotfix.zip. Новые тесты и инструкция в архиве не нужны для обычного запуска. В выбранной папке montage.py уже исправлен; если запускается другая копия, обновите и её. EXE-запускатель и пользовательские настройки менять не нужно. Сырые клипы, монтаж которых не удался, программа по-прежнему сохраняет в failed папки данных, пока они не вытеснены ограничением в десять файлов; автоматически они не перемонтируются.

## Свои фразы и варианты в чате

Нажмите «Фразы чата…» рядом с кнопками запуска. В отдельном окне укажите основную фразу, например «вот это момент», и варианты написания — каждый на отдельной строке. Нажмите «Добавить / обновить группу», чтобы добавить её в список, затем «Сохранить и применить». Последняя незавершённая группа также добавляется при сохранении. Кнопка «Новая» начинает новую группу; выбор строки позволяет отредактировать существующую, «Удалить» убирает её. Изменения вступают в силу только после сохранения. При закрытии окно предлагает сохранить несохранённые изменения.

Внизу редактора можно проверить сообщение на текущем списке, не подключаясь к Twitch. Поиск не учитывает регистр и повторные пробелы, учитывает Unicode-нормализацию и границы слов: «момент» не совпадает с «моментик». Фраза может находиться внутри более длинного сообщения. Символы вроде +, скобок или точки трактуются буквально, не как регулярное выражение. Варианты пунктуации и написания нужно добавить явно; автоматического нечёткого угадывания нет. Допускаются до 200 групп, до 30 вариантов в каждой и до 160 символов на фразу/вариант.

Свои фразы дополняют встроенные реакции и учитываются в категории «реакции». Они не запускают клип при каждом отдельном совпадении: сохраняются пороги детектора, защита от ботов, учёт одного пользователя и пауза между клипами. Смех по-прежнему имеет приоритет, если сообщение подходит под обе категории. Переключатель в редакторе отключает только свои фразы, не встроенные реакции.

Список сохраняется в %LOCALAPPDATA%\\TwitchClipper\\chat.json и применяется ко всем указанным каналам. Его можно менять во время записи: рабочий процесс перечитывает изменения примерно раз в секунду. При повреждённом файле сохраняется последний корректный список и выводится предупреждение. Для запуска напрямую через main.py можно передать путь переменной CLIP_CHAT_CONFIG; у launcher.py есть аргумент --chat-config. Новые модули chat_settings.py и mp4_metadata.py должны оставаться рядом с остальными исходниками. Существующий EXE-запускатель пересобирать не нужно.

## Причины срабатывания

В строке TRIGGER теперь указано, какие именно условия выполнены: общий score превысил порог и/или определённая категория чата (смех, реакции, активность) достигла отдельного порога. Строка также содержит взвешенный вклад каждой компоненты, количества уникальных чаттеров и режим обычного триггера либо эскалации. Снимок с причиной сохраняется в JSON рядом с готовым MP4.

TRIGGER означает решение детектора сохранить момент. Буфер пишется непрерывно независимо от триггеров. Если очередь заполнена или в записи разрыв, следующее сообщение явно сообщает, что клип пропущен.

## Пороги, аудио и файлы

Поля «общий», «чат» и «пауза, с» сохраняются при запуске. Начальные значения: 1.2, 4.0 и 40 секунд. Меньшие пороги дают больше клипов, но увеличивают ложные срабатывания. Это пороги нормализованного сигнала, а не количество сообщений. Менять их нужно после остановки и затем запускать запись снова. При сильной эскалации повтор допускается раньше cooldown, но не раньше min(20, cooldown) секунд. Одна только громкость без положительного сигнала чата клип не запускает.

HLS передаёт аудио пакетами: age в несколько секунд само по себе не означает пропадание звука. Анализ учитывает максимальную RMS-громкость новых блоков между тиками один раз, не теряя её при последующем тихом блоке. Анализ детектора не меняет аудиодорожку исходной записи. Монтаж применяет шумоподавление, музыку с приглушением под исходный звук и нормализацию.

Wall-clock привязка видео к чату приблизительная. Поле сдвига видео от −60 до +60 секунд позволяет подобрать смещение по реальной трансляции. Положительное значение выбирает более поздний участок видео.

Готовые MP4 и JSON находятся в ready выбранной папки данных; буфер — buf, ожидающие сырые клипы — clips, журналы — logs. Автопубликации нет. Готовые ролики автоматически не удаляются. Очередь монтажа ограничена восемью ожидающими заданиями. В failed сохраняется до десяти неудачных сырых клипов.

Настройки запуска находятся в %LOCALAPPDATA%\TwitchClipper\settings.json. Пути материалов и области кадра — в render.json рядом с ним. Записанные видео и эти настройки при обновлении проекта не удаляются.

## Проверки

В Linux успешно выполнены 111 автоматических тестов на FFmpeg 4.4.2 и повторно на FFmpeg 9.0.2; на обеих версиях также прошёл smoke_test.py с реальным синтетическим монтажом. Проверен синтаксис всех Python-файлов. Дополнительно проверены параметры FPS и раскладка камеры/баннера из журнала ошибки, отсутствие -vsync, нормализация больших дробей FPS, запись stderr и передача PCM-массива в распознаватель субтитров. Дополнительно проверены FPS исходников 25, 30000/1001 и 60 с выходными значениями 23, около 30,07003 и 62 FPS, длительность и синхронность дорожек, декодирование всех кадров и звука, значения CapCut в метаданных, сохранение/обновление фраз и логика редактора без дисплея. По цветам пикселей проверены вырезание областей перед зеркалированием, увеличение камеры, зеркалирование основного видео, положение баннера и сохранение его ориентации и цвета. Проверены музыка, размер 1080×1920, интервалы сегментов и фактическая нарезка. Логика редактора баннера (выделение, Shift-выделение, изменение размера всеми восемью маркерами, ограничения размера и границ, перетаскивание, курсоры, сохранение и сброс) проверена без графического дисплея.

Tkinter-интерфейс визуально, установщик на настоящей Windows и живое Twitch-подключение в этой среде не запускались. Для установщика проверены резервирование старого окружения, переиспользование рабочего, извлечение только двух EXE из ZIP, очистка временных файлов и ошибки скачивания; сеть и Windows-команды в этих тестах заменены имитациями. Батник проверен статически, включая CRLF и переходы по меткам. Автоматического определения вебкамеры нет: область задаёт пользователь. Для воспроизводимых проверок приложены test_detector.py, test_pipeline.py, test_render.py, test_setup.py, test_metadata.py, test_features.py, test_montage_compat.py и smoke_test.py; при обычном запуске они не выполняются. TEST_RESULTS_v4.txt и SHA256SUMS_v4.txt относятся к исходной поставке v4, до этих доработок.

Используйте трансляции, музыку и рекламные материалы только при наличии необходимых разрешений.
