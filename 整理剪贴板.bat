@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
setlocal
cd /d "%~dp0"

rem Clipboard cleaner.
rem   double-click      -> clean once and show the before/after preview
rem   ... --watch       -> keep running: every copy is cleaned automatically
rem Extra arguments are forwarded to the one-shot mode, e.g. --clean-aggressive

if /i "%~1"=="--watch" (
    py -3 "type_text.py" --watch-clipboard
    if errorlevel 9009 python "type_text.py" --watch-clipboard
) else (
    py -3 "type_text.py" --clean-clipboard --beep %*
    if errorlevel 9009 python "type_text.py" --clean-clipboard --beep %*
)

echo.
pause
