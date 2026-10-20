@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run run.bat once first.
    pause
    exit /b 1
)

echo [1/5] Installing build packages...
".venv\Scripts\python.exe" -m pip install -r requirements-desktop.txt --quiet
if errorlevel 1 goto :fail

echo [2/5] Preparing icon...
if not exist "app.ico" ".venv\Scripts\python.exe" make_icon.py

echo [3/5] Cleaning previous build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo [4/5] Building (this takes a few minutes)...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean "네오벤타정산.spec"
if errorlevel 1 goto :fail

echo [5/5] Refreshing desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "make_shortcut.ps1"

echo.
echo Done: dist\네오벤타정산\네오벤타정산.exe
echo A desktop shortcut has been created/refreshed.
pause
goto :eof

:fail
echo.
echo Build failed. See the messages above.
pause
exit /b 1
