@echo off
chcp 65001 >nul
cd /d "%~dp0"
python build.py
echo.
echo 창을 닫으려면 아무 키나 누르세요...
pause >nul
