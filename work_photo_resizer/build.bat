@echo off
echo Building photo_converter.exe ...
pyinstaller --onefile --windowed --name photo_converter ^
    --icon app.ico ^
    --add-data "app.ico;." ^
    --hidden-import=PIL ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=tkinterdnd2 ^
    --collect-all tkinterdnd2 ^
    main.py
echo Done. Check dist\photo_converter.exe
pause
