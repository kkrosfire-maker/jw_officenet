"""우측 '특이사항' 패널: 선택한 병원의 제약사별 메모를 보여주고 바로 고칠 수 있다.

- 제약사마다 이름 + 메모 입력칸. 칸 밖을 누르거나 Ctrl+Enter를 누르면 저장(on_edit 호출).
- 이전 달 기록을 이월해서 보여줄 땐 이름 옆에 '9월 기록'처럼 출처를 작게 표시한다.
- 지금 입력 중인 제약사는 강조하고 맨 위로 스크롤한다.
"""
import tkinter as tk

from names import norm

PANEL_W = 230
BG, ROW_BG, ROW_ON = "#33363a", "#43474c", "#2f6aa8"      # 어두운 화면 속에서도 구분되게 밝은 회색
TEXT_BG = "#565b61"


class NotesPanel:
    def __init__(self, parent, *, on_edit, width=PANEL_W):
        self._on_edit = on_edit
        self._hospital = ""
        self._rows = []                     # {norm, frame, text, original, pharma}

        self.panel = tk.Frame(parent, bg=BG, width=width)
        self.panel.pack_propagate(False)
        self.hdr = tk.Label(self.panel, text="특이사항", bg=BG, fg="#e6e6e6", font=("Segoe UI", 9, "bold"),
                            anchor="w", padx=6, pady=4)
        self.hdr.pack(fill="x")
        tk.Label(self.panel, text="병원을 고르면 제약사별 메모가 나옵니다.\n칸 밖을 누르면 저장됩니다.",
                 bg=BG, fg="#a8adb3", font=("Segoe UI", 8), justify="left", anchor="w", padx=6).pack(fill="x")
        inner = tk.Frame(self.panel, bg=BG)
        inner.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(inner, bg=BG, highlightthickness=0, bd=0)
        scr = tk.Scrollbar(inner, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scr.set)
        scr.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.list_frame = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        for w in (self.canvas, self.list_frame, self.hdr):
            w.bind("<MouseWheel>", self._on_wheel)

    def _on_wheel(self, e):
        self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def has_focus(self):
        f = self.panel.focus_get()
        return isinstance(f, tk.Text) and str(f).startswith(str(self.panel))

    # ── 내용 ────────────────────────────────────────────────────────────

    def set_data(self, hospital, entries, current_pharma=""):
        """entries: [{pharma, note, tag}]. 입력 중인 칸이 있으면 덮어쓰지 않는다."""
        if self.has_focus():
            return
        self._hospital = hospital
        for w in self.list_frame.winfo_children():
            w.destroy()
        self._rows = []
        self.hdr.config(text=f"특이사항 — {hospital}" if hospital else "특이사항")
        for g in entries:
            self._add_row(g)
        self.highlight(current_pharma)
        self.canvas.yview_moveto(0)

    def _add_row(self, g):
        fr = tk.Frame(self.list_frame, bg=ROW_BG, padx=4, pady=3)
        fr.pack(fill="x", padx=2, pady=2)
        top = tk.Frame(fr, bg=ROW_BG)
        top.pack(fill="x")
        name = tk.Label(top, text=g["pharma"], bg=ROW_BG, fg="#f2f2f2", font=("Malgun Gothic", 9, "bold"),
                        anchor="w")
        name.pack(side="left")
        tag = tk.Label(top, text=f"  {g['tag']}" if g.get("tag") else "", bg=ROW_BG, fg="#d9a441",
                       font=("Malgun Gothic", 8), anchor="w")
        tag.pack(side="left")
        txt = tk.Text(fr, height=1, wrap="word", bg=TEXT_BG, fg="white", insertbackground="white",
                      relief="flat", font=("Malgun Gothic", 9), padx=4, pady=2, undo=True)
        txt.pack(fill="x", pady=(2, 0))
        txt.insert("1.0", g.get("note", ""))
        txt.bind("<KeyRelease>", lambda e, t=txt: self._fit(t), add="+")        # 내용만큼만 줄을 늘린다
        txt.bind("<Configure>", lambda e, t=txt: self._fit(t), add="+")         # 폭이 바뀌면 줄바꿈도 다시 계산
        row = {"norm": norm(g["pharma"]), "frame": fr, "text": txt, "original": g.get("note", ""),
               "pharma": g["pharma"], "labels": (top, name, tag)}
        self._rows.append(row)
        txt.bind("<FocusOut>", lambda e, r=row: self._commit(r))
        txt.bind("<Control-Return>", lambda e, r=row: (self._commit(r), "break")[1])
        for w in (fr, top, name, tag):
            w.bind("<MouseWheel>", self._on_wheel)

    @staticmethod
    def _fit(txt):
        """내용이 없으면 한 줄, 있으면 (줄바꿈 포함) 그 내용이 차지하는 줄 수만큼만 높이를 맞춘다."""
        try:
            n = txt.count("1.0", "end-1c", "update", "displaylines")      # update: 줄바꿈 계산을 먼저 끝낸 뒤 센다
            n = n[0] if isinstance(n, (tuple, list)) else n
            lines = int(n or 0) + 1                      # count 는 두 위치 사이에서 넘어간 줄 수라 실제 줄 수보다 1 작다
            if int(txt.cget("height")) != lines:
                txt.config(height=lines)
                txt.after_idle(lambda: NotesPanel._fit(txt))      # 높이가 바뀌면 줄바꿈이 달라질 수 있어 한 번 더
        except tk.TclError:
            pass

    def flush(self):
        """아직 저장 안 된 입력이 있으면 모두 저장 (창 닫기·저장 직전 호출)."""
        for r in self._rows:
            self._commit(r)

    def _commit(self, row):
        text = row["text"].get("1.0", "end").strip()
        if text == row["original"].strip():
            return
        row["original"] = text
        row["labels"][2].config(text="")                    # 직접 고친 메모는 이월 표시 제거
        self._on_edit(self._hospital, row["pharma"], text)

    def highlight(self, pharma):
        """지금 입력 중인 제약사 칸을 강조하고 보이는 위치로 스크롤."""
        k = norm(pharma)
        target = None
        for r in self._rows:
            on = bool(k) and r["norm"] == k
            bg = ROW_ON if on else ROW_BG
            r["frame"].config(bg=bg)
            for w in r["labels"]:
                w.config(bg=bg)
            if on:
                target = r
        if target is not None:
            self.list_frame.update_idletasks()
            total = max(1, self.list_frame.winfo_reqheight())
            self.canvas.yview_moveto(max(0.0, (target["frame"].winfo_y() - 4) / total))
