@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul 2>&1
pushd "%~dp0"
if errorlevel 1 goto :folder_error
title Twitchautoclipper - dependency setup
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PY="

if not exist "%~dp0roma_setup.py" goto :missing_files
if not exist "%~dp0launcher.py" goto :missing_files
if not exist "%~dp0requirements.txt" goto :missing_files

rem Search installed Python first: a copied .venv can refer to the old PC.
where py.exe >nul 2>&1
if errorlevel 1 goto :known_paths
for %%V in (3.13 3.12 3.11) do for /f "delims=" %%P in ('py.exe -%%V -c "import sys; print(sys.executable)" 2^>nul') do call :try_python "%%P"

:known_paths
call :try_python "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
call :try_python "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :try_python "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
call :try_python "%ProgramFiles%\Python313\python.exe"
call :try_python "%ProgramFiles%\Python312\python.exe"
call :try_python "%ProgramFiles%\Python311\python.exe"
for /f "delims=" %%P in ('where python.exe 2^>nul') do call :try_python "%%P"
call :try_python "%~dp0.venv\Scripts\python.exe"
if not defined PY goto :no_python

echo.
echo === Twitchautoclipper: dependency setup ===
echo Python: "%PY%"
"%PY%" -I "%~dp0roma_setup.py" %*
if errorlevel 1 goto :failed
echo.
echo Setup complete. Starting Twitchautoclipper...
call "%~dp0start.cmd"
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%

:try_python
if defined PY exit /b 0
if not exist "%~1" exit /b 0
"%~1" -I -c "import sys,struct,platform; assert (3,11)<=sys.version_info[:2]<(3,14); assert struct.calcsize('P')==8; assert platform.machine().lower() in ('amd64','x86_64')" >nul 2>&1
if errorlevel 1 exit /b 0
set "PY=%~1"
exit /b 0

:no_python
echo ERROR: Install Python 3.11, 3.12 or 3.13 for Windows x64 first.
echo Download: https://www.python.org/downloads/windows/
echo Enable pip and Tcl/Tk in the installer, then run Roma.bat again.
echo Python is NOT installed automatically. Administrator rights are not required.
goto :failed

:missing_files
echo ERROR: Copy the entire Twitchautoclipper folder, not only Roma.bat or the EXE.
goto :failed

:folder_error
echo ERROR: Cannot open the project folder.
pause
exit /b 1

:failed
echo.
echo Setup failed. Read the error above and run Roma.bat again.
popd
pause
exit /b 1
