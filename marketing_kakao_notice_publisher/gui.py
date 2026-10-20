"""공지 URL 입력 -> 추출 -> (수정) -> 소식 발행 -> 메시지 작성(발송 직전에서 정지)."""
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext

# PyInstaller(onedir) 실행 시 Playwright 드라이버 경로 보정
if getattr(sys, "frozen", False):
    import playwright as _pw

    _internal = Path(sys.executable).parent / "_internal"
    _pw.__file__ = str(_internal / "playwright" / "__init__.py")
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright"))

from PIL import Image, ImageTk

import extract
import kakao_biz
import learn
from paths import DATA_DIR as HERE

DEFAULT_URL = "https://pf.kakao.com/_tMlMX/"
ICON = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "app.ico")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("카카오 공지 자동 발행")
        self.geometry("760x780")
        try:
            self.iconbitmap(default=ICON)
        except tk.TclError:
            pass
        self.q: queue.Queue = queue.Queue()
        self.info: dict | None = None
        self.image_urls: list[str] = []
        self.image_paths: list[str] = []
        self._thumbs: list = []
        self.shown = ""

        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="공지 URL").pack(side="left")
        self.url = tk.Entry(top)
        self.url.pack(side="left", fill="x", expand=True, padx=6)
        self.url.focus_set()
        self.url.bind("<Return>", lambda e: self.on_extract())
        self.url.bind("<KP_Enter>", lambda e: self.on_extract())  # 숫자 키패드 엔터
        self.btn_extract = tk.Button(top, text="1. 추출", width=10, command=self.on_extract)
        self.btn_extract.pack(side="left")

        # 하단 우측: 새화면 / 끝내기 (창이 작아져도 보이도록 먼저 아래에 배치)
        bottom = tk.Frame(self)
        bottom.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        tk.Button(bottom, text="끝내기", width=10, command=self.on_quit).pack(side="right")
        tk.Button(bottom, text="새화면", width=10, command=self.on_reset).pack(side="right", padx=(0, 6))
        self.bind("<Escape>", lambda e: self.on_quit())

        head = tk.Frame(self)
        head.pack(fill="x", padx=10, pady=(10, 6))
        tk.Label(head, text="발췌문 (불필요한 부분을 지운 뒤 '학습'을 누르면 기억합니다)", anchor="w").pack(side="left")
        tk.Button(head, text="학습수정", width=8, command=self.open_rules).pack(side="right")
        tk.Button(head, text="학습", width=8, command=self.on_learn).pack(side="right", padx=(0, 4))
        self.body = scrolledtext.ScrolledText(self, height=12, font=("맑은 고딕", 10))
        self.body.pack(fill="both", expand=True, padx=10)
        self.meta = tk.Label(self, text="", anchor="w", fg="#555")
        self.meta.pack(fill="x", padx=10, pady=(6, 10))

        tk.Label(self, text="이미지 (클릭하면 크게 보기)", anchor="w").pack(fill="x", padx=10, pady=(0, 4))
        strip = tk.Frame(self)
        strip.pack(fill="x", padx=10)
        self.canvas = tk.Canvas(strip, height=112, highlightthickness=0)
        sb = tk.Scrollbar(strip, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=sb.set)
        self.canvas.pack(fill="x")
        sb.pack(fill="x")
        self.thumb_row = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.thumb_row, anchor="nw")
        self.thumb_row.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.btn_run = tk.Button(self, text="2. 소식 발행 + 메시지 작성 (발송 직전까지)", state="disabled",
                                 command=self.on_run, height=2, bg="#fee500")
        self.btn_run.pack(fill="x", padx=10, pady=14)

        tk.Label(self, text="진행 로그", anchor="w").pack(fill="x", padx=10, pady=(0, 4))
        self.log = scrolledtext.ScrolledText(self, height=9, state="disabled", font=("Consolas", 9))
        self.log.pack(fill="both", padx=10, pady=(0, 6))
        self.after(150, self.pump)

    # --- 새화면 / 끝내기
    def on_reset(self):
        """입력·추출 결과·로그를 비우고 처음 상태로 돌린다."""
        if str(self.btn_extract["state"]) == "disabled":
            return messagebox.showinfo("새화면", "작업이 진행 중입니다. 끝난 뒤에 눌러 주세요.", parent=self)
        self.info = None
        self.image_urls, self.image_paths = [], []
        self.shown = ""
        self.url.delete(0, "end")
        self.body.delete("1.0", "end")
        self.meta.config(text="")
        for w in self.thumb_row.winfo_children():
            w.destroy()
        self._thumbs.clear()
        self.canvas.xview_moveto(0)
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")
        self.btn_extract.config(state="normal")
        self.btn_run.config(state="disabled")
        self.url.focus_set()

    def on_quit(self):
        # 확인 버튼이 기본 선택이라 창이 뜬 상태에서 엔터를 치면 바로 종료된다.
        if messagebox.askokcancel("종료", "종료할까요?", default="ok", parent=self):
            self.destroy()

    # --- 로그/스레드 유틸
    def say(self, msg: str):
        self.q.put(("log", msg))

    def pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.log.config(state="normal")
                    self.log.insert("end", val + "\n")
                    self.log.see("end")
                    self.log.config(state="disabled")
                elif kind == "extracted":
                    self.info, self.image_urls, self.image_paths = val
                    self.show_thumbs()
                    self.body.delete("1.0", "end")
                    self.shown = kakao_biz.blocks(self.info["body"])
                    self.body.insert("1.0", self.shown)
                    self.meta.config(text=f"날짜 {self.info['date']}  |  제목 {self.info['title']}  |  이미지 {len(self.image_urls)}장")
                    self.btn_run.config(state="normal")
                    self.btn_extract.config(state="normal")
                elif kind == "done":
                    self.lift()
                    self.attributes("-topmost", True)
                    self.attributes("-topmost", False)
                    messagebox.showinfo("완료", val, parent=self)
                elif kind == "enable":
                    self.btn_extract.config(state="normal")
                    self.btn_run.config(state="normal" if self.info else "disabled")
        except queue.Empty:
            pass
        self.after(150, self.pump)

    # --- 학습: 추출된 발췌문 vs 현재 편집본
    def on_learn(self):
        if not self.info:
            return messagebox.showinfo("학습", "먼저 공지를 추출해 주세요.", parent=self)
        learned = learn.learn(self.shown, self.body.get("1.0", "end").strip())
        if not learned:
            return messagebox.showinfo("학습", "추출된 발췌문에서 바뀐 부분이 없습니다.", parent=self)
        self.shown = self.body.get("1.0", "end").strip()
        for msg in learned:
            self.say(f"[{msg}]")
        messagebox.showinfo("학습", f"{len(learned)}건 학습했습니다.", parent=self)

    # --- 학습 규칙 관리
    def open_rules(self):
        win = tk.Toplevel(self)
        win.title("학습 (선택 후 삭제)")
        lb = tk.Listbox(win, width=90, height=14, selectmode="extended")
        lb.pack(padx=8, pady=8, fill="both", expand=True)
        items: list[tuple[str, str]] = []

        def refresh():
            lb.delete(0, "end")
            items.clear()
            r = learn.load()
            for src, dst in r["replace"].items():
                items.append(("replace", src))
                lb.insert("end", f"수정  {src}  →  {dst}")
            for ln in r["drop"]:
                items.append(("drop", ln))
                lb.insert("end", f"삭제  {ln}")

        def delete():
            for i in reversed(lb.curselection()):
                learn.delete_rule(*items[i])
            refresh()

        tk.Button(win, text="선택 삭제", command=delete).pack(pady=(0, 8))
        refresh()

    # --- 섬네일
    def show_thumbs(self):
        for w in self.thumb_row.winfo_children():
            w.destroy()
        self._thumbs.clear()
        for i, path in enumerate(self.image_paths, 1):
            try:
                im = Image.open(path)
                im.thumbnail((140, 100))
                ph = ImageTk.PhotoImage(im)
            except Exception:
                continue
            self._thumbs.append(ph)
            lb = tk.Label(self.thumb_row, image=ph, relief="solid", bd=1, cursor="hand2")
            lb.pack(side="left", padx=3, pady=3)
            lb.bind("<Button-1>", lambda e, p=path, n=i: self.open_full(p, n))

    def open_full(self, path, n):
        win = tk.Toplevel(self)
        win.title(f"이미지 {n}/{len(self.image_paths)}  (클릭 또는 Esc로 닫기)")
        im = Image.open(path)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        im.thumbnail((int(sw * 0.9), int(sh * 0.85)))
        ph = ImageTk.PhotoImage(im)
        lb = tk.Label(win, image=ph, cursor="hand2")
        lb.image = ph
        lb.pack()
        lb.bind("<Button-1>", lambda e: win.destroy())
        win.bind("<Escape>", lambda e: win.destroy())
        win.focus_set()

    # --- 1단계: 추출
    def on_extract(self):
        if str(self.btn_extract["state"]) == "disabled":  # 엔터 키로 중복 실행 방지
            return
        url = self.url.get().strip()
        if url.isdigit():  # 글 번호만 입력한 경우
            url = DEFAULT_URL + url
        if not url.startswith("http"):
            return messagebox.showwarning("URL", "공지 URL을 입력해 주세요.")
        self.btn_extract.config(state="disabled")
        self.btn_run.config(state="disabled")
        threading.Thread(target=self._extract, args=(url,), daemon=True).start()

    def _extract(self, url):
        try:
            self.say("페이지 불러오는 중...")
            post = extract.fetch_post(url)
            info = extract.extract_text(post)
            imgs = extract.extract_images(post)
            if not info["body"] or not info["date"]:
                raise RuntimeError("발췌문 또는 날짜를 찾지 못했습니다. 공지 URL이 맞는지 확인해 주세요.")
            info["body"], applied = learn.apply(info["body"])
            for a in applied:
                self.say(f"[학습 적용] {a}")
            out = os.path.join(HERE, "downloads", info["date"].replace("/", ""))
            self.say("이미지 다운로드 중...")
            paths = extract.download_images(imgs, out)
            self.say(f"추출 완료: {info['date']} / 이미지 {len(paths)}장 -> {out}")
            self.q.put(("extracted", (info, imgs, paths)))
        except Exception as e:
            self.say(f"[오류] {e}")
            self.q.put(("enable", None))

    # --- 2단계: 발행 + 메시지
    def on_run(self):
        body = self.body.get("1.0", "end").strip()
        date = self.info["date"]
        if not messagebox.askyesno(
            "소식 발행 확인",
            f"'{date} 공지사항' 소식을 채널에 실제로 발행합니다.\n(친구들에게 공개됩니다)\n\n계속할까요?",
        ):
            return
        self.btn_extract.config(state="disabled")
        self.btn_run.config(state="disabled")
        threading.Thread(target=self._run, args=(date, body, list(self.image_paths)), daemon=True).start()

    def _run(self, date, body, paths):
        from playwright.sync_api import sync_playwright

        try:
            with sync_playwright() as p:
                # 소식 발행은 숨김(headless)으로 처리. 로그인이 풀렸을 때만 보이는 창으로 전환.
                ctx = kakao_biz.open_context(p, headless=True)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                visible = False
                if not kakao_biz.is_logged_in(page):
                    ctx.close()
                    visible = True
                    ctx = kakao_biz.open_context(p, headless=False)
                    page = ctx.pages[0] if ctx.pages else ctx.new_page()
                    self.say("로그인이 필요합니다. 열린 창에서 로그인해 주세요. (최대 5분 대기)")
                    page.goto("https://business.kakao.com/")
                    page.wait_for_url("**/space/**", timeout=300000)
                self.say("소식 발행 확인 중...")
                if kakao_biz.has_post(page, date):
                    self.say(f"이미 '{date} 공지사항' 소식이 있어 발행을 건너뜁니다.")
                else:
                    self.say("소식 발행 중...")
                    kakao_biz.write_post(page, date, body, paths, submit=True)
                    self.say("소식 발행 완료")
                # 발송 전 직접 확인해야 하므로 메시지 작성부터는 보이는 창으로 연다.
                if not visible:
                    ctx.close()
                    ctx = kakao_biz.open_context(p, headless=False)
                    page = ctx.pages[0] if ctx.pages else ctx.new_page()
                self.say("메시지 작성 중...")
                kakao_biz.write_message(page, date, body)
                self.say("✔ 메시지 작성 완료. 브라우저에서 내용을 확인하고 '다음'으로 진행해 발송하세요.")
                self.say("   (창을 닫으면 종료됩니다)")
                self.q.put(("done", "완료되었습니다.\n\n열려 있는 브라우저에서 내용을 확인하고\n'다음'으로 진행해 발송해 주세요."))
                ctx.wait_for_event("close", timeout=0)
        except Exception as e:
            self.say(f"[오류] {e}")
        finally:
            self.q.put(("enable", None))


def selftest() -> None:
    """빌드 확인용: 샘플 공지를 추출해 결과를 selftest.txt 에 기록한다."""
    out = os.path.join(os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__), "selftest.txt")
    try:
        post = extract.fetch_post("https://pf.kakao.com/_tMlMX/114907486")
        info = extract.extract_text(post)
        res = f"OK {info['date']} / 이미지 {len(extract.extract_images(post))}장 / 데이터폴더 {HERE}\n{info['body']}"
    except Exception as e:  # noqa: BLE001
        res = f"FAIL {type(e).__name__}: {e}"
    with open(out, "w", encoding="utf-8") as f:
        f.write(res)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        App().mainloop()
