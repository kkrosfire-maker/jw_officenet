python -m PyInstaller --noconfirm --onefile --windowed `
  --name "제너리스주문관리" `
  --icon "app.ico" --add-data "app.ico;." `
  --add-data "app;app" `
  app\main.py
