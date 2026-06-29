"""카카오 채널 이미지 다운로더 GUI"""
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# PyInstaller 환경: playwright driver 경로 및 브라우저 경로 명시
if getattr(sys, 'frozen', False):
    import os, playwright as _pw
    _internal = Path(sys.executable).parent / '_internal'
    _pw.__file__ = str(_internal / 'playwright' / '__init__.py')
    # 브라우저를 ms-playwright 시스템 경로에서 찾도록 명시 (기본값이 .local-browsers로 바뀌는 것 방지)
    if 'PLAYWRIGHT_BROWSERS_PATH' not in os.environ:
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(Path(os.environ['LOCALAPPDATA']) / 'ms-playwright')


def _ext(src: str) -> str:
    for e in (".png", ".gif", ".webp"):
        if e in src:
            return e
    return ".jpg"


def _download(url: str, path: Path) -> None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://pf.kakao.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        path.write_bytes(resp.read())


def _ensure_browser(log) -> bool:
    """Chromium이 없으면 자동 설치. 성공 시 True."""
    import os, subprocess

    browsers_path = Path(
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        or Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    )
    if browsers_path.exists() and any(browsers_path.glob("chromium-*")):
        return True

    log("Chromium 브라우저가 없습니다. 자동 설치를 시작합니다 (약 150MB)...\n")

    try:
        from playwright._impl._driver import compute_driver_executable
        driver = compute_driver_executable()
        result = subprocess.run(
            [str(driver), "install", "chromium"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            log("브라우저 설치 완료!\n\n")
            return True
        else:
            log(f"설치 실패 (코드 {result.returncode}):\n{result.stderr[:500]}\n")
            return False
    except Exception as e:
        log(f"설치 중 오류: {e}\n")
        return False


def run_download(url: str, save_dir: Path, log, on_done):
    try:
        from playwright.sync_api import sync_playwright

        if not _ensure_browser(log):
            log("브라우저 설치에 실패했습니다.\n터미널에서 'playwright install chromium'을 직접 실행해주세요.\n")
            on_done(None, None)
            return

        save_dir.mkdir(parents=True, exist_ok=True)

        # 이전 실행 파일(001.jpg 형식) 제거 — 재실행 시 잔여 파일 방지
        for old in save_dir.glob("[0-9][0-9][0-9].*"):
            old.unlink()

        log(f"페이지 로딩 중...\n{url}\n")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            for _ in range(10):
                page.evaluate("window.scrollBy(0, 500)")
                time.sleep(0.8)

            imgs = page.evaluate("""() => {
                // 1순위: 카카오 채널 본문 이미지 컨테이너
                let bodyImgs = Array.from(document.querySelectorAll('.item_archive_image img'));

                // 2순위: 래퍼 컨테이너
                if (bodyImgs.length === 0) {
                    bodyImgs = Array.from(document.querySelectorAll('.wrap_archive_content img'));
                }

                // 폴백: 헤더·다른소식 영역을 명시적으로 제외
                if (bodyImgs.length === 0) {
                    const EXCL = '.head_channel, .wrap_qr, .box_qr, .wrap_fit_thumb, .box_list_board, .item_thumb';
                    const excludedEls = Array.from(document.querySelectorAll(EXCL));
                    bodyImgs = Array.from(document.querySelectorAll('img'))
                        .filter(img => !excludedEls.some(el => el.contains(img)));
                }

                return bodyImgs.map(img => ({
                    src: img.src || img.dataset.src || img.dataset.lazySrc || '',
                    w: img.naturalWidth,
                    h: img.naturalHeight,
                }));
            }""")
            browser.close()

        visible = [i for i in imgs if i["src"].startswith("http") and i["w"] >= 200 and i["h"] >= 200]
        lazy    = [i for i in imgs if i["src"].startswith("http") and i["w"] == 0 and i["h"] == 0
                   and "kakaocdn.net" in i["src"]]
        targets = visible + lazy

        log(f"이미지 {len(targets)}개 발견 ({len(visible)} visible + {len(lazy)} lazy)\n")

        saved = 0
        for idx, img in enumerate(targets, 1):
            src  = img["src"]
            dest = save_dir / f"{idx:03d}{_ext(src)}"
            try:
                _download(src, dest)
                log(f"  [{idx}/{len(targets)}] {dest.name} 저장\n")
                saved += 1
            except Exception as e:
                log(f"  [{idx}] 실패: {e}\n")

        on_done(saved, save_dir)

    except Exception as e:
        log(f"\n오류: {e}\n")
        on_done(None, None)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("카카오 채널 이미지 다운로더")
        self.resizable(False, False)
        self._set_icon()
        self._build_ui()

    def _set_icon(self):
        try:
            from PIL import Image, ImageTk
            icon_path = Path(__file__).parent / "icon.png"
            if getattr(sys, 'frozen', False):
                icon_path = Path(sys.executable).parent / "_internal" / "icon.png"
            img = Image.open(icon_path)
            self._icon_img = ImageTk.PhotoImage(img)
            self.iconphoto(True, self._icon_img)
        except Exception:
            pass

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        # URL 입력
        tk.Label(self, text="카카오 채널 URL", font=("맑은 고딕", 10)).grid(
            row=0, column=0, sticky="w", **pad)

        self.url_var = tk.StringVar()
        url_entry = tk.Entry(self, textvariable=self.url_var, width=52, font=("맑은 고딕", 10))
        url_entry.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 6), sticky="ew")
        url_entry.bind("<Return>", lambda _: self._start())

        # 버튼
        self.btn = tk.Button(
            self, text="추출하기", font=("맑은 고딕", 11, "bold"),
            bg="#FEE500", activebackground="#e6ce00",
            width=12, command=self._start
        )
        self.btn.grid(row=2, column=0, columnspan=2, pady=6)

        # 로그
        self.log_text = tk.Text(self, width=60, height=16, font=("Consolas", 9),
                                state="disabled", bg="#f5f5f5")
        self.log_text.grid(row=3, column=0, columnspan=2, padx=12, pady=(0, 12))

        # 상태바
        self.status_var = tk.StringVar(value="URL을 입력하고 추출하기를 눌러주세요.")
        tk.Label(self, textvariable=self.status_var, fg="gray",
                 font=("맑은 고딕", 9)).grid(row=4, column=0, columnspan=2, pady=(0, 8))

    def _log(self, msg: str):
        def _append():
            self.log_text.config(state="normal")
            self.log_text.insert("end", msg)
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.after(0, _append)

    def _start(self):
        url = self.url_var.get().strip()
        if not url.startswith("http"):
            messagebox.showwarning("입력 오류", "올바른 URL을 입력해주세요.")
            return

        today = datetime.now().strftime("%y%m%d")
        post_id = url.rstrip("/").split("/")[-1]
        save_dir = Path.home() / "Desktop" / f"{today}_kakao_{post_id}"

        # UI 초기화
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self.btn.config(state="disabled")
        self.status_var.set(f"저장 위치: {save_dir}")

        def on_done(count, path):
            self.after(0, lambda: self.btn.config(state="normal"))
            if count is None:
                self.after(0, lambda: self.status_var.set("오류가 발생했습니다."))
            else:
                msg = f"완료: {count}개 저장 → {path}"
                self.after(0, lambda: self.status_var.set(msg))
                self._log(f"\n{msg}\n")

        threading.Thread(
            target=run_download,
            args=(url, save_dir, self._log, on_done),
            daemon=True,
        ).start()


if __name__ == "__main__":
    app = App()
    app.mainloop()
