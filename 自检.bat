@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
setlocal
cd /d "%~dp0"

rem Self test: opens a window, types a sample into it and reports pass or fail.
py -3 "type_text.py" --self-test %*
if errorlevel 9009 python "type_text.py" --self-test %*

echo.
pause
