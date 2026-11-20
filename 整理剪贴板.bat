@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
setlocal
cd /d "%~dp0"

rem Clean the clipboard in place and show what changed.
rem Extra arguments are passed through, e.g.  clean-clipboard.bat --clean-aggressive

py -3 "type_text.py" --clean-clipboard --beep %*
if errorlevel 9009 python "type_text.py" --clean-clipboard --beep %*

echo.
pause
