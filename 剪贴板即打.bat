@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
setlocal
cd /d "%~dp0"

rem One click: type whatever is in the clipboard into the focused window.
rem After launching, click into your input box within 4 seconds.

py -3 "type_text.py" --clipboard --countdown 4 %*
if errorlevel 9009 (
    python "type_text.py" --clipboard --countdown 4 %*
    if errorlevel 9009 (
        echo Python 3 was not found. Please install it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

echo.
pause
