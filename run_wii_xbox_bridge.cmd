@echo off
setlocal
set "MODE=%~1"
if not defined MODE (
    echo Select stick mode:
    echo 1. inverted
    echo 2. normal
    choice /c 12 /n /m "Mode [1/2]: "
    if errorlevel 2 (set "MODE=normal") else (set "MODE=inverted")
)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup.cmd first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "%~dp0wii_xbox_bridge.py" --mode "%MODE%"
if errorlevel 1 pause
endlocal
