"""Windows first-run setup used by Roma.bat. Python is supplied by the user."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
MAX_DOWNLOAD = 512 * 1024 * 1024


def run(args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def check_platform():
    if sys.platform != "win32" or sys.getwindowsversion().major < 10:
        raise RuntimeError("Поддерживаются Windows 10/11 x64, не macOS/Linux и не Windows 7/8.")
    if not (3, 11) <= sys.version_info[:2] < (3, 14):
        raise RuntimeError("Нужен установленный Python 3.11–3.13 x64.")
    if struct.calcsize("P") != 8 or platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("Нужны Windows x64 и Python x64. ARM64/x86 не поддерживаются этой сборкой.")
    for name in ("launcher.py", "main.py", "montage.py", "detector.py", "chat_settings.py",
                 "mp4_metadata.py", "i18n.py", "version.py", "render_settings.py", "requirements.txt", "start.cmd"):
        if not (ROOT / name).is_file():
            raise RuntimeError(f"Не найден {name}. Скопируйте всю папку проекта.")
    try:
        import tkinter  # noqa: F401
    except ImportError as error:
        raise RuntimeError("В установленном Python отсутствует Tcl/Tk. Включите его через Modify установщика Python.") from error
    with tempfile.TemporaryFile(dir=ROOT):
        pass  # Fail early when the project folder is read-only.


def prepare_environment():
    directory = ROOT / ".venv"
    python = directory / "Scripts" / "python.exe"
    probe = ("import json,sys,struct; "
             "assert (3,11)<=sys.version_info[:2]<(3,14); "
             "assert struct.calcsize('P')==8; "
             "assert sys.prefix!=sys.base_prefix; "
             "print(json.dumps(sys.prefix))")
    if python.is_file():
        try:
            result = run([python, "-I", "-c", probe], capture_output=True, text=True, timeout=20)
            if Path(json.loads(result.stdout)).resolve() == directory.resolve():
                print("Используется существующее .venv.", flush=True)
                return python
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    if directory.exists():
        # A venv copied from another PC often contains references to its old Python.
        # Keep it intact as a backup rather than deleting user data.
        backup = ROOT / (".venv.backup_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        directory.rename(backup)
        print(f"Нерабочее окружение сохранено в {backup.name}.", flush=True)
    print("Создаётся локальное .venv...", flush=True)
    run([sys.executable, "-I", "-m", "venv", directory], cwd=ROOT, timeout=180)
    run([python, "-I", "-c", probe], capture_output=True, timeout=20)
    return python


def install_packages(python, subtitles=False):
    print("Установка Python-библиотек (требуется интернет)...", flush=True)
    run([python, "-I", "-m", "ensurepip", "--upgrade"], cwd=ROOT, timeout=180)
    run([python, "-I", "-m", "pip", "install", "--disable-pip-version-check",
         "--upgrade", "pip"], cwd=ROOT, timeout=600)
    run([python, "-I", "-m", "pip", "install", "--disable-pip-version-check",
         "--prefer-binary", "-r", ROOT / "requirements.txt"], cwd=ROOT, timeout=900)
    if subtitles:
        run([python, "-I", "-m", "pip", "install", "--disable-pip-version-check",
             "--prefer-binary", "faster-whisper"], cwd=ROOT, timeout=1200)
    run([python, "-I", "-m", "pip", "check"], cwd=ROOT, timeout=60)
    imports = "import numpy, streamlink, tkinter; root=tkinter.Tk(); root.withdraw(); root.destroy()"
    if subtitles:
        imports += "; import faster_whisper"
    run([python, "-I", "-c", imports], cwd=ROOT, timeout=90)



def tool_works(path):
    try:
        run([path, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def available_tool(name):
    override = os.environ.get(name.upper() + "_PATH")
    if override:
        if not Path(override).is_file() or not tool_works(override):
            raise RuntimeError(f"Исправьте или удалите переменную {name.upper()}_PATH: {override}")
        return override
    local = ROOT / "bin" / (name + ".exe")
    if local.is_file():
        return str(local) if tool_works(local) else None
    found = shutil.which(name + ".exe")
    return found if found and tool_works(found) else None


def download_archive(destination):
    print("Скачивается FFmpeg x64 essentials с Gyan.dev (статическая сборка)...", flush=True)
    print(FFMPEG_URL, flush=True)
    request = urllib.request.Request(FFMPEG_URL, headers={"User-Agent": "Twitchautoclipper-Setup"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
        if not response.geturl().lower().startswith("https://"):
            raise RuntimeError("Отказ от скачивания FFmpeg по незащищённому соединению.")
        total = 0
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > MAX_DOWNLOAD:
                raise RuntimeError("Архив FFmpeg превышает допустимый размер 512 МБ.")
            output.write(block)
        if not total:
            raise RuntimeError("Получен пустой архив FFmpeg.")


def extract_tools(archive, destination):
    # Only copy the two exact binaries; never extract arbitrary paths or execute ZIP scripts.
    with zipfile.ZipFile(archive) as source:
        for name in ("ffmpeg.exe", "ffprobe.exe"):
            candidates = [entry for entry in source.infolist()
                          if not entry.is_dir() and entry.filename.replace("\\", "/").split("/")[-2:] == ["bin", name]]
            if len(candidates) != 1 or not 0 < candidates[0].file_size <= MAX_DOWNLOAD:
                raise RuntimeError(f"В архиве отсутствует единственный корректный bin/{name}.")
            target = destination / name
            with source.open(candidates[0]) as inp, target.open("wb") as out:
                shutil.copyfileobj(inp, out)
            with target.open("rb") as inp:
                if inp.read(2) != b"MZ":
                    raise RuntimeError(f"{name} не является Windows-программой.")


def ensure_ffmpeg():
    if available_tool("ffmpeg") and available_tool("ffprobe"):
        print("FFmpeg и FFprobe уже доступны.", flush=True)
        return
    directory = ROOT / "bin"
    directory.mkdir(exist_ok=True)
    try:
        # Stage in the same filesystem; final files appear only after both binaries work.
        with tempfile.TemporaryDirectory(prefix="roma_ffmpeg_", dir=directory) as work:
            work = Path(work)
            archive = work / "ffmpeg.zip"
            download_archive(archive)
            extract_tools(archive, work)
            for name in ("ffmpeg.exe", "ffprobe.exe"):
                if not tool_works(work / name):
                    raise RuntimeError(f"Скачанный {name} не запускается на этом компьютере.")
            for name in ("ffmpeg.exe", "ffprobe.exe"):
                os.replace(work / name, directory / name)
        print("FFmpeg и FFprobe установлены в bin.", flush=True)
    except Exception as error:
        raise RuntimeError(f"Не удалось подготовить FFmpeg: {error}\n"
                           "Можно вручную положить статические ffmpeg.exe и ffprobe.exe в bin.\n"
                           "Официальный каталог сборок: https://ffmpeg.org/download.html") from error


def main(argv=None):
    parser = argparse.ArgumentParser(description="Установка зависимостей Twitchautoclipper на Windows x64")
    parser.add_argument("--subtitles", action="store_true", help="Также установить faster-whisper для субтитров")
    args = parser.parse_args(argv)
    try:
        check_platform()
        python = prepare_environment()
        install_packages(python, args.subtitles)
        ensure_ffmpeg()
        code = "import sys; sys.path.insert(0, sys.argv[1]); from main import preflight; preflight()"
        env = dict(os.environ, CLIP_SUBTITLES="1" if args.subtitles else "0")
        run([python, "-I", "-c", code, ROOT], cwd=ROOT, env=env, timeout=90)
        print("\nГотово: Python-библиотеки, Tkinter и фильтры FFmpeg проверены.", flush=True)
        return 0
    except Exception as error:
        print(f"\nОШИБКА УСТАНОВКИ: {error}", file=sys.stderr, flush=True)
        print("Проверьте интернет, свободное место и права записи в папку проекта.\n"
              "Roma.bat можно запустить повторно. Видео и настройки не удаляются.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
