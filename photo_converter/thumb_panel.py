"""좌측 파일 목록(썸네일) 패널 — main.py / annotate_app.py 공용 컴포넌트.

실제 파일 목록(리스트, 현재 인덱스)과 그에 따른 로직(로드/저장/삭제 오케스트레이션)은
소유 앱이 그대로 들고 있는다. 이 컴포넌트는 화면에 썸네일을 그리고, 클릭/우클릭/체크박스
같은 사용자 조작을 콜백으로 앱에 알려주는 역할만 담당한다.
"""
import subprocess
import threading
import tkinter as tk
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageTk

THUMB_W, THUMB_H = 112, 84
THUMB_PANEL_W    = 148


class ThumbPanel:
    def __init__(self, parent, *, on_select, on_delete, on_delete_selected,
                 extra_menu_items=None, checkbox_default=True,
                 open_label="탐색기에서 열기", delete_label="목록에서 삭제",
                 panel_w=THUMB_PANEL_W, thumb_w=THUMB_W, thumb_h=THUMB_H):
        """
        on_select(idx): 썸네일(또는 이름) 클릭 시 호출 — 파일 선택
        on_delete(idx): 컨텍스트 메뉴 "삭제" 클릭 시 호출 — 실제 목록 관리는 호출자 책임
        on_delete_selected(): 헤더 "선택삭제" 버튼 클릭 시 호출
        extra_menu_items: [(label, callback(idx)), ...] — 열기/삭제 사이에 끼워 넣을 추가 메뉴
        checkbox_default: 새 항목 추가 시 체크박스 초기값
        """
        self._on_select = on_select
        self._on_delete = on_delete
        self._extra_menu_items = extra_menu_items or []
        self._checkbox_default = checkbox_default
        self._open_label = open_label
        self._delete_label = delete_label
        self._thumb_w, self._thumb_h = thumb_w, thumb_h

        self.items = []      # list of {frame, var, img_lbl, bg_widgets, idx, path}
        self.photos = []     # PhotoImage 참조 유지 (GC 방지)
        self.gen = 0         # 세대 번호 — 구 스레드 콜백 폐기용
        self.cache = {}      # {경로: PhotoImage} — 삭제 후 재구성 시 재디코딩 방지

        self.panel = tk.Frame(parent, bg="#1e1e1e", width=panel_w)
        self.panel.pack(side="left", fill="y", padx=(0, 4))
        self.panel.pack_propagate(False)

        hdr_row = tk.Frame(self.panel, bg="#1e1e1e")
        hdr_row.pack(fill="x")
        self.hdr = tk.Label(hdr_row, text="파일 목록", bg="#1e1e1e", fg="#555",
                             font=("Segoe UI", 8), anchor="w", padx=6, pady=3)
        self.hdr.pack(side="left")
        tk.Button(hdr_row, text="선택삭제", command=on_delete_selected,
                  bg="#3d4043", fg="#ddd", relief="flat", padx=5, pady=0,
                  font=("Segoe UI", 7), cursor="hand2", bd=0,
                  activebackground="#6b3a3a", activeforeground="white"
                  ).pack(side="right", padx=4, pady=2)

        inner = tk.Frame(self.panel, bg="#1e1e1e")
        inner.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(inner, bg="#1e1e1e", highlightthickness=0, bd=0)
        scr = tk.Scrollbar(inner, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scr.set)
        scr.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.list_frame = tk.Frame(self.canvas, bg="#1e1e1e")
        self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")

        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self._bind_wheel_recursive(self.panel)

    # ── 스크롤 ──────────────────────────────────────────────────────────

    def _bind_wheel_recursive(self, widget):
        widget.bind("<MouseWheel>", self._on_wheel)
        for child in widget.winfo_children():
            self._bind_wheel_recursive(child)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    # ── 재구성 ──────────────────────────────────────────────────────────

    def rebuild(self, files, current_idx):
        """files 기반으로 패널 전체 재구성 (이미지는 백그라운드 로드)."""
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.items.clear()
        self.photos.clear()

        n = len(files)
        self.hdr.config(text=f"파일 목록  {n}개" if n else "파일 목록")
        if not files:
            return

        for i, fpath in enumerate(files):
            item = self._create_item(i, fpath)
            self.items.append(item)
            self.photos.append(None)

        self.highlight(current_idx)
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        self.gen += 1
        gen = self.gen

        to_load = []
        for fpath in files:
            cached = self.cache.get(fpath)
            if cached is not None:
                self._apply_photo_by_path(fpath, cached, gen)
            else:
                to_load.append(fpath)

        if not to_load:
            return

        def load_all():
            for fpath in to_load:
                if gen != self.gen:
                    return
                photo = self._make_photo(fpath)
                if gen != self.gen:
                    return
                if photo is not None:
                    self.cache[fpath] = photo
                self.panel.after(0, lambda p=fpath, ph=photo, g=gen: self._apply_photo_by_path(p, ph, g))

        threading.Thread(target=load_all, daemon=True).start()

    def remove_item(self, idx, current_idx):
        """전체 재구성 없이 항목 하나만 패널에서 제거."""
        if not (0 <= idx < len(self.items)):
            return
        item = self.items.pop(idx)
        self.photos.pop(idx)
        item["frame"].destroy()
        for it in self.items[idx:]:
            it["idx"] -= 1

        n = len(self.items)
        self.hdr.config(text=f"파일 목록  {n}개" if n else "파일 목록")
        self.highlight(current_idx)
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def forget_cache(self, path):
        self.cache.pop(path, None)

    # ── 항목 생성 ────────────────────────────────────────────────────────

    def _create_item(self, idx, fpath):
        BG = "#252525"
        frame = tk.Frame(self.list_frame, bg=BG, padx=3, pady=3,
                         cursor="hand2", highlightthickness=0)
        frame.pack(fill="x", padx=2, pady=1)

        img_lbl = tk.Label(frame, bg="#1a1a1a",
                            width=self._thumb_w // 8, height=self._thumb_h // 16)
        img_lbl.pack(fill="x")

        bot = tk.Frame(frame, bg=BG)
        bot.pack(fill="x", pady=(2, 0))

        name = Path(fpath).name
        if len(name) > 13:
            name = name[:10] + "..."
        name_lbl = tk.Label(bot, text=name, bg=BG, fg="#888",
                             font=("Segoe UI", 7), anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True)

        var = tk.BooleanVar(value=self._checkbox_default)
        cb = tk.Checkbutton(bot, variable=var, bg=BG,
                             activebackground=BG, selectcolor="#555",
                             bd=0, highlightthickness=0, padx=0)
        cb.pack(side="right")

        bg_widgets = [frame, img_lbl, bot, name_lbl, cb]
        # idx는 다른 항목이 삭제될 때마다 갱신되는 가변 값이라 dict로 참조한다
        # (클로저가 생성 시점의 정수를 그대로 캡처하면 삭제 이후 어긋남)
        item = {"frame": frame, "var": var, "img_lbl": img_lbl,
                "bg_widgets": bg_widgets, "idx": idx, "path": fpath}

        for w in (frame, img_lbl, name_lbl):
            w.bind("<Button-1>", lambda e, it=item: self._on_select(it["idx"]))
            w.bind("<Button-3>", lambda e, it=item: self._context_menu(e, it["idx"]))

        self._bind_wheel_recursive(frame)
        return item

    def _make_photo(self, fpath):
        try:
            buf = np.fromfile(fpath, dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if img is None:
                return None
            h, w   = img.shape[:2]
            scale  = min(self._thumb_w / w, self._thumb_h / h)
            nh, nw = max(1, int(h * scale)), max(1, int(w * scale))
            small  = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
            rgb    = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            return ImageTk.PhotoImage(Image.fromarray(rgb))
        except Exception:
            return None

    def _apply_photo_by_path(self, path, photo, gen):
        """스레드에서 로드 완료된 썸네일을 경로로 찾아 적용.
        (백그라운드 로드 도중 다른 항목이 삭제되어 인덱스가 밀려도 안전)"""
        if gen != self.gen or photo is None:
            return
        for i, item in enumerate(self.items):
            if item["path"] == path:
                self.photos[i] = photo
                item["img_lbl"].configure(image=photo, width=0, height=0)
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
                return

    # ── 하이라이트 & 스크롤 ──────────────────────────────────────────────

    def highlight(self, idx):
        for i, item in enumerate(self.items):
            active = (i == idx)
            bg = "#1e4a7a" if active else "#252525"
            sc = "#3a7abf" if active else "#555"
            item["frame"].configure(
                highlightthickness=1 if active else 0,
                highlightbackground="#4a9eff" if active else "#252525")
            for w in item["bg_widgets"]:
                try:
                    w.configure(bg=bg)
                    if isinstance(w, tk.Checkbutton):
                        w.configure(selectcolor=sc, activebackground=bg)
                except Exception:
                    pass

    def scroll_to(self, idx):
        if not self.items or idx >= len(self.items):
            return
        frame   = self.items[idx]["frame"]
        self.list_frame.update_idletasks()
        total_h = self.list_frame.winfo_reqheight()
        if total_h <= 0:
            return
        y       = frame.winfo_y()
        h       = frame.winfo_height()
        view    = self.canvas.yview()
        vis_top = view[0] * total_h
        vis_bot = vis_top + self.canvas.winfo_height()
        if y < vis_top:
            self.canvas.yview_moveto(y / total_h)
        elif y + h > vis_bot:
            self.canvas.yview_moveto(
                max(0, (y + h - self.canvas.winfo_height()) / total_h))

    # ── 체크박스 ────────────────────────────────────────────────────────

    def checked_indices(self):
        return [i for i, item in enumerate(self.items) if item["var"].get()]

    def is_checked(self, idx):
        """idx가 아직 패널에 반영 안 됐으면(썸네일 미구성 상태) 기본 포함으로 취급."""
        if idx >= len(self.items):
            return True
        return self.items[idx]["var"].get()

    # ── 컨텍스트 메뉴 ────────────────────────────────────────────────────

    def _context_menu(self, event, idx):
        if not (0 <= idx < len(self.items)):
            return
        menu = tk.Menu(self.panel, tearoff=0)
        menu.add_command(label=self._open_label,
                          command=lambda: self._open_in_explorer(self.items[idx]["path"]))
        for label, cb in self._extra_menu_items:
            menu.add_command(label=label, command=lambda cb=cb, i=idx: cb(i))
        menu.add_command(label=self._delete_label, command=lambda: self._on_delete(idx))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _open_in_explorer(self, fpath):
        subprocess.Popen(f'explorer /select,"{fpath}"', shell=True)
