"""2단계(annotate.py) 단독 테스트용 GUI. main.py와는 독립적으로 실행된다."""
import math
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import cv2
import numpy as np
import openpyxl
from PIL import Image, ImageGrab, ImageTk
from tkinterdnd2 import TkinterDnD, DND_FILES

from annotate import parse_filename, build_label, annotate_image, rect_corners

IMAGE_EXT     = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
EXCEL_EXT     = {".xlsx", ".xlsm"}
SAVE_FOLDER   = "라벨완료"
CANVAS_W      = 620
CANVAS_H      = 620
HANDLE_R      = 5       # 모서리 핸들 canvas 반지름
RESIZE_HIT    = HANDLE_R * 2.5   # 이 반지름 안쪽: 리사이즈
ROTATE_HIT    = RESIZE_HIT + 16  # 이 반지름 안쪽(리사이즈 바깥쪽): 회전
MIN_HALF      = 8        # 리사이즈 시 최소 반너비/반높이(이미지 px)
MONTHS        = [f"{i}월" for i in range(1, 13)]
UNDO_LIMIT    = 50

THUMB_W, THUMB_H = 112, 84
THUMB_PANEL_W    = 148


def read_image(path: str):
    buf = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def write_image(path: str, img) -> bool:
    ext = Path(path).suffix.lower() or ".png"
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(str(path))
    return bool(ok)


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    p = directory / (stem + suffix)
    n = 1
    while p.exists():
        p = directory / f"{stem}_{n}{suffix}"
        n += 1
    return p


def load_reference_excel(path: str):
    """1열=병원명, 2열=제약사명 기준 엑셀을 읽어 (병원명 목록, 제약사명 목록) 반환.
    1행은 헤더로 간주해 건너뛴다."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    hospitals, pharmas = [], []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        if len(row) > 0 and row[0] not in (None, ""):
            hospitals.append(str(row[0]).strip())
        if len(row) > 1 and row[1] not in (None, ""):
            pharmas.append(str(row[1]).strip())
    wb.close()
    # 순서 유지 + 중복 제거
    hospitals = list(dict.fromkeys(hospitals))
    pharmas   = list(dict.fromkeys(pharmas))
    return hospitals, pharmas


class AutocompleteEntry(tk.Entry):
    """
    직접 입력도 가능한 일반 입력창. 두 글자 이상 입력하고 (타이핑이 잠시 멈추면)
    전체 후보 중 부분 일치하는 항목을 마우스로 클릭해 고를 수 있는 목록을 아래에 띄운다.

    ttk.Combobox + event_generate("<Down>") 방식은 드롭다운을 열 때 키보드 포커스가
    내부 리스트박스로 넘어가 버려서, 그 다음 타이핑이 입력창이 아니라 리스트박스로
    들어가며 "입력이 멈추는" 것처럼 보이는 버그가 있었다. 이 위젯은 클릭으로만
    선택하는 별도의 팝업(Toplevel)을 써서 입력창의 포커스를 건드리지 않는다.
    """
    DEBOUNCE_MS = 150
    MAX_ITEMS   = 8
    ITEM_H      = 22

    def __init__(self, parent, textvariable=None, **kw):
        self._var = textvariable if textvariable is not None else tk.StringVar()
        super().__init__(parent, textvariable=self._var, **kw)
        self._all_values = []
        self._filter_job = None
        self._popup      = None
        self._listbox    = None
        self.bind("<KeyRelease>", self._on_keyrelease)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Escape>", lambda e: self._close_popup())

    def set_candidates(self, values):
        self._all_values = list(values)

    def _on_keyrelease(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        if self._filter_job:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(self.DEBOUNCE_MS, self._apply_filter)

    def _apply_filter(self):
        self._filter_job = None
        text = self._var.get().strip()
        if len(text) >= 2 and self._all_values:
            matches = [v for v in self._all_values if text in v]
            if matches:
                self._show_popup(matches)
                return
        self._close_popup()

    def _show_popup(self, matches):
        if self._popup is None:
            self._popup = tk.Toplevel(self)
            self._popup.wm_overrideredirect(True)
            try:
                self._popup.wm_attributes("-topmost", True)
            except tk.TclError:
                pass
            self._listbox = tk.Listbox(self._popup, font=self.cget("font"), activestyle="none",
                                        bg="#333333", fg="white", selectbackground="#3d6fa5",
                                        highlightthickness=1, highlightbackground="#555", bd=0)
            self._listbox.pack(fill="both", expand=True)
            # <<ListboxSelect>>가 아니라 클릭 자체를 바로 처리 — 리스트박스에
            # 포커스가 남더라도 입력창 타이핑을 방해하지 않도록 팝업을 즉시 닫는다.
            self._listbox.bind("<Button-1>", self._on_listbox_click)

        matches = matches[: self.MAX_ITEMS]
        self._listbox.delete(0, tk.END)
        for m in matches:
            self._listbox.insert(tk.END, m)

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = max(self.winfo_width(), 160)
        h = len(matches) * self.ITEM_H
        self._popup.geometry(f"{w}x{h}+{x}+{y}")
        self._popup.deiconify()
        self._popup.lift()

    def _on_listbox_click(self, event):
        idx = self._listbox.nearest(event.y)
        if idx is not None and idx >= 0:
            value = self._listbox.get(idx)
            self._var.set(value)
            self.icursor(tk.END)
        self.after(10, self._close_popup)

    def _on_focus_out(self, event):
        # 리스트박스 클릭 처리(Button-1)가 먼저 끝나도록 살짝 지연 후 닫는다.
        self.after(150, self._close_popup)

    def _close_popup(self):
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None
            self._listbox = None


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("라벨 + 테두리 삽입 (2단계 테스트)")
        self.geometry("1460x800")
        self.configure(bg="#242424")

        self._cv_img       = None
        self._cv_result     = None
        self._current_path  = None

        self._scale = 1.0
        self._ox = self._oy = 0

        # [{"cx","cy","hw","hh","angle","thickness"}, ...] (이미지 좌표, angle: 도 단위)
        self._rects        = []
        self._selected_idx  = None
        # ("resize", idx, fixed_pt(img)) | ("rotate", idx, start_angle, start_mouse_angle) | ("move", idx, ix, iy, cx, cy)
        self._drag_mode     = None
        self._pre_drag_snapshot = None

        self._undo_stack = []
        self._redo_stack = []

        self._hospital_list = []
        self._pharma_list   = []

        self._alt_held  = False
        self._ctrl_held = False

        # 파일 목록 (좌측 패널)
        self._folder_files = []
        self._folder_idx   = 0
        self._thumbs        = []
        self._thumb_photos  = []
        self._thumb_gen     = 0
        self._thumb_cache   = {}

        self._build_ui()
        self._setup_dnd()
        self._setup_rotate_keys()
        self._setup_history_keys()
        self.bind_all("<Control-v>", self._on_paste_shortcut)
        self.bind("<Delete>", self._on_key_delete_file)

    # ── UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        B = dict(bg="#3d4043", fg="white", relief="flat", padx=10, pady=4,
                  cursor="hand2", font=("Segoe UI", 9), bd=0,
                  activebackground="#4e5255", activeforeground="white")

        top = tk.Frame(self, bg="#2e2e2e", pady=6)
        top.pack(fill="x")
        tk.Button(top, text="파일 열기", command=self._open_file, **B).pack(side="left", padx=4)
        tk.Button(top, text="폴더 열기", command=self._open_folder, **B).pack(side="left", padx=4)
        tk.Button(top, text="붙여넣기 (Ctrl+V)", command=self._paste_from_clipboard, **B).pack(side="left", padx=4)
        tk.Button(top, text="기준 엑셀 열기", command=self._open_excel, **B).pack(side="left", padx=4)
        self._excel_lbl = tk.Label(top, text="기준 엑셀: 없음 (드래그&드롭으로도 불러올 수 있습니다)",
                                    bg="#2e2e2e", fg="#888", font=("Segoe UI", 9))
        self._excel_lbl.pack(side="left", padx=10)

        self._nav = tk.Frame(top, bg="#2e2e2e")
        tk.Button(self._nav, text="◀", command=self._prev, **B).pack(side="left", padx=2)
        self._nav_lbl = tk.Label(self._nav, text="", bg="#2e2e2e", fg="#aaa",
                                  font=("Segoe UI", 9), width=10)
        self._nav_lbl.pack(side="left")
        tk.Button(self._nav, text="▶", command=self._next, **B).pack(side="left", padx=2)
        self._nav.pack(side="right", padx=8)

        form = tk.Frame(self, bg="#2e2e2e", pady=6)
        form.pack(fill="x")

        self._hospital_var = tk.StringVar()
        self._month_var    = tk.StringVar()
        self._pharma_var    = tk.StringVar()
        self._thick_var     = tk.IntVar(value=4)

        tk.Label(form, text="병원명", bg="#2e2e2e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        self._hospital_cb = AutocompleteEntry(form, textvariable=self._hospital_var, width=14,
                                              font=("Segoe UI", 10))
        self._hospital_cb.pack(side="left")

        tk.Label(form, text="월", bg="#2e2e2e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        self._month_cb = ttk.Combobox(form, textvariable=self._month_var, width=6,
                                       values=MONTHS, font=("Segoe UI", 10))
        self._month_cb.pack(side="left")

        tk.Label(form, text="제약사명", bg="#2e2e2e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        self._pharma_cb = AutocompleteEntry(form, textvariable=self._pharma_var, width=14,
                                            font=("Segoe UI", 10))
        self._pharma_cb.pack(side="left")

        tk.Label(form, text="선택 테두리 두께", bg="#2e2e2e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 2))
        tk.Spinbox(form, from_=1, to=30, textvariable=self._thick_var,
                   width=4, font=("Segoe UI", 10), command=self._on_thickness_change
                   ).pack(side="left")
        self._thick_var.trace_add("write", self._on_thickness_change)

        tk.Button(form, text="+ 테두리 추가", command=self._add_rect, **B).pack(side="left", padx=(14, 4))
        tk.Button(form, text="선택 테두리 삭제", command=self._delete_selected_rect, **B).pack(side="left", padx=4)

        form2 = tk.Frame(self, bg="#2e2e2e", pady=4)
        form2.pack(fill="x")
        tk.Button(form2, text="미리보기 적용", command=self._apply, **B).pack(side="left", padx=10)
        tk.Button(form2, text=f"'{SAVE_FOLDER}' 폴더에 저장", command=self._save, **B).pack(side="left", padx=4)
        tk.Button(form2, text="↶ 실행 취소 (Ctrl+Z)", command=self._undo, **B).pack(side="left", padx=(14, 4))
        tk.Button(form2, text="↷ 다시 실행 (Ctrl+Y)", command=self._redo, **B).pack(side="left", padx=4)
        tk.Button(form2, text="테두리 전체 지우기", command=self._clear_all_rects, **B).pack(side="left", padx=4)

        body = tk.Frame(self, bg="#242424")
        body.pack(fill="both", expand=True, padx=6, pady=6)

        self._build_thumb_panel(body)

        left = tk.Frame(body, bg="#242424")
        left.pack(side="left", fill="both", expand=True, padx=(0, 3))
        tk.Label(left, text="원본  |  몸통 드래그: 이동  /  모서리: 크기 조절  /  모서리 바깥쪽: 회전  /  "
                             "선택 후 ALT+←→: 15°, CTRL+ALT+←→: 5° 회전",
                 bg="#242424", fg="#888", font=("Segoe UI", 9)).pack(anchor="w")
        self._orig_canvas = tk.Canvas(left, bg="#1a1a1a", width=CANVAS_W, height=CANVAS_H,
                                       highlightthickness=1, highlightbackground="#3a3a3a")
        self._orig_canvas.pack(fill="both", expand=True)
        self._orig_canvas.bind("<Button-1>", self._on_canvas_press)
        self._orig_canvas.bind("<B1-Motion>", self._on_canvas_motion)
        self._orig_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self._orig_canvas.bind("<Motion>", self._on_canvas_hover)

        right = tk.Frame(body, bg="#242424")
        right.pack(side="right", fill="both", expand=True, padx=(3, 0))
        tk.Label(right, text="결과 미리보기", bg="#242424", fg="#888",
                 font=("Segoe UI", 9)).pack(anchor="w")
        self._res_canvas = tk.Canvas(right, bg="#1a1a1a", width=CANVAS_W, height=CANVAS_H,
                                      highlightthickness=1, highlightbackground="#3a3a3a")
        self._res_canvas.pack(fill="both", expand=True)

        self._st = tk.Label(self, text="이미지를 열거나 창에 드래그 & 드롭하세요.", bg="#2e2e2e", fg="#888",
                             anchor="w", font=("Segoe UI", 9), padx=8, pady=4)
        self._st.pack(fill="x", side="bottom")

    # ── 좌측 파일 목록 패널 ──────────────────────────────────────────────

    def _build_thumb_panel(self, parent):
        panel = tk.Frame(parent, bg="#1e1e1e", width=THUMB_PANEL_W)
        panel.pack(side="left", fill="y", padx=(0, 4))
        panel.pack_propagate(False)

        hdr_row = tk.Frame(panel, bg="#1e1e1e")
        hdr_row.pack(fill="x")
        self._thumb_hdr = tk.Label(hdr_row, text="파일 목록", bg="#1e1e1e", fg="#555",
                                    font=("Segoe UI", 8), anchor="w", padx=6, pady=3)
        self._thumb_hdr.pack(side="left")
        tk.Button(hdr_row, text="선택삭제", command=self._delete_selected_files,
                  bg="#3d4043", fg="#ddd", relief="flat", padx=5, pady=0,
                  font=("Segoe UI", 7), cursor="hand2", bd=0,
                  activebackground="#6b3a3a", activeforeground="white"
                  ).pack(side="right", padx=4, pady=2)

        inner = tk.Frame(panel, bg="#1e1e1e")
        inner.pack(fill="both", expand=True)

        self._thumb_canvas = tk.Canvas(inner, bg="#1e1e1e", highlightthickness=0, bd=0)
        scr = tk.Scrollbar(inner, orient="vertical", command=self._thumb_canvas.yview)
        self._thumb_canvas.configure(yscrollcommand=scr.set)
        scr.pack(side="right", fill="y")
        self._thumb_canvas.pack(side="left", fill="both", expand=True)

        self._thumb_list = tk.Frame(self._thumb_canvas, bg="#1e1e1e")
        self._thumb_canvas.create_window((0, 0), window=self._thumb_list, anchor="nw")

        self._thumb_list.bind("<Configure>", lambda e: self._thumb_canvas.configure(
            scrollregion=self._thumb_canvas.bbox("all")))
        self._bind_wheel_recursive(panel)

    def _bind_wheel_recursive(self, widget):
        widget.bind("<MouseWheel>", self._on_thumb_wheel)
        for child in widget.winfo_children():
            self._bind_wheel_recursive(child)

    def _on_thumb_wheel(self, event):
        self._thumb_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _rebuild_thumbs(self):
        for w in self._thumb_list.winfo_children():
            w.destroy()
        self._thumbs.clear()
        self._thumb_photos.clear()

        n = len(self._folder_files)
        self._thumb_hdr.config(text=f"파일 목록  {n}개" if n else "파일 목록")
        if not self._folder_files:
            return

        for i, fpath in enumerate(self._folder_files):
            item = self._create_thumb_item(i, fpath)
            self._thumbs.append(item)
            self._thumb_photos.append(None)

        self._highlight_thumb(self._folder_idx)
        self._thumb_canvas.update_idletasks()
        self._thumb_canvas.configure(scrollregion=self._thumb_canvas.bbox("all"))

        self._thumb_gen += 1
        gen = self._thumb_gen

        to_load = []
        for i, fpath in enumerate(self._folder_files):
            cached = self._thumb_cache.get(fpath)
            if cached is not None:
                self._apply_thumb_photo(i, cached, gen)
            else:
                to_load.append(fpath)

        if not to_load:
            return

        def load_all():
            for fpath in to_load:
                if gen != self._thumb_gen:
                    return
                photo = self._make_thumb_photo(fpath)
                if gen != self._thumb_gen:
                    return
                if photo is not None:
                    self._thumb_cache[fpath] = photo
                self.after(0, lambda p=fpath, ph=photo, g=gen: self._apply_thumb_photo_by_path(p, ph, g))

        threading.Thread(target=load_all, daemon=True).start()

    def _remove_thumb_item(self, idx: int):
        if not (0 <= idx < len(self._thumbs)):
            return
        item = self._thumbs.pop(idx)
        self._thumb_photos.pop(idx)
        item["frame"].destroy()
        for it in self._thumbs[idx:]:
            it["idx"] -= 1

        n = len(self._folder_files)
        self._thumb_hdr.config(text=f"파일 목록  {n}개" if n else "파일 목록")
        self._highlight_thumb(self._folder_idx)
        self._thumb_canvas.update_idletasks()
        self._thumb_canvas.configure(scrollregion=self._thumb_canvas.bbox("all"))

    def _create_thumb_item(self, idx: int, fpath: str) -> dict:
        BG = "#252525"
        frame = tk.Frame(self._thumb_list, bg=BG, padx=3, pady=3,
                         cursor="hand2", highlightthickness=0)
        frame.pack(fill="x", padx=2, pady=1)

        img_lbl = tk.Label(frame, bg="#1a1a1a",
                            width=THUMB_W // 8, height=THUMB_H // 16)
        img_lbl.pack(fill="x")

        bot = tk.Frame(frame, bg=BG)
        bot.pack(fill="x", pady=(2, 0))

        name = Path(fpath).name
        if len(name) > 13:
            name = name[:10] + "..."
        name_lbl = tk.Label(bot, text=name, bg=BG, fg="#888",
                             font=("Segoe UI", 7), anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True)

        var = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(bot, variable=var, bg=BG,
                             activebackground=BG, selectcolor="#555",
                             bd=0, highlightthickness=0, padx=0)
        cb.pack(side="right")

        bg_widgets = [frame, img_lbl, bot, name_lbl, cb]
        item = {"frame": frame, "var": var, "img_lbl": img_lbl,
                "bg_widgets": bg_widgets, "idx": idx, "path": fpath}

        for w in (frame, img_lbl, name_lbl):
            w.bind("<Button-1>", lambda e, it=item: self._select_file(it["idx"]))
            w.bind("<Button-3>", lambda e, it=item: self._thumb_context_menu(e, it["idx"]))

        self._bind_wheel_recursive(frame)
        return item

    def _make_thumb_photo(self, fpath: str):
        try:
            buf = np.fromfile(fpath, dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if img is None:
                return None
            h, w   = img.shape[:2]
            scale  = min(THUMB_W / w, THUMB_H / h)
            nh, nw = max(1, int(h * scale)), max(1, int(w * scale))
            small  = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
            rgb    = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            return ImageTk.PhotoImage(Image.fromarray(rgb))
        except Exception:
            return None

    def _apply_thumb_photo(self, idx: int, photo, gen: int):
        if gen != self._thumb_gen or idx >= len(self._thumbs) or photo is None:
            return
        self._thumb_photos[idx] = photo
        self._thumbs[idx]["img_lbl"].configure(image=photo, width=0, height=0)
        self._thumb_canvas.configure(scrollregion=self._thumb_canvas.bbox("all"))

    def _apply_thumb_photo_by_path(self, path: str, photo, gen: int):
        if gen != self._thumb_gen or photo is None:
            return
        for i, item in enumerate(self._thumbs):
            if item["path"] == path:
                self._apply_thumb_photo(i, photo, gen)
                return

    def _highlight_thumb(self, idx: int):
        for i, item in enumerate(self._thumbs):
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

    def _scroll_to_active_thumb(self):
        idx = self._folder_idx
        if not self._thumbs or idx >= len(self._thumbs):
            return
        frame   = self._thumbs[idx]["frame"]
        self._thumb_list.update_idletasks()
        total_h = self._thumb_list.winfo_reqheight()
        if total_h <= 0:
            return
        y       = frame.winfo_y()
        h       = frame.winfo_height()
        view    = self._thumb_canvas.yview()
        vis_top = view[0] * total_h
        vis_bot = vis_top + self._thumb_canvas.winfo_height()
        if y < vis_top:
            self._thumb_canvas.yview_moveto(y / total_h)
        elif y + h > vis_bot:
            self._thumb_canvas.yview_moveto(
                max(0, (y + h - self._thumb_canvas.winfo_height()) / total_h))

    def _thumb_context_menu(self, event, idx: int):
        if not (0 <= idx < len(self._folder_files)):
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="탐색기에서 열기", command=lambda: self._open_in_explorer(self._folder_files[idx]))
        menu.add_command(label="목록에서 삭제", command=lambda: self._remove_file(idx))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _open_in_explorer(self, fpath: str):
        subprocess.Popen(f'explorer /select,"{fpath}"', shell=True)

    def _remove_file(self, idx: int):
        if not self._folder_files or not (0 <= idx < len(self._folder_files)):
            return
        active = self._folder_idx
        self._thumb_cache.pop(self._folder_files[idx], None)
        self._folder_files.pop(idx)
        if not self._folder_files:
            self._folder_idx = 0
            self._cv_img     = None
            self._cv_result  = None
            self._current_path = None
            self._rects.clear()
            self._selected_idx = None
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._orig_canvas.delete("all")
            self._res_canvas.delete("all")
            self._st.config(text="파일을 열거나 창에 드래그 & 드롭하세요.")
            self._nav.pack_forget()
            self._rebuild_thumbs()
            return

        if idx == active:
            self._folder_idx = min(idx, len(self._folder_files) - 1)
            reload_preview = True
        else:
            self._folder_idx = active - 1 if idx < active else active
            reload_preview = False

        if reload_preview:
            self._load_image(self._folder_files[self._folder_idx])
        self._update_nav()
        self._remove_thumb_item(idx)

    def _on_key_delete_file(self, event):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Spinbox, ttk.Entry)):
            return
        if self._folder_files and 0 <= self._folder_idx < len(self._folder_files):
            self._remove_file(self._folder_idx)

    def _delete_selected_files(self):
        idxs = [i for i, item in enumerate(self._thumbs) if item["var"].get()]
        if not idxs:
            messagebox.showinfo("알림", "선택된 파일이 없습니다.\n썸네일 체크박스를 확인해 주세요.")
            return
        if not messagebox.askyesno(
                "선택 삭제",
                f"체크된 {len(idxs)}개 파일을 목록에서 삭제할까요?\n"
                f"(실제 파일은 삭제되지 않고, 목록에서만 제외됩니다)"):
            return
        for i in sorted(idxs, reverse=True):
            self._remove_file(i)

    def _update_nav(self):
        self._nav_lbl.config(text=f"{self._folder_idx + 1} / {len(self._folder_files)}")

    def _select_file(self, idx: int):
        if not self._folder_files or not (0 <= idx < len(self._folder_files)):
            return
        self._folder_idx = idx
        self._update_nav()
        self._highlight_thumb(idx)
        self._scroll_to_active_thumb()
        self._load_image(self._folder_files[idx])

    def _prev(self):
        self._select_file(self._folder_idx - 1)

    def _next(self):
        self._select_file(self._folder_idx + 1)

    # ── 키보드 회전 (ALT+←→: 15°, CTRL+ALT+←→: 5°) ────────────────────────

    def _setup_rotate_keys(self):
        def set_alt(v):
            self._alt_held = v
        def set_ctrl(v):
            self._ctrl_held = v

        for key in ("Alt_L", "Alt_R"):
            self.bind_all(f"<KeyPress-{key}>", lambda e: set_alt(True))
            self.bind_all(f"<KeyRelease-{key}>", lambda e: set_alt(False))
        for key in ("Control_L", "Control_R"):
            self.bind_all(f"<KeyPress-{key}>", lambda e: set_ctrl(True))
            self.bind_all(f"<KeyRelease-{key}>", lambda e: set_ctrl(False))

        self.bind_all("<Left>", self._on_key_rotate)
        self.bind_all("<Right>", self._on_key_rotate)

    def _on_key_rotate(self, event):
        if not self._alt_held or self._selected_idx is None:
            return None
        step = 5 if self._ctrl_held else 15
        if event.keysym == "Left":
            step = -step
        self._push_undo()
        r = self._rects[self._selected_idx]
        r["angle"] = (r["angle"] + step) % 360
        self._draw_rect_overlay()
        self._apply(silent=True)
        return "break"

    # ── 실행 취소 / 다시 실행 ─────────────────────────────────────────────

    def _setup_history_keys(self):
        self.bind_all("<Control-z>", self._undo)
        self.bind_all("<Control-y>", self._redo)
        self.bind_all("<Control-Z>", self._redo)   # Ctrl+Shift+Z

    def _snapshot(self):
        return [dict(r) for r in self._rects]

    def _push_undo(self):
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > UNDO_LIMIT:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _restore(self, snapshot):
        self._rects = [dict(r) for r in snapshot]
        self._selected_idx = None
        self._draw_rect_overlay()
        self._apply(silent=True)

    def _undo(self, event=None):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Spinbox, ttk.Entry)):
            return None
        if not self._undo_stack:
            self._st.config(text="더 되돌릴 내용이 없습니다.")
            return "break"
        self._redo_stack.append(self._snapshot())
        prev = self._undo_stack.pop()
        self._restore(prev)
        self._st.config(text=f"실행 취소함 (테두리 {len(self._rects)}개)")
        return "break"

    def _redo(self, event=None):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Spinbox, ttk.Entry)):
            return None
        if not self._redo_stack:
            self._st.config(text="다시 실행할 내용이 없습니다.")
            return "break"
        self._undo_stack.append(self._snapshot())
        nxt = self._redo_stack.pop()
        self._restore(nxt)
        self._st.config(text=f"다시 실행함 (테두리 {len(self._rects)}개)")
        return "break"

    def _clear_all_rects(self):
        if not self._rects:
            return
        self._push_undo()
        self._rects.clear()
        self._selected_idx = None
        self._draw_rect_overlay()
        self._apply(silent=True)
        self._st.config(text="테두리를 모두 지웠습니다.")

    # ── DnD ─────────────────────────────────────────────────────────────

    def _setup_dnd(self):
        for w in (self, self._orig_canvas, self._res_canvas):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event):
        files = self.tk.splitlist(event.data)
        images = [f for f in files if Path(f).suffix.lower() in IMAGE_EXT]
        excels = [f for f in files if Path(f).suffix.lower() in EXCEL_EXT]
        others = [f for f in files if f not in images and f not in excels]

        if images:
            self._add_files(images)
        if excels:
            self._load_excel(excels[0])
        if others:
            self._st.config(text=f"지원하지 않는 파일 형식: {Path(others[0]).name}")

    # ── 파일 열기 (이미지) ────────────────────────────────────────────────

    def _open_file(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("이미지", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp"),
                       ("모든 파일", "*.*")])
        if paths:
            self._add_files(list(paths))

    def _open_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        files = sorted(str(f) for f in Path(folder).iterdir()
                       if f.suffix.lower() in IMAGE_EXT)
        if not files:
            messagebox.showinfo("알림", "지원하는 이미지가 없습니다.")
            return
        self._add_files(files)

    def _add_files(self, new_paths: list):
        existing = set(self._folder_files)
        to_add   = [p for p in new_paths if p not in existing]
        if not to_add:
            self._st.config(text="추가할 새 파일이 없습니다. (모두 이미 목록에 있음)")
            return
        first_new = len(self._folder_files)
        self._folder_files.extend(to_add)
        self._folder_idx = first_new
        if len(self._folder_files) > 1:
            self._nav.pack(side="right", padx=8)
        self._load_image(self._folder_files[first_new])
        self._update_nav()
        self._rebuild_thumbs()

    def _load_image(self, path: str):
        img = read_image(path)
        if img is None:
            messagebox.showerror("오류", "이미지를 읽을 수 없습니다.")
            return

        self._current_path = path
        self._cv_img    = img
        self._cv_result = None
        self._rects.clear()
        self._selected_idx = None
        self._undo_stack.clear()
        self._redo_stack.clear()

        fields = parse_filename(path)
        if fields:
            self._hospital_var.set(fields["hospital"])
            self._month_var.set(fields["month"])
            self._pharma_var.set(fields["pharma"])
            self._st.config(text=f"파일명에서 자동 인식: {build_label(**fields)}")
        else:
            self._hospital_var.set("")
            self._month_var.set("")
            self._pharma_var.set("")
            self._st.config(text="파일명에서 자동 인식 실패 — 병원명/월/제약사명을 직접 입력하세요.")

        self._render_original()
        self._res_canvas.delete("all")

    # ── 클립보드 붙여넣기 ────────────────────────────────────────────────

    def _on_paste_shortcut(self, event):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Spinbox, ttk.Entry)):
            return None   # 입력창에서의 Ctrl+V는 기본 텍스트 붙여넣기 동작에 맡긴다
        self._paste_from_clipboard()
        return "break"

    def _paste_from_clipboard(self):
        try:
            data = ImageGrab.grabclipboard()
        except Exception as e:
            messagebox.showerror("오류", f"클립보드를 읽을 수 없습니다: {e}")
            return

        if isinstance(data, list) and data:
            images = [f for f in data if Path(f).suffix.lower() in IMAGE_EXT]
            if images:
                self._add_files(images)
                return
            self._st.config(text="클립보드의 파일 중 지원하는 이미지가 없습니다.")
            return

        if data is None:
            self._st.config(text="클립보드에 이미지가 없습니다.")
            return

        rgb = np.array(data.convert("RGB"))
        img = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        self._load_clipboard_image(img)

    def _load_clipboard_image(self, img):
        self._current_path = None
        self._cv_img    = img
        self._cv_result = None
        self._rects.clear()
        self._selected_idx = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._hospital_var.set("")
        self._month_var.set("")
        self._pharma_var.set("")
        self._st.config(text="클립보드에서 이미지를 붙여넣었습니다 — 병원명/월/제약사명을 입력하세요. "
                              "(파일명이 없어 저장 시 위치를 직접 지정합니다)")
        self._render_original()
        self._res_canvas.delete("all")

    # ── 기준 엑셀 ────────────────────────────────────────────────────────

    def _open_excel(self):
        p = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xlsm")])
        if p:
            self._load_excel(p)

    def _load_excel(self, path: str):
        try:
            hospitals, pharmas = load_reference_excel(path)
        except Exception as e:
            messagebox.showerror("오류", f"엑셀을 읽을 수 없습니다: {e}")
            return
        self._hospital_list = hospitals
        self._pharma_list   = pharmas
        self._hospital_cb.set_candidates(hospitals)
        self._pharma_cb.set_candidates(pharmas)
        self._excel_lbl.config(
            text=f"기준 엑셀: {Path(path).name}  (병원 {len(hospitals)}개 / 제약사 {len(pharmas)}개)")
        self._st.config(text="기준 엑셀 로드 완료 — 병원명/제약사명에 2글자 이상 입력하면 목록이 좁혀집니다.")

    # ── 원본 캔버스 렌더링 ────────────────────────────────────────────────

    def _render_original(self):
        self._orig_canvas.delete("all")
        if self._cv_img is None:
            return
        h, w = self._cv_img.shape[:2]
        self._scale = min((CANVAS_W - 4) / w, (CANVAS_H - 4) / h)
        nw, nh = max(1, int(w * self._scale)), max(1, int(h * self._scale))
        self._ox = (CANVAS_W - nw) // 2
        self._oy = (CANVAS_H - nh) // 2

        resized = cv2.resize(self._cv_img, (nw, nh), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        self._tk_orig = ImageTk.PhotoImage(Image.fromarray(rgb))
        self._orig_canvas.create_image(self._ox, self._oy, anchor="nw", image=self._tk_orig)
        self._draw_rect_overlay()

    # ── 좌표 변환 ───────────────────────────────────────────────────────

    def _image_to_canvas(self, ix, iy):
        return ix * self._scale + self._ox, iy * self._scale + self._oy

    def _canvas_to_image(self, cx, cy):
        return (cx - self._ox) / self._scale, (cy - self._oy) / self._scale

    # ── 테두리 오버레이 렌더링 ───────────────────────────────────────────

    def _draw_rect_overlay(self):
        self._orig_canvas.delete("rect_overlay")
        if self._cv_img is None:
            return
        for idx, r in enumerate(self._rects):
            corners = [self._image_to_canvas(x, y) for x, y in rect_corners(r)]
            selected = (idx == self._selected_idx)
            outline = "#FFDD33" if selected else "#FF4444"
            flat = [v for p in corners for v in p]
            self._orig_canvas.create_polygon(*flat, outline=outline, fill="",
                                              width=2, tags="rect_overlay")
            for hx, hy in corners:
                fill = "#FFDD33" if selected else "white"
                self._orig_canvas.create_rectangle(
                    hx - HANDLE_R, hy - HANDLE_R, hx + HANDLE_R, hy + HANDLE_R,
                    fill=fill, outline="#333", tags="rect_overlay")

    # ── 테두리 히트테스트 ────────────────────────────────────────────────

    def _hit_zone(self, r, cx, cy):
        """corner 근처 히트테스트. ("resize"|"rotate", corner_idx) 또는 None."""
        for i, (ix, iy) in enumerate(rect_corners(r)):
            px, py = self._image_to_canvas(ix, iy)
            dist = math.hypot(px - cx, py - cy)
            if dist <= RESIZE_HIT:
                return "resize", i
            if dist <= ROTATE_HIT:
                return "rotate", i
        return None

    def _point_in_rect(self, r, cx, cy):
        ix, iy = self._canvas_to_image(cx, cy)
        a = math.radians(r.get("angle", 0.0))
        dx, dy = ix - r["cx"], iy - r["cy"]
        cos_a, sin_a = math.cos(-a), math.sin(-a)
        lx = dx * cos_a - dy * sin_a
        ly = dx * sin_a + dy * cos_a
        return abs(lx) <= r["hw"] and abs(ly) <= r["hh"]

    # ── 테두리 추가/삭제 ─────────────────────────────────────────────────

    def _add_rect(self):
        if self._cv_img is None:
            messagebox.showwarning("알림", "먼저 이미지를 열어주세요.")
            return
        self._push_undo()
        h, w = self._cv_img.shape[:2]
        self._rects.append({
            "cx": w / 2, "cy": h / 2,
            "hw": w * 0.125, "hh": h * 0.125,
            "angle": 0.0,
            "thickness": self._thick_var.get(),
        })
        self._selected_idx = len(self._rects) - 1
        self._draw_rect_overlay()
        self._apply(silent=True)

    def _delete_selected_rect(self):
        if self._selected_idx is None:
            messagebox.showinfo("알림", "선택된 테두리가 없습니다. 테두리를 클릭해 선택하세요.")
            return
        self._push_undo()
        del self._rects[self._selected_idx]
        self._selected_idx = None
        self._draw_rect_overlay()
        self._apply(silent=True)

    def _sync_thickness_spinbox(self):
        if self._selected_idx is not None:
            self._thick_var.set(self._rects[self._selected_idx]["thickness"])

    def _on_thickness_change(self, *args):
        if self._selected_idx is not None and 0 <= self._selected_idx < len(self._rects):
            try:
                self._rects[self._selected_idx]["thickness"] = self._thick_var.get()
            except tk.TclError:
                return
            self._draw_rect_overlay()

    # ── 테두리 드래그(이동/리사이즈/회전) ─────────────────────────────────

    def _on_canvas_press(self, event):
        if self._cv_img is None:
            return

        for idx in reversed(range(len(self._rects))):
            zone = self._hit_zone(self._rects[idx], event.x, event.y)
            if zone is None:
                continue
            kind, corner_idx = zone
            r = self._rects[idx]
            self._selected_idx = idx
            self._pre_drag_snapshot = self._snapshot()
            if kind == "resize":
                fixed_pt = rect_corners(r)[(corner_idx + 2) % 4]   # 대각선 반대쪽 꼭짓점(고정)
                self._drag_mode = ("resize", idx, fixed_pt)
            else:  # rotate
                start_mouse_angle = math.degrees(math.atan2(
                    event.y - self._image_to_canvas(r["cx"], r["cy"])[1],
                    event.x - self._image_to_canvas(r["cx"], r["cy"])[0]))
                self._drag_mode = ("rotate", idx, r["angle"], start_mouse_angle)
            self._sync_thickness_spinbox()
            self._draw_rect_overlay()
            return

        for idx in reversed(range(len(self._rects))):
            if self._point_in_rect(self._rects[idx], event.x, event.y):
                r = self._rects[idx]
                ix, iy = self._canvas_to_image(event.x, event.y)
                self._selected_idx = idx
                self._pre_drag_snapshot = self._snapshot()
                self._drag_mode = ("move", idx, ix, iy, r["cx"], r["cy"])
                self._sync_thickness_spinbox()
                self._draw_rect_overlay()
                return

        self._selected_idx = None
        self._drag_mode = None
        self._draw_rect_overlay()

    def _on_canvas_motion(self, event):
        if not self._drag_mode:
            return
        mode, idx = self._drag_mode[0], self._drag_mode[1]
        r = self._rects[idx]
        ix, iy = self._canvas_to_image(event.x, event.y)

        if mode == "resize":
            fx, fy = self._drag_mode[2]
            a = math.radians(r.get("angle", 0.0))
            u = (math.cos(a), math.sin(a))
            v = (-math.sin(a), math.cos(a))
            dx, dy = ix - fx, iy - fy
            new_hw = abs(dx * u[0] + dy * u[1]) / 2
            new_hh = abs(dx * v[0] + dy * v[1]) / 2
            r["hw"] = max(MIN_HALF, new_hw)
            r["hh"] = max(MIN_HALF, new_hh)
            r["cx"] = (fx + ix) / 2
            r["cy"] = (fy + iy) / 2

        elif mode == "rotate":
            _, _, start_angle, start_mouse_angle = self._drag_mode
            ccx, ccy = self._image_to_canvas(r["cx"], r["cy"])
            cur_mouse_angle = math.degrees(math.atan2(event.y - ccy, event.x - ccx))
            new_angle = start_angle + (cur_mouse_angle - start_mouse_angle)
            if self._alt_held:
                step = 5 if self._ctrl_held else 15
                new_angle = round(new_angle / step) * step
            r["angle"] = new_angle % 360

        else:  # move
            _, _, start_ix, start_iy, ocx, ocy = self._drag_mode
            h_img, w_img = self._cv_img.shape[:2]
            r["cx"] = max(0.0, min(float(w_img), ocx + (ix - start_ix)))
            r["cy"] = max(0.0, min(float(h_img), ocy + (iy - start_iy)))

        self._draw_rect_overlay()

    def _on_canvas_release(self, event):
        had_drag = self._drag_mode is not None
        self._drag_mode = None
        if had_drag:
            if self._pre_drag_snapshot is not None and self._pre_drag_snapshot != self._rects:
                self._undo_stack.append(self._pre_drag_snapshot)
                if len(self._undo_stack) > UNDO_LIMIT:
                    self._undo_stack.pop(0)
                self._redo_stack.clear()
            self._pre_drag_snapshot = None
            self._apply(silent=True)   # 테두리 조작이 끝나면 바로 결과 미리보기 갱신

    def _on_canvas_hover(self, event):
        if self._drag_mode or self._cv_img is None:
            return
        for r in reversed(self._rects):
            zone = self._hit_zone(r, event.x, event.y)
            if zone:
                kind, _ = zone
                self._orig_canvas.configure(cursor="sizing" if kind == "resize" else "exchange")
                return
            if self._point_in_rect(r, event.x, event.y):
                self._orig_canvas.configure(cursor="fleur")
                return
        self._orig_canvas.configure(cursor="")

    # ── 미리보기 & 저장 ──────────────────────────────────────────────────

    def _apply(self, silent=False):
        if self._cv_img is None:
            if not silent:
                messagebox.showwarning("알림", "먼저 이미지를 열어주세요.")
            return
        hospital = self._hospital_var.get().strip()
        month    = self._month_var.get().strip()
        pharma   = self._pharma_var.get().strip()
        if not (hospital and month and pharma):
            if not silent:
                messagebox.showwarning("알림", "병원명 / 월 / 제약사명을 모두 입력해주세요.")
            return

        label = build_label(hospital, month, pharma)
        self._cv_result = annotate_image(self._cv_img, label, rects=self._rects)
        self._render_result()
        self._st.config(text=f"미리보기 적용됨: {label}  (테두리 {len(self._rects)}개)")

    def _render_result(self):
        self._res_canvas.delete("all")
        if self._cv_result is None:
            return
        h, w = self._cv_result.shape[:2]
        scale = min((CANVAS_W - 4) / w, (CANVAS_H - 4) / h)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        ox, oy = (CANVAS_W - nw) // 2, (CANVAS_H - nh) // 2

        resized = cv2.resize(self._cv_result, (nw, nh), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        self._tk_res = ImageTk.PhotoImage(Image.fromarray(rgb))
        self._res_canvas.create_image(ox, oy, anchor="nw", image=self._tk_res)

    def _save(self):
        if self._cv_result is None:
            messagebox.showwarning("알림", "먼저 '미리보기 적용'으로 결과를 만들어주세요.")
            return

        if self._current_path:
            p = Path(self._current_path)
            out_dir = p.parent / SAVE_FOLDER
            out_dir.mkdir(exist_ok=True)
            out = unique_path(out_dir, p.stem, p.suffix)
        else:
            # 클립보드에서 붙여넣은 이미지 등 원본 경로가 없는 경우 저장 위치를 직접 지정
            path = filedialog.asksaveasfilename(
                defaultextension=".png", initialfile="붙여넣은이미지",
                filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("모든 파일", "*.*")])
            if not path:
                return
            out = Path(path)

        if write_image(str(out), self._cv_result):
            self._st.config(text=f"저장됨: {out}")
        else:
            messagebox.showerror("오류", "저장 실패")


if __name__ == "__main__":
    App().mainloop()
