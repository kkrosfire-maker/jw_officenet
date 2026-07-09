"""2단계(annotate.py) 단독 테스트용 GUI. main.py와는 독립적으로 실행된다."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import cv2
import numpy as np
import openpyxl
from PIL import Image, ImageGrab, ImageTk
from tkinterdnd2 import TkinterDnD, DND_FILES

from annotate import parse_filename, build_label, annotate_image
from imageio_utils import read_image, write_image, unique_path
from thumb_panel import ThumbPanel
from undo_stack import HistoryController
from file_list_controller import FileListController
from rect_canvas import RectCanvas

IMAGE_EXT     = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
EXCEL_EXT     = {".xlsx", ".xlsm"}
SAVE_FOLDER   = "라벨완료"
CANVAS_W      = 620
CANVAS_H      = 620
MONTHS        = [f"{i}월" for i in range(1, 13)]
UNDO_LIMIT    = 50


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

        self._hospital_list = []
        self._pharma_list   = []

        self._build_ui()

        self._history = HistoryController(
            snapshot_fn=self._orig_canvas.get_rects,
            restore_fn=self._restore_rects,
            limit=UNDO_LIMIT,
        )
        self._files = FileListController(
            self._thumb_panel,
            on_load=self._load_image,
            on_empty=self._on_files_empty,
            nav=self._nav,
            nav_label=self._nav_lbl,
            status=lambda t: self._st.config(text=t),
        )

        self._orig_canvas.bind_keyboard_rotate(self)
        self._history.bind_keys(self, ignore_types=(tk.Entry, tk.Spinbox, ttk.Entry),
                                 status_fn=self._history_status)

        self._setup_dnd()
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
        tk.Button(self._nav, text="◀", command=lambda: self._files.prev(), **B).pack(side="left", padx=2)
        self._nav_lbl = tk.Label(self._nav, text="", bg="#2e2e2e", fg="#aaa",
                                  font=("Segoe UI", 9), width=10)
        self._nav_lbl.pack(side="left")
        tk.Button(self._nav, text="▶", command=lambda: self._files.next(), **B).pack(side="left", padx=2)

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
        tk.Button(form2, text="↶ 실행 취소 (Ctrl+Z)",
                  command=lambda: self._history_status("undo", self._history.undo()), **B).pack(side="left", padx=(14, 4))
        tk.Button(form2, text="↷ 다시 실행 (Ctrl+Y)",
                  command=lambda: self._history_status("redo", self._history.redo()), **B).pack(side="left", padx=4)
        tk.Button(form2, text="테두리 전체 지우기", command=self._clear_all_rects, **B).pack(side="left", padx=4)

        body = tk.Frame(self, bg="#242424")
        body.pack(fill="both", expand=True, padx=6, pady=6)

        self._thumb_panel = ThumbPanel(
            body,
            on_select=lambda idx: self._files.select(idx),
            on_delete=lambda idx: self._files.remove(idx),
            on_delete_selected=lambda: self._files.remove_selected(),
            checkbox_default=False,
        )

        left = tk.Frame(body, bg="#242424")
        left.pack(side="left", fill="both", expand=True, padx=(0, 3))
        tk.Label(left, text="원본  |  몸통 드래그: 이동  /  모서리: 크기 조절  /  모서리 바깥쪽: 회전  /  "
                             "선택 후 ALT+←→: 15°, CTRL+ALT+←→: 5° 회전",
                 bg="#242424", fg="#888", font=("Segoe UI", 9)).pack(anchor="w")
        self._orig_canvas = RectCanvas(left, width=CANVAS_W, height=CANVAS_H,
                                        on_edit=self._on_rect_edit, on_select=self._on_rect_select)
        self._orig_canvas.pack(fill="both", expand=True)

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

    # ── 파일 목록 빈 상태 / 로드 ─────────────────────────────────────────

    def _on_files_empty(self):
        self._cv_img       = None
        self._cv_result     = None
        self._current_path  = None
        self._history.clear()
        self._orig_canvas.clear()
        self._res_canvas.delete("all")
        self._st.config(text="파일을 열거나 창에 드래그 & 드롭하세요.")

    def _on_key_delete_file(self, event):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Spinbox, ttk.Entry)):
            return
        self._files.remove_current()

    # ── 실행 취소 / 다시 실행 ─────────────────────────────────────────────

    def _restore_rects(self, snapshot):
        self._orig_canvas.set_rects(snapshot)
        self._apply(silent=True)

    def _history_status(self, action, ok):
        n = len(self._orig_canvas.get_rects())
        if action == "undo":
            self._st.config(text=f"실행 취소함 (테두리 {n}개)" if ok else "더 되돌릴 내용이 없습니다.")
        else:
            self._st.config(text=f"다시 실행함 (테두리 {n}개)" if ok else "다시 실행할 내용이 없습니다.")

    # ── 테두리 편집 콜백 (RectCanvas) ─────────────────────────────────────

    def _on_rect_edit(self, kind, pre_snapshot, index=None):
        self._history.push(pre_snapshot)
        self._apply(silent=True)

    def _on_rect_select(self, idx):
        if idx is not None:
            self._thick_var.set(self._orig_canvas.selected_thickness())

    def _add_rect(self):
        if self._cv_img is None:
            messagebox.showwarning("알림", "먼저 이미지를 열어주세요.")
            return
        self._orig_canvas.add_rect(hw_ratio=0.125, hh_ratio=0.125, thickness=self._thick_var.get())

    def _delete_selected_rect(self):
        if self._orig_canvas.selected_index() is None:
            messagebox.showinfo("알림", "선택된 테두리가 없습니다. 테두리를 클릭해 선택하세요.")
            return
        self._orig_canvas.delete_selected()

    def _clear_all_rects(self):
        if not self._orig_canvas.clear_rects():
            return
        self._st.config(text="테두리를 모두 지웠습니다.")

    def _on_thickness_change(self, *args):
        if self._orig_canvas.selected_index() is not None:
            try:
                self._orig_canvas.set_selected_thickness(self._thick_var.get())
            except tk.TclError:
                return

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
            self._files.add_files(images)
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
            self._files.add_files(list(paths))

    def _open_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        files = sorted(str(f) for f in Path(folder).iterdir()
                       if f.suffix.lower() in IMAGE_EXT)
        if not files:
            messagebox.showinfo("알림", "지원하는 이미지가 없습니다.")
            return
        self._files.add_files(files)

    def _load_image(self, path: str):
        img = read_image(path)
        if img is None:
            messagebox.showerror("오류", "이미지를 읽을 수 없습니다.")
            return

        self._current_path = path
        self._cv_img    = img
        self._cv_result = None
        self._history.clear()

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

        self._orig_canvas.show(img)
        self._orig_canvas.set_rects([])
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
                self._files.add_files(images)
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
        self._history.clear()
        self._hospital_var.set("")
        self._month_var.set("")
        self._pharma_var.set("")
        self._st.config(text="클립보드에서 이미지를 붙여넣었습니다 — 병원명/월/제약사명을 입력하세요. "
                              "(파일명이 없어 저장 시 위치를 직접 지정합니다)")
        self._orig_canvas.show(img)
        self._orig_canvas.set_rects([])
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
        rects = self._orig_canvas.get_rects()
        self._cv_result = annotate_image(self._cv_img, label, rects=rects)
        self._render_result()
        self._st.config(text=f"미리보기 적용됨: {label}  (테두리 {len(rects)}개)")

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
