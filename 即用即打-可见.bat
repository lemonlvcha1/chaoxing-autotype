@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
setlocal
cd /d "%~dp0"

rem Visible version: shows live status in this window, so you can see where it stops.
rem Copy text first, then double-click me, then click into the 学习通 / Chrome input box.

py -3 "type_text.py" --clipboard --clean --wait-window Chrome --wait-timeout 120 --settle 2 --only-window Chrome --beep --log "输入日志.txt"
if errorlevel 9009 (
    python "type_text.py" --clipboard --clean --wait-window Chrome --wait-timeout 120 --settle 2 --only-window Chrome --beep --log "输入日志.txt"
    if errorlevel 9009 (
        echo Python 3 was not found. Please install it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

echo.
pause
