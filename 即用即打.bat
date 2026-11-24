@echo off
setlocal
cd /d "%~dp0"

rem Main entry point.
rem Cleans the clipboard text and types it into the focused input field.
rem No console window is kept open. All options are documented in README.md.

where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 "type_text.py" --clipboard --clean --wait-window Chrome --wait-timeout 120 --settle 2 --only-window Chrome --beep --no-gui --log "输入日志.txt"
    exit /b 0
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "type_text.py" --clipboard --clean --wait-window Chrome --wait-timeout 120 --settle 2 --only-window Chrome --beep --no-gui --log "输入日志.txt"
    exit /b 0
)

echo pythonw.exe was not found. Install Python 3 from https://www.python.org/downloads/
pause
exit /b 1
