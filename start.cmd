@echo off
setlocal
cd /d "%~dp0"
title Twitchautoclipper 1.0
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

rem Launch the application with its existing Python environment.
if not exist "%~dp0launcher.py" (
    echo ERROR: launcher.py not found. Download and extract the entire repository into one folder.
    pause
    exit /b 1
)
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0launcher.py"
    goto :finished
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0launcher.py"
    goto :finished
)
where py.exe >nul 2>&1
if not errorlevel 1 (
    py.exe -3 "%~dp0launcher.py"
    goto :finished
)
python.exe "%~dp0launcher.py"

:finished
if errorlevel 1 (
    echo.
    echo Program failed. Copy the error above.
    echo On a new PC or after moving the folder, run Roma.bat to install or repair dependencies.
    pause
    exit /b 1
)
exit /b 0
