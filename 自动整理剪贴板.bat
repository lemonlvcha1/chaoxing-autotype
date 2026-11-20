@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
setlocal
cd /d "%~dp0"

rem Start the clipboard watcher: every copy gets cleaned automatically.
rem Keep this window open while you need it; close it (or Ctrl+C) to stop.

py -3 "type_text.py" --watch-clipboard %*
if errorlevel 9009 python "type_text.py" --watch-clipboard %*

pause
