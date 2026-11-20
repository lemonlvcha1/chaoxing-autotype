@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
setlocal
cd /d "%~dp0"

rem Run the self test with python. Does not depend on the .pyw file association.
py -3 "自检.pyw" %*
if errorlevel 9009 python "自检.pyw" %*

echo.
pause
