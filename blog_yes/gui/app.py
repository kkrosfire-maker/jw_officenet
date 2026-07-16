"""연세예스내과 블로그 — 이미지 생성 + 최종 조립 GUI (API 미사용).

리서치·글쓰기·이미지 HTML 디자인은 지금처럼 Claude Code 대화로 완성해서
output/[yymmdd_주제]/draft.md 와 tmp_html/body-N.html 을 만들어둔 뒤,
이 GUI로 썸네일/본문이미지 캡처와 최종 HTML 조립만 버튼으로 실행한다.

실행: python gui/app.py  (또는 run_gui.bat 더블클릭)
"""
import glob
import os
import queue
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from PIL import Image, ImageTk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pipeline_runner  # noqa: E402


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("연세예스내과 블로그 — 이미지·조립 자동화")
        self.geometry("1000x760")

        self.msg_queue = queue.Queue()
        self.busy = False

        self.topic = ""
        self.draft_md = ""
        self.final_html = ""
        self._image_refs = []

        self._build_ui()
        self._refresh_topics()
        self.after(100, self._poll_queue)

    # ── UI 구성 ─────────────────────────────────────────────────
    def _build_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_run = ttk.Frame(self.notebook)
        self.tab_images = ttk.Frame(self.notebook)
        self.tab_final = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_run, text="1. 주제 선택 · 실행")
        self.notebook.add(self.tab_images, text="2. 이미지 미리보기")
        self.notebook.add(self.tab_final, text="3. 최종 결과")

        self._build_tab_run()
        self._build_tab_images()
        self._build_tab_final()

        log_frame = ttk.LabelFrame(self, text="진행 로그")
        log_frame.pack(fill="both", expand=False, padx=8, pady=(0, 8))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state="disabled")
        self.log_text.pack(fill="both", expand=True)

    def _build_tab_run(self):
        frame = self.tab_run

        ttk.Label(
            frame,
            text="리서치·글쓰기·이미지 디자인(HTML)은 지금처럼 Claude Code 대화로 먼저 완성하세요.\n"
            "이 화면은 그 결과물(draft.md, tmp_html/)을 읽어 이미지 캡처와 최종 조립만 실행합니다.",
            foreground="#888",
            justify="left",
        ).pack(anchor="w", padx=12, pady=(12, 8))

        topic_row = ttk.Frame(frame)
        topic_row.pack(fill="x", padx=12)
        ttk.Label(topic_row, text="주제 폴더:").pack(side="left")
        self.topic_combo = ttk.Combobox(topic_row, width=40)
        self.topic_combo.pack(side="left", padx=(6, 6))
        ttk.Button(topic_row, text="새로고침", command=self._refresh_topics).pack(side="left")
        ttk.Button(topic_row, text="불러오기", command=self._load_topic).pack(side="left", padx=(6, 0))
        ttk.Button(topic_row, text="폴더 열기", command=self._open_topic_folder).pack(
            side="left", padx=(6, 0)
        )

        self.status_label = ttk.Label(frame, text="", foreground="#555", justify="left")
        self.status_label.pack(anchor="w", padx=12, pady=(10, 8))

        title_frame = ttk.LabelFrame(frame, text="썸네일 제목 줄 (짧게, 각 줄 8자 이내 권장)")
        title_frame.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Label(title_frame, text="줄 1:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.title_line1 = ttk.Entry(title_frame, width=30)
        self.title_line1.grid(row=0, column=1, padx=(0, 16), pady=6)
        ttk.Label(title_frame, text="줄 2:").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        self.title_line2 = ttk.Entry(title_frame, width=30)
        self.title_line2.grid(row=0, column=3, padx=(0, 6), pady=6)

        btns = ttk.Frame(frame)
        btns.pack(anchor="w", padx=12, pady=8)
        self.btn_images = ttk.Button(
            btns, text="이미지 생성 (썸네일 + 본문 캡처) →", command=self._start_images
        )
        self.btn_images.pack(side="left")

    def _build_tab_images(self):
        frame = self.tab_images
        container = ttk.Frame(frame)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        canvas = tk.Canvas(container, borderwidth=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.images_inner = ttk.Frame(canvas)
        self.images_inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.images_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="left", fill="y")

        btns = ttk.Frame(frame)
        btns.pack(side="right", fill="y", padx=(0, 12), pady=12)
        self.btn_regen_images = ttk.Button(
            btns, text="이미지 재생성", command=self._start_images
        )
        self.btn_regen_images.pack(fill="x", pady=(0, 8))
        self.btn_assemble = ttk.Button(btns, text="조립 진행 →", command=self._start_assemble)
        self.btn_assemble.pack(fill="x")

    def _build_tab_final(self):
        frame = self.tab_final
        self.final_label = ttk.Label(frame, text="아직 생성되지 않았습니다.", wraplength=900)
        self.final_label.pack(anchor="w", padx=12, pady=16)
        btns = ttk.Frame(frame)
        btns.pack(anchor="w", padx=12)
        ttk.Button(btns, text="브라우저에서 열기", command=self._open_final_html).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(btns, text="폴더 열기", command=self._open_final_folder).pack(side="left")

    # ── 주제 선택 ───────────────────────────────────────────────
    def _refresh_topics(self):
        topics = pipeline_runner.list_topics()
        self.topic_combo["values"] = topics
        if topics and not self.topic_combo.get():
            self.topic_combo.set(topics[0])

    def _load_topic(self):
        topic = self.topic_combo.get().strip()
        if not topic:
            messagebox.showwarning("입력 필요", "주제 폴더를 선택하거나 입력하세요.")
            return
        self.topic = topic
        info = pipeline_runner.check_readiness(topic)
        if info["draft_md"] is None:
            self.status_label.configure(text=f"⚠ {info['reason']}", foreground="#c0392b")
            self.draft_md = ""
            return

        self.draft_md = info["draft_md"]
        if info["ok"]:
            self.status_label.configure(
                text=f"✓ 준비 완료 — 이미지 마커 {info['marker_count']}개, tmp_html 파일 모두 존재",
                foreground="#2e7d32",
            )
        else:
            self.status_label.configure(text=f"⚠ {info['reason']}", foreground="#c0392b")

    def _open_topic_folder(self):
        topic = self.topic_combo.get().strip()
        if not topic:
            messagebox.showwarning("입력 필요", "주제 폴더를 선택하거나 입력하세요.")
            return
        os.startfile(pipeline_runner.topic_dir(topic))

    # ── 백그라운드 작업 오케스트레이션 ──────────────────────────
    def _log(self, msg: str):
        self.msg_queue.put(("log", msg))

    def _append_log(self, msg: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_busy(self, busy: bool):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.btn_images, self.btn_regen_images, self.btn_assemble):
            b.configure(state=state)

    def _run_bg(self, fn, on_done):
        if self.busy:
            messagebox.showwarning("진행 중", "다른 작업이 진행 중입니다. 완료 후 다시 시도하세요.")
            return
        self._set_busy(True)

        def worker():
            try:
                result = fn()
                self.msg_queue.put(("done", on_done, result))
            except Exception as e:
                self.msg_queue.put(("error", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self):
        try:
            while True:
                item = self.msg_queue.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._append_log(item[1])
                elif kind == "done":
                    _, on_done, result = item
                    self._set_busy(False)
                    on_done(result)
                elif kind == "error":
                    self._set_busy(False)
                    self._append_log(f"오류: {item[1]}")
                    messagebox.showerror("오류", item[1])
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    # ── 단계별 핸들러 ───────────────────────────────────────────
    def _start_images(self):
        topic = self.topic_combo.get().strip()
        if not topic:
            messagebox.showwarning("입력 필요", "주제 폴더를 선택하거나 입력하세요.")
            return
        self.topic = topic

        info = pipeline_runner.check_readiness(topic)
        if info["draft_md"] is None:
            messagebox.showerror("실행 불가", info["reason"])
            return
        if not info["ok"]:
            if not messagebox.askyesno(
                "일부 이미지 HTML 누락",
                f"{info['reason']}\n\n누락된 이미지는 건너뛰고 계속할까요?",
            ):
                return
        self.draft_md = info["draft_md"]

        title_lines = [
            t for t in (self.title_line1.get().strip(), self.title_line2.get().strip()) if t
        ]
        if not title_lines:
            messagebox.showwarning("입력 필요", "썸네일 제목 줄을 최소 1개 입력하세요.")
            return

        draft_md = self.draft_md

        def task():
            return pipeline_runner.run_images(topic, title_lines, draft_md, log=self._log)

        def done(new_draft_md):
            self.draft_md = new_draft_md
            self._load_image_previews()
            self.notebook.select(self.tab_images)

        self._run_bg(task, done)

    def _start_assemble(self):
        if not self.topic:
            messagebox.showwarning("순서 오류", "먼저 이미지 생성을 실행하세요.")
            return

        def task():
            return pipeline_runner.run_assemble(self.topic, log=self._log)

        def done(final_html):
            self.final_html = final_html
            self.final_label.configure(text=final_html)
            self.notebook.select(self.tab_final)

        self._run_bg(task, done)

    # ── 이미지 미리보기 / 최종 결과 ─────────────────────────────
    def _load_image_previews(self):
        for widget in self.images_inner.winfo_children():
            widget.destroy()
        self._image_refs.clear()

        images_dir = os.path.join(pipeline_runner.topic_dir(self.topic), "images")
        if not os.path.isdir(images_dir):
            ttk.Label(self.images_inner, text="이미지 폴더가 없습니다.").pack()
            return

        files = sorted(glob.glob(os.path.join(images_dir, "*.png")))
        col_count = 3
        for idx, path in enumerate(files):
            try:
                img = Image.open(path)
                img.thumbnail((220, 220))
                photo = ImageTk.PhotoImage(img)
            except Exception:
                continue
            self._image_refs.append(photo)
            cell = ttk.Frame(self.images_inner, padding=6)
            cell.grid(row=idx // col_count, column=idx % col_count)
            ttk.Label(cell, image=photo).pack()
            ttk.Label(cell, text=os.path.basename(path)).pack()

    def _open_final_html(self):
        if self.final_html and os.path.exists(self.final_html):
            webbrowser.open(self.final_html)
        else:
            messagebox.showwarning("없음", "먼저 조립 단계를 완료하세요.")

    def _open_final_folder(self):
        if not self.topic:
            messagebox.showwarning("없음", "먼저 주제를 선택하세요.")
            return
        os.startfile(pipeline_runner.topic_dir(self.topic))


if __name__ == "__main__":
    app = App()
    app.mainloop()
