"""한진택배정산 실행 파일."""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller onedir: Playwright가 드라이버를 _internal에서 찾게 한다
    import playwright as _pw
    _pw.__file__ = str(Path(sys.executable).parent / "_internal" / "playwright" / "__init__.py")
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"))

from PySide6.QtWidgets import QApplication, QMessageBox

from hanjin import paths
from hanjin.gui import MainWindow
from hanjin.theme import QSS


def setup_logging():
    paths.ensure_dirs()
    logging.basicConfig(
        filename=paths.LOG_DIR / f"{datetime.now():%Y%m%d}.log",
        level=logging.INFO, encoding="utf-8",
        format="%(asctime)s %(levelname)s %(message)s",
    )


def check_browser():
    """`한진택배정산.exe --check-browser`: Edge 자동화가 되는지 점검해 logs/browser_check.txt에 기록."""
    from playwright.sync_api import sync_playwright
    out = paths.LOG_DIR / "browser_check.txt"
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="msedge", headless=True)
            page = b.new_page()
            page.goto("http://focus.hanjin.com", wait_until="domcontentloaded")
            page.get_by_placeholder("아이디를 입력해주세요").wait_for(timeout=30000)
            msg = f"OK {page.url}"
            b.close()
    except Exception as e:
        msg = f"FAIL {e}"
    out.write_text(msg, encoding="utf-8")


def main():
    setup_logging()
    if "--check-browser" in sys.argv:
        check_browser()
        return
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)

    def excepthook(exc_type, exc, tb):
        logging.getLogger("hanjin").error("예기치 못한 오류", exc_info=(exc_type, exc, tb))
        QMessageBox.critical(None, "오류", f"예기치 못한 오류가 발생했습니다.\n{exc}\n\n자세한 내용은 logs 폴더를 확인하세요.")
    sys.excepthook = excepthook

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
