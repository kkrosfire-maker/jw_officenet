@echo off
cd /d "%~dp0"
start "" cmd /c "ping -n 3 127.0.0.1 >nul & start http://127.0.0.1:8787/admin.html"
python admin_server.py
pause
