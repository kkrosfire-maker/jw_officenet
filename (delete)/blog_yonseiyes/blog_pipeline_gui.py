#!/usr/bin/env python3
"""
연세예스내과 블로그 파이프라인 GUI — Naver Blog Editor Style

빌드:
  pip install pyinstaller
  pyinstaller --onefile --windowed --name 블로그파이프라인 blog_pipeline_gui.py

실행 위치: exe를 blog/ 폴더 (output/, scripts/ 와 같은 위치)에 두고 실행.
"""

import os, sys, subprocess, threading, shutil, time
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

# ── 경로 탐지 ─────────────────────────────────────────────────
def _find_blog_dir():
    if getattr(sys, "frozen", False):
        candidates = [os.path.dirname(sys.executable),
                      os.path.dirname(os.path.dirname(sys.executable))]
    else:
        candidates = [os.path.dirname(os.path.abspath(__file__))]
    for c in candidates:
        if os.path.isdir(os.path.join(c, "output")):
            return c
    return candidates[0] if candidates else os.getcwd()

BLOG_DIR    = _find_blog_dir()
OUTPUT_DIR  = os.path.join(BLOG_DIR, "output")
SCRIPTS_DIR = os.path.join(BLOG_DIR, "scripts")

# ── 색상 (Naver Light Editor) ─────────────────────────────────
C_BG       = "#F2F8F5"    # 연한 그린-화이트 메인 배경
C_PANEL    = "#FFFFFF"    # 흰 패널
C_CARD     = "#FFFFFF"    # 흰 카드
C_SIDEBAR  = "#EDF7F1"    # 연한 그린 사이드바
C_HDR      = "#03C75A"    # Naver 그린 헤더
C_BORDER   = "#C8E6D4"    # 그린 톤 테두리
C_SEL      = "#D8F2E6"    # 선택 배경

C_GREEN    = "#03C75A"    # Naver 시그니처 그린
C_GREEN2   = "#027A38"    # 진한 그린 (텍스트·강조)
C_GREEN3   = "#EAF8F1"    # 연한 그린 배경
C_ORANGE   = "#F5A623"
C_BLUE     = "#2E7DD6"
C_PURPLE   = "#6C5CE7"
C_RED      = "#E84057"

C_TEXT     = "#1A1A1A"
C_TEXT2    = "#4A7060"
C_MUTED    = "#9DB5A8"
C_WHITE    = "#FFFFFF"


def _find_python():
    return shutil.which("python") or shutil.which("python3") or "python"

def _get_topics():
    if not os.path.isdir(OUTPUT_DIR):
        return []
    return sorted(d for d in os.listdir(OUTPUT_DIR)
                  if os.path.isdir(os.path.join(OUTPUT_DIR, d)))

def _get_status(topic):
    base    = os.path.join(OUTPUT_DIR, topic)
    img_dir = os.path.join(base, "images")
    imgs    = (len([f for f in os.listdir(img_dir) if f.endswith(".png")])
               if os.path.isdir(img_dir) else 0)
    return {
        "research": os.path.exists(os.path.join(base, "research.md")),
        "draft":    os.path.exists(os.path.join(base, "draft.md")),
        "images":   imgs,
        "final":    os.path.exists(os.path.join(base, "final.html")),
    }


# ── 다이얼로그 베이스 ─────────────────────────────────────────
class _BaseDialog(tk.Toplevel):
    def __init__(self, parent, title, width=420, height=300):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=C_PANEL)
        self.geometry(f"{width}x{height}")
        self.result = None
        self._build()
        self.transient(parent)
        self.grab_set()
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - width)  // 2
        py = parent.winfo_y() + (parent.winfo_height() - height) // 2
        self.geometry(f"+{px}+{py}")
        self.wait_window()

    def _header(self, text):
        h = tk.Frame(self, bg=C_GREEN, height=48)
        h.pack(fill="x")
        h.pack_propagate(False)
        c = tk.Canvas(h, width=28, height=28, bg=C_GREEN, highlightthickness=0)
        c.pack(side="left", padx=(14, 0), pady=10)
        c.create_rectangle(0, 0, 28, 28, fill="white", outline="")
        c.create_text(14, 14, text="N", font=("맑은 고딕", 11, "bold"), fill=C_GREEN)
        tk.Label(h, text=text, font=("맑은 고딕", 10, "bold"),
                 bg=C_GREEN, fg="white", padx=10).pack(side="left")

    def _body_frame(self):
        f = tk.Frame(self, bg=C_PANEL, padx=24, pady=16)
        f.pack(fill="both", expand=True)
        return f

    def _btn_row(self, parent, ok_label, ok_cmd):
        row = tk.Frame(parent, bg=C_PANEL)
        row.pack(fill="x", side="bottom", pady=(12, 0))
        tk.Button(row, text="취소", font=("맑은 고딕", 9),
                  bg=C_CARD, fg=C_TEXT2, relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  command=self.destroy).pack(side="right", padx=(8, 0))
        tk.Button(row, text=ok_label, font=("맑은 고딕", 9, "bold"),
                  bg=C_GREEN, fg="white", relief="flat",
                  padx=14, pady=7, cursor="hand2",
                  command=ok_cmd).pack(side="right")

    def _label(self, parent, text, bold=False, muted=False):
        fg = C_TEXT2 if muted else C_TEXT
        font = ("맑은 고딕", 9, "bold") if bold else ("맑은 고딕", 9)
        tk.Label(parent, text=text, font=font, bg=C_PANEL, fg=fg).pack(anchor="w")

    def _entry(self, parent):
        e = tk.Entry(parent, font=("맑은 고딕", 11), relief="flat",
                     bg=C_CARD, fg=C_TEXT,
                     insertbackground=C_GREEN,
                     highlightthickness=1,
                     highlightbackground=C_BORDER,
                     highlightcolor=C_GREEN,
                     width=36)
        e.pack(fill="x", pady=(4, 10))
        return e

    def _build(self):
        pass


# ── ThumbnailDialog ───────────────────────────────────────────
class ThumbnailDialog(_BaseDialog):
    def __init__(self, parent, topic):
        self._topic = topic
        self._entries = []
        super().__init__(parent, "썸네일 설정", width=430, height=340)

    def _build(self):
        self._header("주제확정 — 썸네일 제목 설정")
        body = self._body_frame()
        tk.Label(body, text=f"주제:  {self._topic}",
                 font=("맑은 고딕", 9), bg=C_PANEL, fg=C_GREEN).pack(anchor="w", pady=(0, 12))
        for label in ["제목 줄 1  *", "제목 줄 2  *", "제목 줄 3  (선택)"]:
            self._label(body, label, bold=True)
            self._entries.append(self._entry(body))
        self._entries[0].focus()
        self._btn_row(body, "썸네일 생성", self._submit)

    def _submit(self):
        vals = [e.get().strip() for e in self._entries]
        if not vals[0] or not vals[1]:
            messagebox.showwarning("입력 오류", "제목 줄 1, 2는 필수입니다.", parent=self)
            return
        self.result = [v for v in vals if v]
        self.destroy()


# ── NewTopicDialog ────────────────────────────────────────────
class NewTopicDialog(_BaseDialog):
    def __init__(self, parent):
        super().__init__(parent, "새 주제 추가", width=380, height=220)

    def _build(self):
        self._header("새 주제 폴더 생성")
        body = self._body_frame()
        self._label(body, "주제 이름 (띄어쓰기 없이)", bold=True)
        self._label(body, "예: 여름철열사병예방", muted=True)
        self._name_entry = self._entry(body)
        self._name_entry.focus()
        self._name_entry.bind("<Return>", lambda _: self._submit())
        self._btn_row(body, "생성", self._submit)

    def _submit(self):
        name = self._name_entry.get().strip()
        if not name:
            messagebox.showwarning("입력 오류", "주제 이름을 입력하세요.", parent=self)
            return
        self.result = name
        self.destroy()


# ── 메인 앱 ───────────────────────────────────────────────────
class BlogPipelineApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("블로그 파이프라인 — 연세예스내과")
        self.geometry("980x700")
        self.minsize(820, 580)
        self.configure(bg=C_BG)
        self._topics   = []
        self._selected = None
        self._running  = False
        self._build_ui()
        self._refresh()

    # ── UI 조립 ──────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()

        body = tk.Frame(self, bg=C_BG)
        body.pack(fill="both", expand=True)

        # 좌 사이드바
        sidebar = tk.Frame(body, bg=C_SIDEBAR, width=210)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        # 세로 구분선
        tk.Frame(body, bg=C_BORDER, width=1).pack(side="left", fill="y")

        # 우 메인 영역
        main = tk.Frame(body, bg=C_BG)
        main.pack(side="left", fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        self._build_status_panel(main)
        self._build_action_panel(main)
        self._build_log_panel(main)

    # ── 헤더 ──────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=C_HDR, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # N 로고 (흰 박스에 그린 N)
        c = tk.Canvas(hdr, width=32, height=32, bg=C_HDR, highlightthickness=0)
        c.pack(side="left", padx=(16, 0), pady=9)
        c.create_rectangle(0, 0, 32, 32, fill="white", outline="")
        c.create_text(16, 16, text="N", font=("맑은 고딕", 14, "bold"), fill=C_GREEN)

        tk.Label(hdr, text=" 연세예스내과 블로그",
                 font=("맑은 고딕", 12, "bold"),
                 bg=C_HDR, fg="white").pack(side="left", padx=(6, 0))

        # 우측 컨트롤
        tk.Button(hdr, text="↺",
                  font=("맑은 고딕", 14),
                  bg=C_HDR, fg="white", relief="flat",
                  activebackground=C_GREEN2, activeforeground="white",
                  padx=6, pady=0, cursor="hand2",
                  command=self._refresh).pack(side="right", padx=16)

        tk.Label(hdr, text="USER: 박원종",
                 font=("Consolas", 9),
                 bg=C_HDR, fg="#C8F5DE").pack(side="right", padx=4)

        self._status_dot = tk.Label(hdr, text="●",
                                    font=("맑은 고딕", 9),
                                    bg=C_HDR, fg="white")
        self._status_dot.pack(side="right", padx=(12, 0))

        self._status_lbl = tk.Label(hdr, text="IDLE",
                                    font=("Consolas", 8),
                                    bg=C_HDR, fg="#C8F5DE")
        self._status_lbl.pack(side="right")

    # ── 사이드바 ──────────────────────────────────────────────
    def _build_sidebar(self, parent):
        # 섹션 레이블
        tk.Label(parent, text="  내 프로젝트",
                 font=("맑은 고딕", 8, "bold"),
                 bg=C_SIDEBAR, fg=C_TEXT2,
                 pady=10).pack(fill="x")
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill="x")

        # 리스트박스
        lf = tk.Frame(parent, bg=C_SIDEBAR)
        lf.pack(fill="both", expand=True)

        self._listbox = tk.Listbox(
            lf, font=("맑은 고딕", 10),
            bg=C_SIDEBAR, fg=C_TEXT,
            selectbackground=C_SEL,
            selectforeground=C_GREEN2,
            relief="flat", bd=0,
            activestyle="none",
            highlightthickness=0,
            selectborderwidth=0,
        )
        sb = ttk.Scrollbar(lf, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._listbox.pack(fill="both", expand=True)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)
        self._listbox.bind("<Button-3>", self._on_listbox_rclick)

        # 추가 버튼
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill="x")
        tk.Button(parent, text="＋  새 주제 추가",
                  font=("맑은 고딕", 9, "bold"),
                  bg=C_GREEN3, fg=C_GREEN2,
                  relief="flat",
                  activebackground=C_GREEN, activeforeground="white",
                  padx=0, pady=11, cursor="hand2",
                  command=self._new_topic).pack(fill="x")

    # ── 상태 패널 ─────────────────────────────────────────────
    def _build_status_panel(self, parent):
        outer = tk.Frame(parent, bg=C_BG)
        outer.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 0))

        card = tk.Frame(outer, bg=C_CARD,
                        highlightthickness=1, highlightbackground=C_BORDER)
        card.pack(fill="x")

        self._status_inner = tk.Frame(card, bg=C_CARD, padx=18, pady=14)
        self._status_inner.pack(fill="both")

        tk.Label(self._status_inner, text="← 좌측에서 주제를 선택하세요",
                 font=("맑은 고딕", 10),
                 bg=C_CARD, fg=C_MUTED).pack(anchor="w")

    def _render_status(self, topic):
        for w in self._status_inner.winfo_children():
            w.destroy()

        st = _get_status(topic)

        # 주제명 행
        top = tk.Frame(self._status_inner, bg=C_CARD)
        top.pack(fill="x", pady=(0, 12))
        tk.Label(top, text="◈",
                 font=("맑은 고딕", 11),
                 bg=C_CARD, fg=C_GREEN).pack(side="left", padx=(0, 8))
        tk.Label(top, text=topic,
                 font=("맑은 고딕", 13, "bold"),
                 bg=C_CARD, fg=C_TEXT).pack(side="left")

        # 4단계 파이프라인 카드
        stages = [
            ("1  리서치",   "research.md",                             st["research"]),
            ("2  본문작성", "draft.md",                                st["draft"]),
            ("3  이미지",   f"{st['images']}개" if st["images"] else "없음", st["images"] > 0),
            ("4  최종본",   "final.html",                              st["final"]),
        ]

        pipe = tk.Frame(self._status_inner, bg=C_CARD)
        pipe.pack(fill="x")

        for i, (label, fname, ok) in enumerate(stages):
            bg  = C_GREEN3 if ok else C_PANEL
            fg  = C_GREEN2 if ok else C_TEXT2
            bdr = C_GREEN  if ok else C_BORDER

            sf = tk.Frame(pipe, bg=bg,
                          highlightthickness=1, highlightbackground=bdr)
            sf.pack(side="left", expand=True, fill="x",
                    padx=(0, 6 if i < 3 else 0))

            tk.Label(sf, text=label,
                     font=("맑은 고딕", 8, "bold"),
                     bg=bg, fg=fg,
                     pady=5, padx=10).pack(anchor="w")
            tk.Label(sf, text=fname,
                     font=("Consolas", 8),
                     bg=bg, fg=C_GREEN if ok else C_MUTED,
                     pady=(0, 5), padx=10).pack(anchor="w")

    # ── 액션 패널 ─────────────────────────────────────────────
    def _build_action_panel(self, parent):
        outer = tk.Frame(parent, bg=C_BG)
        outer.grid(row=1, column=0, sticky="ew", padx=16, pady=10)

        card = tk.Frame(outer, bg=C_CARD,
                        highlightthickness=1, highlightbackground=C_BORDER)
        card.pack(fill="x")

        inner = tk.Frame(card, bg=C_CARD, padx=14, pady=12)
        inner.pack(fill="x")

        tk.Label(inner, text="PIPELINE ACTIONS",
                 font=("Consolas", 8),
                 bg=C_CARD, fg=C_TEXT2).pack(anchor="w", pady=(0, 8))

        btn_row = tk.Frame(inner, bg=C_CARD)
        btn_row.pack(fill="x")

        self._action_btns = {}
        actions = [
            ("본문작성",         C_GREEN,   self._do_write),
            ("썸네일생성",       C_ORANGE,  self._do_confirm_topic),
            ("이미지캡처",       C_BLUE,    self._do_capture),
            ("미리보기 및 수정", C_PURPLE,  self._do_preview_edit),
            ("최종파일생성",     C_BLUE,    self._do_build_final),
            ("폴더열기",         "#3A5A4A", self._do_open_folder),
        ]

        for col, (label, color, cmd) in enumerate(actions):
            btn_row.columnconfigure(col, weight=1)
            b = tk.Button(btn_row, text=label,
                          font=("맑은 고딕", 9, "bold"),
                          bg=color, fg="white", relief="flat",
                          padx=0, pady=10, cursor="hand2",
                          command=cmd,
                          activebackground=color, activeforeground="white")
            b.grid(row=0, column=col,
                   padx=(0, 5 if col < 5 else 0), sticky="ew")
            self._action_btns[label] = b

    # ── 로그 패널 ─────────────────────────────────────────────
    def _build_log_panel(self, parent):
        outer = tk.Frame(parent, bg=C_BG)
        outer.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 14))
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        # 로그 헤더
        lhdr = tk.Frame(outer, bg=C_CARD,
                        highlightthickness=1, highlightbackground=C_BORDER)
        lhdr.grid(row=0, column=0, sticky="ew")

        tk.Label(lhdr, text="  실행 로그",
                 font=("맑은 고딕", 8, "bold"),
                 bg=C_CARD, fg=C_GREEN2, pady=7).pack(side="left")
        tk.Button(lhdr, text="지우기",
                  font=("맑은 고딕", 8),
                  bg=C_CARD, fg=C_MUTED, relief="flat",
                  padx=10, pady=3, cursor="hand2",
                  command=self._clear_log).pack(side="right", padx=8, pady=5)

        # 로그 터미널 (어두운 터미널 유지 — 가독성)
        log_wrap = tk.Frame(outer, bg="#0D1A12",
                            highlightthickness=1, highlightbackground=C_BORDER)
        log_wrap.grid(row=1, column=0, sticky="nsew")
        log_wrap.columnconfigure(0, weight=1)
        log_wrap.rowconfigure(0, weight=1)

        self._log = tk.Text(
            log_wrap,
            font=("Consolas", 9),
            bg="#0D1A12", fg="#7AE8A0",
            relief="flat", bd=0,
            padx=14, pady=10,
            wrap="word",
            state="disabled",
            highlightthickness=0,
            insertbackground=C_GREEN,
        )
        sb = ttk.Scrollbar(log_wrap, command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        self._log.grid(row=0, column=0, sticky="nsew")

        self._log.tag_configure("ok",       foreground="#03C75A")
        self._log.tag_configure("err",      foreground="#E84057")
        self._log.tag_configure("cmd",      foreground="#5BA8E0")
        self._log.tag_configure("info",     foreground="#7AE8A0")
        self._log.tag_configure("progress", foreground="#5BA8E0")

        self._log_write(">> 블로그 파이프라인 초기화 완료\n", "ok")
        self._log_write(f">> 프로젝트 경로: {BLOG_DIR}\n", "info")

    # ── 주제 목록 ─────────────────────────────────────────────
    def _refresh(self):
        self._topics = _get_topics()
        self._listbox.delete(0, "end")
        for t in self._topics:
            st   = _get_status(t)
            done = sum([st["research"], st["draft"], st["images"] > 0, st["final"]])
            icon = "◈" if done == 4 else "◇"
            self._listbox.insert("end", f"  {icon}  {t}")
        if self._selected in self._topics:
            idx = self._topics.index(self._selected)
            self._listbox.selection_set(idx)
            self._listbox.see(idx)

    def _on_select(self, _):
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._topics):
            self._selected = self._topics[idx]
            self._render_status(self._selected)

    def _on_listbox_rclick(self, event):
        idx = self._listbox.nearest(event.y)
        if idx < 0 or idx >= len(self._topics):
            return
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(idx)
        self._selected = self._topics[idx]
        self._render_status(self._selected)
        menu = tk.Menu(self, tearoff=0, bg=C_CARD, fg=C_TEXT,
                       activebackground=C_RED, activeforeground="white",
                       font=("맑은 고딕", 9))
        menu.add_command(
            label=f"  🗑  '{self._selected}' 삭제",
            command=self._delete_selected_topic,
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _delete_selected_topic(self):
        if not self._selected:
            return
        if not messagebox.askyesno(
            "주제 삭제",
            f"'{self._selected}' 폴더를 삭제합니다.\n"
            f"output/{self._selected}/ 안의 모든 파일이 삭제됩니다.\n\n계속할까요?",
            parent=self,
        ):
            return
        folder = os.path.join(OUTPUT_DIR, self._selected)
        try:
            shutil.rmtree(folder)
            self._log_write(f">> 삭제됨: output/{self._selected}/\n", "ok")
            self._selected = None
            for w in self._status_inner.winfo_children():
                w.destroy()
            tk.Label(self._status_inner, text="← 좌측에서 주제를 선택하세요",
                     font=("맑은 고딕", 10), bg=C_CARD, fg=C_MUTED).pack(anchor="w")
            self._refresh()
        except Exception as e:
            self._log_write(f">> 삭제 오류: {e}\n", "err")

    def _new_topic(self):
        dlg = NewTopicDialog(self)
        if not dlg.result:
            return
        name = dlg.result
        if os.path.exists(os.path.join(OUTPUT_DIR, name)):
            messagebox.showwarning("중복", f"'{name}' 폴더가 이미 존재합니다.")
            return
        os.makedirs(os.path.join(OUTPUT_DIR, name, "images"),   exist_ok=True)
        os.makedirs(os.path.join(OUTPUT_DIR, name, "tmp_html"), exist_ok=True)
        self._log_write(f">> 생성: output/{name}/\n", "ok")
        self._refresh()

    # ── 액션 핸들러 ───────────────────────────────────────────
    def _need_topic(self):
        if not self._selected:
            messagebox.showinfo("주제 선택", "좌측에서 주제를 먼저 선택하세요.")
            return False
        return True

    def _do_confirm_topic(self):
        if not self._need_topic():
            return
        dlg = ThumbnailDialog(self, self._selected)
        if not dlg.result:
            return
        self._run_script("make_thumbnail.py", self._selected, *dlg.result)

    def _do_write(self):
        if not self._need_topic():
            return
        prompt = (
            f"주제는 '{self._selected}'. "
            f"agents/researcher.md 를 읽고 리서치 후 output/{self._selected}/research.md 생성, "
            f"이어서 agents/writer.md 를 읽고 output/{self._selected}/draft.md 생성해줘. "
            f"웹 검색 권한이 없으면 학습 데이터로 바로 진행해. "
            f"중간에 사용자에게 선택지를 묻거나 확인을 요청하지 말고 최선의 판단으로 끝까지 진행해줘."
        )
        self._launch_claude_task(prompt)

    def _do_capture(self):
        if not self._need_topic():
            return
        self._run_script("capture_bodies.py", self._selected)

    def _do_preview_edit(self):
        if not self._need_topic():
            return
        html_path  = os.path.join(OUTPUT_DIR, self._selected, "final.html")
        draft_path = os.path.join(OUTPUT_DIR, self._selected, "draft.md")
        if os.path.exists(html_path):
            webbrowser.open("file:///" + html_path.replace(os.sep, "/"))
        elif os.path.exists(draft_path):
            webbrowser.open("file:///" + draft_path.replace(os.sep, "/"))
            self._log_write(">> final.html 없음 — draft.md 열었습니다.\n", "info")
        else:
            self._log_write(">> 열 파일 없음. 본문작성을 먼저 실행하세요.\n", "err")
            return
        self._open_claude_interactive()

    def _do_build_final(self):
        if not self._need_topic():
            return
        self._run_script("build_final.py", self._selected)

    def _do_open_folder(self):
        if not self._need_topic():
            return
        os.startfile(os.path.join(OUTPUT_DIR, self._selected))

    def _launch_claude_task(self, prompt: str):
        """claude -p 비대화형 실행 — 출력을 GUI 로그에 실시간 스트리밍."""
        if self._running:
            messagebox.showinfo("실행 중", "현재 작업이 완료될 때까지 기다려주세요.")
            return

        task_file     = os.path.join(BLOG_DIR, ".claude_task.txt")
        launcher_file = os.path.join(BLOG_DIR, ".claude_run.py")

        with open(task_file, 'w', encoding='utf-8') as f:
            f.write(prompt)

        # 런처: claude -p 출력을 line-by-line으로 stdout에 흘려보냄
        launcher_code = (
            "import subprocess, os, sys, io\n"
            # stdout을 UTF-8로 강제 설정 (cp949 인코딩 오류 방지)
            "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)\n"
            f"os.chdir(r'{BLOG_DIR}')\n"
            "with open('.claude_task.txt', encoding='utf-8') as f:\n"
            "    msg = f.read()\n"
            "proc = subprocess.Popen(\n"
            "    ['claude', '-p', msg],\n"
            "    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,\n"
            "    text=True, encoding='utf-8', errors='replace',\n"
            ")\n"
            "for line in proc.stdout:\n"
            "    print(line, end='', flush=True)\n"
            "proc.wait()\n"
            "sys.exit(proc.returncode)\n"
        )
        with open(launcher_file, 'w', encoding='utf-8') as f:
            f.write(launcher_code)

        python = _find_python()
        self._running = True
        self._log_write(f"\n>> Claude 작업 시작: {self._selected} 본문작성\n", "cmd")
        self._set_running(True)
        threading.Thread(
            target=self._worker,
            args=([python, launcher_file],),
            daemon=True,
        ).start()

    def _open_claude_interactive(self):
        """대화형 Claude Code 세션 열기 (미리보기·수정용)."""
        try:
            subprocess.Popen(
                ['cmd', '/k', 'claude'],
                cwd=BLOG_DIR,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            self._log_write(">> Claude Code 대화 창 열림\n", "ok")
        except FileNotFoundError:
            self._log_write(">> 오류: 'claude' CLI를 찾을 수 없습니다.\n", "err")

    # ── 스크립트 실행 ──────────────────────────────────────────
    def _run_script(self, script_name, *args):
        if self._running:
            messagebox.showinfo("실행 중", "현재 작업이 완료될 때까지 기다려주세요.")
            return
        self._running = True
        script  = os.path.join(SCRIPTS_DIR, script_name)
        python  = _find_python()
        cmd     = [python, script] + list(args)
        display = f"python {script_name} {' '.join(str(a) for a in args)}"
        self._log_write(f"\n>> {display}\n", "cmd")
        self._set_running(True)
        threading.Thread(target=self._worker, args=(cmd,), daemon=True).start()

    def _worker(self, cmd):
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", cwd=BLOG_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW,
                env=env,
            )
            for line in proc.stdout:
                self.after(0, self._log_write, line)
            proc.wait()
            ok  = proc.returncode == 0
            msg = ">> 완료\n" if ok else f">> 오류 (exit {proc.returncode})\n"
            self.after(0, self._log_write, msg, "ok" if ok else "err")
        except FileNotFoundError:
            self.after(0, self._log_write, ">> Python을 찾을 수 없습니다.\n", "err")
        except Exception as e:
            self.after(0, self._log_write, f">> {e}\n", "err")
        finally:
            self.after(0, self._on_done)

    def _on_done(self):
        self._running = False
        self._set_running(False)
        self._refresh()
        if self._selected:
            self._render_status(self._selected)

    def _set_running(self, running: bool):
        for b in self._action_btns.values():
            b.configure(state="disabled" if running else "normal")
        if running:
            self._run_start = time.time()
            self._status_dot.configure(text="●", fg=C_GREEN)
            self._status_lbl.configure(text="RUNNING", fg=C_GREEN)
            self._tick()
        else:
            # 로그에서 progress 라인 제거
            self._log.configure(state="normal")
            for r0, r1 in zip(*[iter(self._log.tag_ranges("progress"))] * 2):
                self._log.delete(r0, r1)
            self._log.configure(state="disabled")
            self._status_dot.configure(text="●", fg=C_TEXT2)
            self._status_lbl.configure(text="IDLE", fg=C_TEXT2)

    _SPIN    = ("◐", "◓", "◑", "◒")
    _spin_idx = 0

    def _tick(self):
        if not self._running:
            return
        elapsed = int(time.time() - self._run_start)
        mins, s = divmod(elapsed, 60)
        BlogPipelineApp._spin_idx = (BlogPipelineApp._spin_idx + 1) % 4
        icon = self._SPIN[BlogPipelineApp._spin_idx]

        # 헤더 도트 깜빡임
        self._status_dot.configure(
            fg=C_GREEN if BlogPipelineApp._spin_idx % 2 == 0 else C_GREEN2
        )

        # 로그 하단 progress 라인 인플레이스 갱신
        line = f"{icon} 실행 중...  {mins:02d}:{s:02d}"
        self._log.configure(state="normal")
        ranges = self._log.tag_ranges("progress")
        if ranges:
            self._log.delete(ranges[0], ranges[-1])
        self._log.insert("end", line, "progress")
        self._log.see("end")
        self._log.configure(state="disabled")

        self.after(500, self._tick)

    # ── 로그 ──────────────────────────────────────────────────
    def _log_write(self, text, tag=None):
        self._log.configure(state="normal")
        # progress 라인을 잠시 제거 후 새 텍스트 삽입 (항상 맨 아래 유지)
        ranges = self._log.tag_ranges("progress")
        if ranges:
            self._log.delete(ranges[0], ranges[-1])
        if tag:
            self._log.insert("end", text, tag)
        else:
            self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")


if __name__ == "__main__":
    app = BlogPipelineApp()
    app.mainloop()
