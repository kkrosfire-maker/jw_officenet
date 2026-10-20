@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean 한진택배정산.spec
if errorlevel 1 exit /b 1
copy /y 사용설명.txt dist\한진택배정산\ >nul
powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\한진택배정산' -DestinationPath 'dist\한진택배정산_v1.0.zip'"
echo.
echo 빌드 완료: dist\한진택배정산\한진택배정산.exe , dist\한진택배정산_v1.0.zip
