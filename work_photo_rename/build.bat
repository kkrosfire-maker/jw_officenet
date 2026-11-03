@echo off
echo Building 사진문구넣기.exe ...
pyinstaller --onefile --windowed --name 사진문구넣기 ^
    --icon app.ico ^
    --add-data "app.ico;." ^
    --add-data "tessdata;tessdata" ^
    --hidden-import=PIL ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=tkinterdnd2 ^
    --collect-all tkinterdnd2 ^
    main.py
copy /Y 기본파일.xlsx dist\
echo Done. Check dist\사진문구넣기.exe
pause
