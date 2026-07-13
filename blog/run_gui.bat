@echo off
cd /d "%~dp0"
python gui\app.py
if errorlevel 1 pause
