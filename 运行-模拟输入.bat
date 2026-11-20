@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
setlocal
cd /d "%~dp0"

rem Type the text into the focused window (simulated keystrokes).
rem Text source: input.txt next to this file, or clipboard, or the file you drop on me.

py -3 "type_text.py" %*
if errorlevel 9009 (
    python "type_text.py" %*
    if errorlevel 9009 (
        echo Python 3 was not found. Please install it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

echo.
pause
