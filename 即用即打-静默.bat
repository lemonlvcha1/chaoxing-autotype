@echo off
setlocal
cd /d "%~dp0"

rem Double-click to run. Does not depend on the .pyw file association.
rem Starts pythonw via start, so no console window stays open.

where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 "type_text.py" --clipboard --clean --wait-window Chrome --wait-timeout 120 --settle 2 --only-window Chrome --beep --no-gui --log "输入日志.txt"
) else (
    start "" pythonw "type_text.py" --clipboard --clean --wait-window Chrome --wait-timeout 120 --settle 2 --only-window Chrome --beep --no-gui --log "输入日志.txt"
)

exit /b 0
