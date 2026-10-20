python -m PyInstaller --noconfirm --onefile --windowed --icon "..\app.ico" --add-data "..\app.ico;." --name "요율표검색기" --distpath "dist" --workpath "build" --specpath "build" "app\main.py"
