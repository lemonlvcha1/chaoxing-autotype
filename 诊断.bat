@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
setlocal
cd /d "%~dp0"

rem 诊断：打印本程序与各窗口的权限级别、剪贴板内容长度等，不改动任何东西。
py -3 "type_text.py" --diagnose
if errorlevel 9009 python "type_text.py" --diagnose

echo.
echo 把上面的内容截图或复制给我，就能定位"发不出字"的原因。
pause
