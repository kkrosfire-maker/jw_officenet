@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Building 정산알림.exe ...
pyinstaller --noconfirm --onefile --windowed --name 정산알림 ^
    --icon app.ico ^
    --add-data "ui.html;." ^
    --add-data "app.ico;." ^
    --add-data "..\work_photo_rename\tessdata;tessdata" ^
    --collect-all webview ^
    --exclude-module torch --exclude-module torchvision --exclude-module scipy ^
    --exclude-module pandas --exclude-module matplotlib --exclude-module sklearn ^
    --exclude-module IPython --exclude-module numba --exclude-module sympy --exclude-module tensorflow ^
    run.pyw
echo Done. dist\정산알림.exe
