@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Twitchautoclipper 1.0 - build EXE

echo === Twitchautoclipper: local Windows EXE build ===
echo This script installs packages into a project-local .venv.
echo It compiles the standalone Windows EXE.
echo Python 3.11-3.13 x64 and a full static FFmpeg build are required.
echo.

for %%F in (detector.py main.py montage.py launcher.py i18n.py version.py render_settings.py chat_settings.py mp4_metadata.py requirements.txt) do (
    if not exist "%%F" (
        echo ERROR: Missing file %%F. Download all project files into one folder.
        goto :fail
    )
)

if not exist ".venv\Scripts\python.exe" (
    set "PY="
    py -3.12 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "PY=py -3.12"
        goto :create_venv
    )
    py -3.11 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "PY=py -3.11"
        goto :create_venv
    )
    py -3.13 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "PY=py -3.13"
        goto :create_venv
    )
    python -c "import sys; assert (3,11) <= sys.version_info[:2] < (3,14)" >nul 2>&1
    if not errorlevel 1 (
        set "PY=python"
        goto :create_venv
    )
    echo ERROR: Install Python 3.12 x64 from https://www.python.org/downloads/windows/
    echo Include the Python launcher or enable Add Python to PATH.
    goto :fail
)
goto :venv_ready

:create_venv
%PY% -m venv .venv
if errorlevel 1 goto :fail

:venv_ready
set "PYTHON=%CD%\.venv\Scripts\python.exe"
"%PYTHON%" -c "import sys,struct; assert (3,11) <= sys.version_info[:2] < (3,14), 'Use Python 3.11-3.13'; assert struct.calcsize('P') == 8, 'Use 64-bit Python'"
if errorlevel 1 goto :fail

set "FFMPEG="
set "FFPROBE="
if exist "%CD%\bin\ffmpeg.exe" set "FFMPEG=%CD%\bin\ffmpeg.exe"
if exist "%CD%\bin\ffprobe.exe" set "FFPROBE=%CD%\bin\ffprobe.exe"
if not defined FFMPEG for /f "delims=" %%F in ('where ffmpeg.exe 2^>nul') do if not defined FFMPEG set "FFMPEG=%%F"
if not defined FFPROBE for /f "delims=" %%F in ('where ffprobe.exe 2^>nul') do if not defined FFPROBE set "FFPROBE=%%F"
if not defined FFMPEG goto :missing_ffmpeg
if not defined FFPROBE goto :missing_ffmpeg
set "FFMPEG_PATH=%FFMPEG%"
set "FFPROBE_PATH=%FFPROBE%"
"%FFMPEG%" -version >nul 2>&1
if errorlevel 1 goto :missing_ffmpeg
"%FFPROBE%" -version >nul 2>&1
if errorlevel 1 goto :missing_ffmpeg

echo === Installing build dependencies ===
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%PYTHON%" -m pip install -r requirements.txt "pyinstaller>=6.11,<7"
if errorlevel 1 goto :fail
set "SUBS_ARGS=--exclude-module faster_whisper"
if "%WITH_SUBTITLES%"=="1" (
    echo === Installing optional subtitle dependencies ===
    "%PYTHON%" -m pip install "faster-whisper>=1.1,<2"
    if errorlevel 1 goto :fail
    set "SUBS_ARGS=--collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers --collect-all onnxruntime --collect-all av --collect-all huggingface_hub"
)

echo === Building single-file EXE; this can take several minutes ===
"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --console --name Twitchautoclipper --collect-all streamlink --collect-all numpy --hidden-import streamlink.plugins.twitch %SUBS_ARGS% --add-binary "%FFMPEG%;bin" --add-binary "%FFPROBE%;bin" launcher.py
if errorlevel 1 goto :fail

echo.
echo SUCCESS: %CD%\dist\Twitchautoclipper.exe
echo The EXE includes Python, Streamlink, NumPy, FFmpeg and FFprobe.
echo Default build has no speech-recognition model or subtitle engine.
echo For subtitles: set WITH_SUBTITLES=1 and rebuild.
start "" "%CD%\dist"
pause
exit /b 0

:missing_ffmpeg
echo.
echo ERROR: ffmpeg.exe and ffprobe.exe are required.
echo Create a bin folder beside this script and place BOTH executables there.
echo Use a full STATIC Windows build with libx264, drawtext, ass and afftdn.
echo FFmpeg download information: https://ffmpeg.org/download.html

goto :fail

:fail
echo.
echo BUILD FAILED. Read the error above; no successful build is being claimed.
pause
exit /b 1
