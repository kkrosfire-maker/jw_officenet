@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Creating virtual environment...
    py -3 -m venv .venv || python -m venv .venv
    if errorlevel 1 goto :novenv
    echo [2/2] Installing packages...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
)

".venv\Scripts\python.exe" -m streamlit run app.py
goto :eof

:novenv
echo.
echo Failed to create a virtual environment. Is Python installed?
pause
