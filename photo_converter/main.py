"""사진 원근 보정 프로그램."""
import ctypes
import io
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import cv2
import numpy as np
from PIL import Image, ImageTk
import threading
from pathlib import Path

from converter import auto_detect_corners, process_image
from imageio_utils import read_image, write_image, unique_path
from thumb_panel import ThumbPanel
from file_list_controller import FileListController

SUPPORTED_EXT      = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
SAVE_FOLDER        = "변환파일"
POINT_COLORS       = ["#FF5555", "#55DD55", "#5599FF", "#FFEE44"]
DEBOUNCE_MS        = 60
DOUBLE_CLICK_MS    = 400
ZOOM_MIN, ZOOM_MAX = 0.3, 15.0


# ── 드래그 가능한 이미지 캔버스 ──────────────────────────────────────────

class ImageCanvas(tk.Canvas):
    """
    이미지 표시 + 꼭짓점 드래그 + 창 리사이즈 대응 + 휠 줌 & 중간버튼 패닝.
    - 창 크기 변경 시 이미지 자동 재렌더링 (50ms 디바운스)
    - 스크롤 휠: 마우스 위치 기준 줌인/아웃
    - 중간 버튼 드래그: 패닝
    - 더블클릭: 줌·패닝 초기화
    """

    def __init__(self, parent, label: str, on_change=None, pannable=True, **kw):
        super().__init__(parent, bg="#1a1a1a", highlightthickness=1,
                         highlightbackground="#3a3a3a", **kw)
        self._label     = label
        self._on_change = on_change
        self._pannable  = pannable

        self._cv_img     = None
        self._tk_img     = None
        self._hint_text  = None

        self._base_scale = 1.0
        self._scale      = 1.0
        self._ox = self._oy = 0

        self._zoom       = 1.0
        self._pan_x      = 0.0
        self._pan_y      = 0.0
        self._pan_anchor = None

        self._pts: list[list[float]] = []
        self._drag_idx = None
        self._resize_job = None

        self._pts_before_click = None   # 더블클릭(뷰 초기화) 판별용 스냅샷
        self._last_click_time  = 0

        self.bind("<Configure>",       self._on_configure)
        self.bind("<Button-1>",        self._drag_start)
        self.bind("<B1-Motion>",       self._drag_motion)
        self.bind("<ButtonRelease-1>", self._drag_end)
        self.bind("<Double-Button-1>", self._on_double_click)
        self.bind("<Motion>",          self._hover)
        if self._pannable:
            self.bind("<MouseWheel>",      self._on_scroll)
            self.bind("<Button-2>",        self._pan_start)
            self.bind("<B2-Motion>",       self._pan_motion)

        self._draw_label()

    # ── 공개 API ────────────────────────────────────────────────────────

    def show(self, cv_img, pts=None, reset_view=False):
        self._cv_img    = cv_img
        self._hint_text = None
        if pts is not None:
            self._pts = [list(p) for p in pts]
        if reset_view:
            self._zoom, self._pan_x, self._pan_y = 1.0, 0.0, 0.0
        self._render()

    def set_points(self, pts):
        self._pts = [list(p) for p in pts]
        self._redraw()

    def get_points(self):
        return self._pts

    def show_hint(self, text="이미지를 여기에 드래그 & 드롭"):
        self._cv_img    = None
        self._tk_img    = None
        self._hint_text = text
        self._pts       = []
        self._render()

    def clear(self):
        self._cv_img = self._tk_img = self._hint_text = None
        self._pts = []
        self.delete("all")
        self._draw_label()

    def reset_view(self, event=None):
        """줌/패닝만 초기 상태로 되돌린다 (꼭짓점 위치는 건드리지 않음)."""
        self._zoom, self._pan_x, self._pan_y = 1.0, 0.0, 0.0
        self._render()

    def _on_double_click(self, event):
        # 더블클릭의 두 번의 클릭 각각이 _drag_start를 거치며 근처 꼭짓점을
        # 클릭 위치로 스냅시킬 수 있으므로, 더블클릭 직전 상태로 점 위치도 복원한다.
        if self._pts_before_click is not None and self._pts_before_click != self._pts:
            self._pts = [list(p) for p in self._pts_before_click]
            if self._on_change:
                self._on_change(self._pts)
        self.reset_view()

    # ── 렌더링 ──────────────────────────────────────────────────────────

    def _render(self):
        self.update_idletasks()
        cw = max(self.winfo_width(),  200)
        ch = max(self.winfo_height(), 200)

        self.delete("all")

        if self._hint_text or self._cv_img is None:
            if self._hint_text:
                self.create_text(cw // 2, ch // 2,
                                 text=self._hint_text,
                                 fill="#444", font=("Segoe UI", 14))
            self._draw_label()
            return

        h, w    = self._cv_img.shape[:2]
        avail_w = cw - 4
        avail_h = ch - 28

        self._base_scale = min(avail_w / w, avail_h / h)
        eff  = self._base_scale * self._zoom
        nw   = max(1, int(w * eff))
        nh   = max(1, int(h * eff))

        cx = max(2, (avail_w - nw) // 2) + 2
        cy = max(0, (avail_h - nh) // 2) + 26

        self._ox    = cx + int(self._pan_x)
        self._oy    = cy + int(self._pan_y)
        self._scale = eff

        resized = cv2.resize(self._cv_img, (nw, nh), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        self._tk_img = ImageTk.PhotoImage(Image.fromarray(rgb))

        self._draw_label()
        self.create_image(self._ox, self._oy, anchor="nw", image=self._tk_img)
        if len(self._pts) == 4:
            self._draw_overlay()

    def _redraw(self):
        self.delete("all")
        self._draw_label()
        if self._tk_img is not None:
            self.create_image(self._ox, self._oy, anchor="nw", image=self._tk_img)
        if len(self._pts) == 4 and self._scale > 0:
            self._draw_overlay()

    def _draw_label(self):
        self.create_text(10, 10, anchor="nw", text=self._label,
                         fill="#555", font=("Segoe UI", 9))

    def _to_canvas(self, ix, iy):
        return ix * self._scale + self._ox, iy * self._scale + self._oy

    def _canvas_pts(self):
        return [self._to_canvas(px, py) for px, py in self._pts]

    def _draw_overlay(self):
        cpts = self._canvas_pts()
        flat = [v for p in cpts for v in p]
        self.create_polygon(*flat, outline="#00DDDD", fill="", width=2, dash=(8, 4))
        for i, (cx, cy) in enumerate(cpts):
            r = 11 if i == self._drag_idx else 9
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             fill=POINT_COLORS[i], outline="white",
                             width=3 if i == self._drag_idx else 2)
            self.create_text(cx, cy, text=str(i + 1),
                             fill="black", font=("Arial", 8, "bold"))

    # ── 리사이즈 ────────────────────────────────────────────────────────

    def _on_configure(self, event):
        if self._cv_img is None and not self._hint_text:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(50, self._render)

    # ── 드래그 ──────────────────────────────────────────────────────────

    def _img_coord(self, cx, cy):
        if self._scale <= 0 or self._cv_img is None:
            return None
        h, w = self._cv_img.shape[:2]
        ix = max(0.0, min(float(w), (cx - self._ox) / self._scale))
        iy = max(0.0, min(float(h), (cy - self._oy) / self._scale))
        return ix, iy

    def _closest_idx(self, cx, cy):
        """캔버스 어디를 클릭하든 4개 꼭짓점 중 가장 가까운 것의 인덱스."""
        pts = self._canvas_pts()
        if not pts:
            return None
        return min(range(len(pts)), key=lambda i: (cx - pts[i][0]) ** 2 + (cy - pts[i][1]) ** 2)

    def _drag_start(self, event):
        # 더블클릭(뷰 초기화) 판별: 직전 클릭과 짧은 시간 안이면 같은 제스처로 보고
        # 스냅샷을 유지, 아니면 새 클릭 시퀀스로 보고 지금 상태를 스냅샷한다.
        if event.time - self._last_click_time > DOUBLE_CLICK_MS:
            self._pts_before_click = [list(p) for p in self._pts]
        self._last_click_time = event.time

        idx = None
        if len(self._pts) == 4:
            # 어디를 클릭해도 가장 가까운 꼭짓점을 클릭 위치로 즉시 이동
            idx = self._closest_idx(event.x, event.y)
            coord = self._img_coord(event.x, event.y)
            if coord:
                self._pts[idx] = list(coord)
                self._redraw()
                if self._on_change:
                    self._on_change(self._pts)
        self._drag_idx = idx

        if idx is None and self._pannable:
            # 꼭짓점이 4개가 아니면(=조정 대상 없음) 왼쪽 버튼 드래그로 화면을 이동(패닝)
            self._pan_anchor = (event.x - self._pan_x, event.y - self._pan_y)

    def _drag_motion(self, event):
        if self._drag_idx is not None and self._pts:
            coord = self._img_coord(event.x, event.y)
            if coord:
                self._pts[self._drag_idx] = list(coord)
                self._redraw()
                if self._on_change:
                    self._on_change(self._pts)
            return
        if self._pan_anchor is not None:
            self._pan_x = event.x - self._pan_anchor[0]
            self._pan_y = event.y - self._pan_anchor[1]
            self._render()

    def _drag_end(self, event):
        self._drag_idx   = None
        self._pan_anchor = None
        self._redraw()

    def _hover(self, event):
        if len(self._pts) == 4:
            self.configure(cursor="fleur")
        elif self._cv_img is not None:
            self.configure(cursor="hand2")
        else:
            self.configure(cursor="")

    # ── 줌 & 패닝 ───────────────────────────────────────────────────────

    def _on_scroll(self, event):
        if self._cv_img is None:
            return
        old = self._img_coord(event.x, event.y)
        if old is None:
            return
        ix, iy = old

        factor     = 1.2 if event.delta > 0 else 1 / 1.2
        self._zoom = max(ZOOM_MIN, min(ZOOM_MAX, self._zoom * factor))

        self.update_idletasks()
        cw, ch = max(self.winfo_width(), 200), max(self.winfo_height(), 200)
        h, w   = self._cv_img.shape[:2]
        new_eff = self._base_scale * self._zoom
        nw, nh  = max(1, int(w * new_eff)), max(1, int(h * new_eff))
        new_cx  = max(2, (cw - 4 - nw) // 2) + 2
        new_cy  = max(0, (ch - 28 - nh) // 2) + 26

        self._pan_x = event.x - new_cx - ix * new_eff
        self._pan_y = event.y - new_cy - iy * new_eff

        self._render()

    def _pan_start(self, event):
        self._pan_anchor = (event.x - self._pan_x, event.y - self._pan_y)

    def _pan_motion(self, event):
        if self._pan_anchor is None:
            return
        self._pan_x = event.x - self._pan_anchor[0]
        self._pan_y = event.y - self._pan_anchor[1]
        self._render()


# ── 메인 앱 ─────────────────────────────────────────────────────────────

class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("사진 원근 보정")
        self.geometry("1360x750")
        self.configure(bg="#242424")
        self.resizable(True, True)

        self._cv_orig       = None
        self._cv_result     = None
        self._current_path  = None
        self._transform_job = None

        self._build_ui()

        self._files = FileListController(
            self._thumb_panel,
            on_load=self._load,
            on_empty=self._on_files_empty,
            nav=self._nav,
            nav_label=self._nav_lbl,
            status=lambda t: self._st.config(text=t),
        )

        self._setup_dnd()
        self.bind("<Delete>", self._on_key_delete)
        self.after(120, self._show_hint)

    # ── UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        tb = tk.Frame(self, bg="#2e2e2e", pady=6)
        tb.pack(fill="x")

        B = dict(bg="#3d4043", fg="white", relief="flat",
                 padx=11, pady=4, cursor="hand2",
                 font=("Segoe UI", 9), bd=0,
                 activebackground="#4e5255", activeforeground="white")

        tk.Button(tb, text="파일 열기",  command=self._open_file,   **B).pack(side="left", padx=4)
        tk.Button(tb, text="폴더 열기",  command=self._open_folder, **B).pack(side="left", padx=4)
        _sep(tb)
        tk.Button(tb, text="재감지",     command=self._redetect,    **B).pack(side="left", padx=4)
        tk.Button(tb, text="변환 적용",  command=self._apply,       **B).pack(side="left", padx=4)
        _sep(tb)
        tk.Button(tb, text="변환파일 폴더에 저장", command=self._save,             **B).pack(side="left", padx=4)
        tk.Button(tb, text="위치 지정 저장",       command=self._save_as,          **B).pack(side="left", padx=4)
        tk.Button(tb, text="클립보드 복사",        command=self._copy_to_clipboard,**B).pack(side="left", padx=4)
        _sep(tb)
        tk.Button(tb, text="↺ 좌회전", command=self._rotate_left,  **B).pack(side="left", padx=4)
        tk.Button(tb, text="↻ 우회전", command=self._rotate_right, **B).pack(side="left", padx=4)
        _sep(tb)
        tk.Button(tb, text="원래대로", command=self._reset_views, **B).pack(side="left", padx=4)

        # 배치 네비 (폴더·다중 파일 로드 시 표시)
        self._nav = tk.Frame(tb, bg="#2e2e2e")
        tk.Button(self._nav, text="◀", command=lambda: self._files.prev(), **B).pack(side="left", padx=2)
        self._nav_lbl = tk.Label(self._nav, text="", bg="#2e2e2e", fg="#aaa",
                                  font=("Segoe UI", 9), width=10)
        self._nav_lbl.pack(side="left")
        tk.Button(self._nav, text="▶", command=lambda: self._files.next(), **B).pack(side="left", padx=2)
        tk.Button(self._nav, text="전체 자동 처리", command=self._batch, **B).pack(side="left", padx=6)

        # 메인 컨텐츠 영역
        content = tk.Frame(self, bg="#242424")
        content.pack(fill="both", expand=True, padx=6, pady=6)

        # 좌측: 썸네일 패널
        self._thumb_panel = ThumbPanel(
            content,
            on_select=lambda idx: self._files.select(idx),
            on_delete=lambda idx: self._files.remove(idx),
            on_delete_selected=lambda: self._files.remove_selected(),
            extra_menu_items=[("Copy", self._select_and_copy)],
            checkbox_default=True,
            open_label="Open",
            delete_label="Delete",
        )

        # 중앙+우측: 원본 | 결과 캔버스
        pv = tk.Frame(content, bg="#242424")
        pv.pack(side="left", fill="both", expand=True)

        self._orig_cv = ImageCanvas(
            pv,
            "원본  |  클릭·드래그: 가장 가까운 꼭짓점 이동",
            on_change=self._on_pts_change,
            pannable=False,
        )
        self._orig_cv.pack(side="left", fill="both", expand=True, padx=(0, 3))

        self._res_cv = ImageCanvas(
            pv,
            "결과  |  드래그: 화면 이동   /   휠: 줌   /   더블클릭: 뷰 초기화",
        )
        self._res_cv.pack(side="right", fill="both", expand=True, padx=(3, 0))

        self._st = tk.Label(self, text="파일을 열거나 창에 드래그 & 드롭하세요.",
                             bg="#2e2e2e", fg="#888", anchor="w",
                             font=("Segoe UI", 9), padx=8, pady=4)
        self._st.pack(fill="x", side="bottom")

    def _show_hint(self):
        if self._cv_orig is None:
            self._orig_cv.show_hint()
            self._res_cv.show_hint("변환 결과가 여기에 표시됩니다")

    # ── 썸네일 패널 연동 ─────────────────────────────────────────────────

    def _select_and_copy(self, idx: int):
        self._files.select(idx)
        self._copy_to_clipboard()

    def _on_files_empty(self):
        self._cv_orig       = None
        self._cv_result     = None
        self._current_path  = None
        self._orig_cv.show_hint()
        self._res_cv.show_hint("변환 결과가 여기에 표시됩니다")
        self._st.config(text="파일을 열거나 창에 드래그 & 드롭하세요.")

    def _on_key_delete(self, event):
        self._files.remove_current()

    # ── DnD ─────────────────────────────────────────────────────────────

    def _setup_dnd(self):
        for w in (self, self._orig_cv, self._res_cv):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event):
        files = self.tk.splitlist(event.data)
        imgs  = sorted(f for f in files if Path(f).suffix.lower() in SUPPORTED_EXT)
        if not imgs:
            self._st.config(text="지원하지 않는 파일 형식입니다.")
            return
        self._files.add_files(imgs)

    # ── 파일 열기 ────────────────────────────────────────────────────────

    def _open_file(self):
        p = filedialog.askopenfilename(
            filetypes=[("이미지", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp"),
                       ("모든 파일", "*.*")])
        if p:
            self._files.add_files([p])

    def _open_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        files = sorted(str(f) for f in Path(folder).iterdir()
                       if f.suffix.lower() in SUPPORTED_EXT)
        if not files:
            messagebox.showinfo("알림", "지원하는 이미지가 없습니다.")
            return
        self._files.add_files(files)

    # ── 이미지 로드 & 감지 ───────────────────────────────────────────────

    def _load(self, path: str):
        img = read_image(path)
        if img is None:
            self._st.config(text=f"읽기 실패: {path}")
            return
        self._cv_orig      = img
        self._cv_result    = None
        self._current_path = path
        self._res_cv.clear()
        self.update_idletasks()
        self._st.config(text=f"{Path(path).name}  ({img.shape[1]}×{img.shape[0]})")
        self._redetect(silent=True)

    def _redetect(self, silent=False):
        if self._cv_orig is None:
            return
        pts = auto_detect_corners(self._cv_orig)
        if pts is None:
            h, w = self._cv_orig.shape[:2]
            m    = min(w, h) * 0.05
            pts  = [[m, m], [w - m, m], [w - m, h - m], [m, h - m]]
            if not silent:
                self._st.config(text="자동 감지 실패 — 꼭짓점을 드래그해 영역을 맞춰주세요.")
        else:
            pts = pts.tolist()
            if not silent:
                self._st.config(text="자동 감지 완료. 꼭짓점 드래그로 미세 조정하세요.")

        self._orig_cv.show(self._cv_orig, pts, reset_view=True)
        self._apply()

    # ── 변환 ─────────────────────────────────────────────────────────────

    def _on_pts_change(self, _pts):
        if self._transform_job:
            self.after_cancel(self._transform_job)
        self._transform_job = self.after(DEBOUNCE_MS, self._apply)

    def _apply(self):
        if self._cv_orig is None:
            return
        pts = self._orig_cv.get_points()
        r = process_image(
            self._cv_orig,
            pts=np.array(pts, dtype="float32") if len(pts) == 4 else None,
        )
        self._cv_result = r.image
        self._res_cv.show(r.image)

    # ── 회전 ──────────────────────────────────────────────────────────────

    def _rotate_left(self):
        if self._cv_orig is None:
            return
        self._cv_orig = cv2.rotate(self._cv_orig, cv2.ROTATE_90_COUNTERCLOCKWISE)
        self._redetect(silent=True)

    def _rotate_right(self):
        if self._cv_orig is None:
            return
        self._cv_orig = cv2.rotate(self._cv_orig, cv2.ROTATE_90_CLOCKWISE)
        self._redetect(silent=True)

    # ── 뷰 초기화 ────────────────────────────────────────────────────────

    def _reset_views(self):
        """확대/축소·이동으로 틀어진 화면을 원래 배율로 되돌린다 (꼭짓점은 유지)."""
        self._orig_cv.reset_view()
        self._res_cv.reset_view()

    # ── 클립보드 ─────────────────────────────────────────────────────────

    def _copy_to_clipboard(self):
        if self._cv_result is None:
            messagebox.showwarning("알림", "복사할 결과 이미지가 없습니다.")
            return
        try:
            rgb = cv2.cvtColor(self._cv_result, cv2.COLOR_BGR2RGB)
            buf = io.BytesIO()
            Image.fromarray(rgb).save(buf, "BMP")
            data = buf.getvalue()[14:]   # BMP 파일 헤더 14바이트 제거
            buf.close()

            k32 = ctypes.windll.kernel32
            k32.GlobalAlloc.restype  = ctypes.c_void_p
            k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            k32.GlobalLock.restype   = ctypes.c_void_p
            k32.GlobalLock.argtypes  = [ctypes.c_void_p]
            k32.GlobalUnlock.argtypes = [ctypes.c_void_p]

            CF_DIB   = 8
            GMEM_MOV = 0x0002
            hMem = k32.GlobalAlloc(GMEM_MOV, len(data))
            ptr  = k32.GlobalLock(hMem)
            ctypes.memmove(ptr, data, len(data))
            k32.GlobalUnlock(hMem)

            u32 = ctypes.windll.user32
            u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            u32.OpenClipboard(0)
            try:
                u32.EmptyClipboard()
                u32.SetClipboardData(CF_DIB, hMem)
            finally:
                u32.CloseClipboard()
            self._st.config(text="클립보드에 복사됨")
        except Exception as e:
            messagebox.showerror("오류", f"클립보드 복사 실패: {e}")

    # ── 저장 ────────────────────────────────────────────────────────────

    def _save(self):
        if self._cv_result is None or not self._current_path:
            messagebox.showwarning("알림", "저장할 결과 이미지가 없습니다.")
            return
        p       = Path(self._current_path)
        out_dir = p.parent / SAVE_FOLDER
        out_dir.mkdir(exist_ok=True)
        out = unique_path(out_dir, p.stem, p.suffix)
        if write_image(str(out), self._cv_result):
            self._st.config(text=f"저장됨: {out}")
        else:
            messagebox.showerror("오류", "저장 실패")

    def _save_as(self):
        if self._cv_result is None:
            messagebox.showwarning("알림", "저장할 결과 이미지가 없습니다.")
            return
        p    = Path(self._current_path) if self._current_path else Path("image")
        path = filedialog.asksaveasfilename(
            initialdir=str(p.parent / SAVE_FOLDER),
            initialfile=p.stem,
            defaultextension=p.suffix or ".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("BMP", "*.bmp"),
                       ("모든 파일", "*.*")])
        if not path:
            return
        dest = Path(path)
        if dest.exists() and not messagebox.askyesno(
                "덮어쓰기 확인", f"'{dest.name}' 이(가) 이미 존재합니다.\n덮어쓸까요?"):
            return
        if write_image(path, self._cv_result):
            self._st.config(text=f"저장됨: {path}")
        else:
            messagebox.showerror("오류", "저장 실패")

    # ── 배치 ────────────────────────────────────────────────────────────

    def _batch(self):
        targets = [
            (i, fpath)
            for i, fpath in enumerate(self._files.files)
            if self._thumb_panel.is_checked(i)
        ]
        if not targets:
            messagebox.showinfo("알림", "처리할 파일이 없습니다.\n썸네일 체크박스를 확인해 주세요.")
            return
        if not messagebox.askyesno("전체 자동 처리",
                                    f"체크된 {len(targets)}개 파일을 자동 처리하여\n"
                                    f"'변환파일' 폴더에 저장할까요?\n(기존 파일은 덮어쓰지 않습니다)"):
            return

        def worker():
            ok = fail = 0
            for seq, (i, fpath) in enumerate(targets):
                self.after(0, lambda s=seq: self._st.config(
                    text=f"처리 중... {s + 1}/{len(targets)}"))
                img = read_image(fpath)
                if img is None:
                    fail += 1; continue
                r       = process_image(img)
                p       = Path(fpath)
                out_dir = p.parent / SAVE_FOLDER
                out_dir.mkdir(exist_ok=True)
                out = unique_path(out_dir, p.stem, p.suffix)
                if write_image(str(out), r.image):
                    ok += 1
                else:
                    fail += 1

            self.after(0, lambda: messagebox.showinfo(
                "완료", f"완료: 성공 {ok}개, 실패 {fail}개\n'변환파일' 폴더에 저장됨"))
            self.after(0, lambda: self._st.config(
                text=f"처리 완료: {ok}/{len(targets)}"))

        threading.Thread(target=worker, daemon=True).start()


def _sep(parent):
    tk.Frame(parent, bg="#484848", width=1, height=26).pack(side="left", padx=8)


if __name__ == "__main__":
    App().mainloop()
