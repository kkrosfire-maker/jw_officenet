@echo off
echo Building 사진문구넣기.exe ...
pyinstaller --noconfirm --onefile --windowed --name 사진문구넣기 ^
    --icon app.ico ^
    --add-data "app.ico;." ^
    --add-data "tessdata;tessdata" ^
    --hidden-import=PIL ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=tkinterdnd2 ^
    --collect-all tkinterdnd2 ^
    --exclude-module torch --exclude-module torchvision --exclude-module torchaudio ^
    --exclude-module scipy --exclude-module pandas --exclude-module pyarrow ^
    --exclude-module lxml --exclude-module cryptography --exclude-module matplotlib ^
    --exclude-module sklearn --exclude-module IPython --exclude-module numba ^
    --exclude-module sympy --exclude-module tensorflow --exclude-module win32com ^
    --exclude-module pythonwin --exclude-module win32ui ^
    main.py
copy /Y 기본파일.xlsx dist\
echo Done. Check dist\사진문구넣기.exe
pause
