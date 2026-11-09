"""입력 + 자동완성 드롭다운 위젯. 직접 입력도 가능하다.

- 입력한 글자가 이름 '어디에든' 들어 있으면 후보에 나온다 ('(주)', 공백, 괄호는 무시: '이든' → '(주)이든파마')
- Enter/Tab: 하이라이트된(기본은 맨 위) 후보로 자동 완성.  ↑↓: 후보 이동.  ▼ 버튼: 전체 목록.
- 후보에 없는 글자는 그대로 남아 직접 입력으로 쓸 수 있다.
(ttk.Combobox는 목록을 바꿔치기하면 선택한 항목과 다른 값이 들어가는 문제가 있어 직접 만들었다.)
"""
import tkinter as tk

from names import norm


class SuggestEntry(tk.Frame):
    MAX_ROWS = 12

    def __init__(self, parent, textvariable: tk.StringVar, width=22, font=("Segoe UI", 10),
                 on_pick=None, bg="#2e2e2e", marked_fn=None, open_on_empty_click=False):
        super().__init__(parent, bg=bg)
        self._open_on_empty_click = open_on_empty_click   # 빈 칸을 클릭하면 입력 커서와 함께 전체 목록도 연다
        self.var = textvariable
        self._on_pick = on_pick
        self._marked_fn = marked_fn          # () -> 정규화한 이름 집합: 목록에서 앞에 ✓를 붙일 항목
        self._primary, self._secondary = [], []
        self._items = []
        self._popup = self._lb = None
        self._font = font

        self.entry = tk.Entry(self, textvariable=self.var, width=width, font=font)
        self.entry.pack(side="left")
        tk.Button(self, text="▼", font=("Segoe UI", 7), relief="flat", bd=0, padx=4, bg="#3d4043",
                  fg="white", activebackground="#4e5255", command=self._toggle_all,
                  takefocus=0).pack(side="left", fill="y")
        e = self.entry
        e.bind("<KeyRelease>", self._on_key)
        e.bind("<Down>", lambda ev: self._move(1))
        e.bind("<Up>", lambda ev: self._move(-1))
        e.bind("<Return>", self._accept)
        e.bind("<Tab>", self._accept_tab)
        e.bind("<Escape>", lambda ev: self.close())
        e.bind("<FocusOut>", lambda ev: self.after(150, self._focus_out))
        e.bind("<ButtonRelease-1>", self._on_entry_click, add="+")

    def _on_entry_click(self, ev):
        if self._open_on_empty_click and self._popup is None and not self.var.get().strip():
            self._show([(v, False) for v in self._primary])

    # ── 후보 ────────────────────────────────────────────────────────────

    def set_candidates(self, primary, secondary=()):
        """primary: 기본 후보(▼로 열면 이것만 보임). secondary: 입력했을 때만 뒤에 덧붙는 후보."""
        self._primary, self._secondary = list(primary), list(secondary)

    def _matches(self, text):
        q = norm(text)
        if not q:
            return [(v, False) for v in self._primary]
        out = []
        for group, dim in ((self._primary, False), (self._secondary, True)):
            hits = [v for v in group if q in norm(v)]
            hits.sort(key=lambda v: 0 if norm(v).startswith(q) else 1)     # 앞에서 시작하는 것 우선
            out += [(v, dim) for v in hits]
        return out

    # ── 팝업 ────────────────────────────────────────────────────────────

    def _on_key(self, ev):
        if ev.keysym in ("Up", "Down", "Return", "Escape", "Tab", "Left", "Right", "Shift_L",
                         "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        self._refresh()

    def _toggle_all(self):
        if self._popup:
            self.close()
            return
        self.entry.focus_set()
        self._show([(v, False) for v in self._primary])

    def _refresh(self):
        m = self._matches(self.var.get())
        if m and not (len(m) == 1 and m[0][0] == self.var.get()):
            self._show(m)
        else:
            self.close()

    def _show(self, items):
        if not items:
            self.close()
            return
        self._items = [v for v, _ in items]
        if self._popup is None:
            self._popup = tk.Toplevel(self)
            self._popup.wm_overrideredirect(True)
            try:
                self._popup.wm_attributes("-topmost", True)
            except tk.TclError:
                pass
            fr = tk.Frame(self._popup, bg="#555")
            fr.pack(fill="both", expand=True)
            sb = tk.Scrollbar(fr)
            self._lb = tk.Listbox(fr, font=self._font, activestyle="none", bg="#333", fg="white",
                                  selectbackground="#3d6fa5", selectforeground="white",
                                  highlightthickness=0, bd=0, exportselection=False,
                                  yscrollcommand=sb.set)
            sb.config(command=self._lb.yview)
            sb.pack(side="right", fill="y")
            self._lb.pack(side="left", fill="both", expand=True)
            self._lb.bind("<Button-1>", self._on_click)
        self._lb.delete(0, tk.END)
        marked = self._marked_fn() if self._marked_fn else set()
        for v, dim in items:
            self._lb.insert(tk.END, ("✓  " if norm(v) in marked else "     ") + v)
            if dim:
                self._lb.itemconfig(tk.END, fg="#9a9a9a")
        self._lb.selection_set(0)
        rows = min(len(items), self.MAX_ROWS)
        w = max(self.winfo_width(), 280)
        self._popup.geometry(f"{w}x{int(rows * 22) + 2}+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")
        self._lb.config(height=rows)
        self._popup.deiconify()
        self._popup.lift()

    def close(self):
        if self._popup is not None:
            self._popup.destroy()
            self._popup = self._lb = None

    def _focus_out(self):
        self.close()

    # ── 선택 ────────────────────────────────────────────────────────────

    def _move(self, d):
        if self._popup is None:
            self._refresh() if self.var.get().strip() else self._toggle_all()
            return "break"
        cur = self._lb.curselection()
        i = max(0, min(len(self._items) - 1, (cur[0] if cur else 0) + d))
        self._lb.selection_clear(0, tk.END)
        self._lb.selection_set(i)
        self._lb.see(i)
        return "break"

    def _pick(self, value):
        self.var.set(value)
        self.entry.icursor(tk.END)
        self.close()
        self.entry.focus_set()
        if self._on_pick:
            self._on_pick(value)

    def _on_click(self, ev):
        i = self._lb.nearest(ev.y)
        if 0 <= i < len(self._items):
            self._pick(self._items[i])
        return "break"

    def _accept(self, ev=None):
        if self._popup is not None and self._items:
            cur = self._lb.curselection()
            self._pick(self._items[cur[0] if cur else 0])
            return "break"
        if self._on_pick:
            self._on_pick(self.var.get())
        return None

    def _accept_tab(self, ev):
        if self._popup is not None and self._items:
            cur = self._lb.curselection()
            self._pick(self._items[cur[0] if cur else 0])
        return None
