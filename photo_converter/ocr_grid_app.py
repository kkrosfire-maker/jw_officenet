"""3단계(ocr_grid.py) 단독 테스트용 GUI. main.py/annotate_app.py와는 독립적으로 실행된다.

테두리 그리기·이동·리사이즈·회전·undo/redo는 annotate_app.py(2단계)와 공용 위젯인
rect_canvas.RectCanvas를 그대로 재사용한다. 다른 점은 결과 미리보기 대신, 선택한
테두리를 OCR로 인식해 우측 텍스트 박스에 넣고 사람이 직접 교정하는 것.
"""
import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import numpy as np
import cv2
from PIL import ImageGrab
from tkinterdnd2 import TkinterDnD, DND_FILES

from ocr_grid import recognize_lines
from imageio_utils import read_image, unique_path
from thumb_panel import ThumbPanel
from undo_stack import HistoryController
from file_list_controller import FileListController
from rect_canvas import RectCanvas

IMAGE_EXT     = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
EXPORT_FOLDER = "그리드결과"
CANVAS_W      = 760
CANVAS_H      = 760
UNDO_LIMIT    = 50


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("그리드 OCR 인식 + 교정 (3단계 테스트)")
        self.geometry("1500x820")
        self.configure(bg="#242424")

        self._cv_img       = None
        self._current_path = None

        self._rect_texts = []   # RectCanvas의 rects와 병렬, 각 테두리의 교정된 OCR 텍스트(멀티라인)
        self._text_idx   = None  # 지금 텍스트 박스에 표시 중인 테두리 인덱스

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
        self._history.bind_keys(self, ignore_types=(tk.Entry, tk.Spinbox, ttk.Entry, tk.Text),
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

        self._nav = tk.Frame(top, bg="#2e2e2e")
        tk.Button(self._nav, text="◀", command=lambda: self._files.prev(), **B).pack(side="left", padx=2)
        self._nav_lbl = tk.Label(self._nav, text="", bg="#2e2e2e", fg="#aaa",
                                  font=("Segoe UI", 9), width=10)
        self._nav_lbl.pack(side="left")
        tk.Button(self._nav, text="▶", command=lambda: self._files.next(), **B).pack(side="left", padx=2)

        form = tk.Frame(self, bg="#2e2e2e", pady=6)
        form.pack(fill="x")

        self._thick_var    = tk.IntVar(value=4)
        self._psm_var      = tk.IntVar(value=6)
        self._scale_var    = tk.DoubleVar(value=2.0)
        self._contrast_var = tk.BooleanVar(value=True)

        tk.Button(form, text="+ 테두리 추가", command=self._add_rect, **B).pack(side="left", padx=(10, 4))
        tk.Button(form, text="선택 테두리 삭제", command=self._delete_selected_rect, **B).pack(side="left", padx=4)
        tk.Label(form, text="테두리 두께", bg="#2e2e2e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 2))
        tk.Spinbox(form, from_=1, to=30, textvariable=self._thick_var,
                   width=4, font=("Segoe UI", 10), command=self._on_thickness_change
                   ).pack(side="left")
        self._thick_var.trace_add("write", self._on_thickness_change)

        tk.Label(form, text="psm", bg="#2e2e2e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 2))
        tk.Spinbox(form, from_=0, to=13, textvariable=self._psm_var,
                   width=3, font=("Segoe UI", 10)).pack(side="left")
        tk.Label(form, text="scale", bg="#2e2e2e", fg="#aaa",
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        tk.Spinbox(form, from_=0.5, to=4.0, increment=0.5, textvariable=self._scale_var,
                   width=4, font=("Segoe UI", 10)).pack(side="left")
        tk.Checkbutton(form, text="대비강조", variable=self._contrast_var, bg="#2e2e2e", fg="#aaa",
                        selectcolor="#2e2e2e", activebackground="#2e2e2e",
                        activeforeground="#aaa", font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))

        form2 = tk.Frame(self, bg="#2e2e2e", pady=4)
        form2.pack(fill="x")
        tk.Button(form2, text="OCR 인식 (선택 테두리)", command=self._run_ocr_selected, **B).pack(side="left", padx=10)
        tk.Button(form2, text="↶ 실행 취소 (Ctrl+Z)",
                  command=lambda: self._history_status("undo", self._history.undo()), **B).pack(side="left", padx=(14, 4))
        tk.Button(form2, text="↷ 다시 실행 (Ctrl+Y)",
                  command=lambda: self._history_status("redo", self._history.redo()), **B).pack(side="left", padx=4)
        tk.Button(form2, text="테두리 전체 지우기", command=self._clear_all_rects, **B).pack(side="left", padx=4)
        tk.Button(form2, text=f"결과 CSV로 내보내기 ('{EXPORT_FOLDER}')", command=self._export_csv, **B).pack(side="left", padx=(14, 4))

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
                                        on_edit=self._on_rect_edit, on_select=self._on_rect_select,
                                        badge_fn=self._rect_badge)
        self._orig_canvas.pack(fill="both", expand=True)

        right = tk.Frame(body, bg="#242424", width=380)
        right.pack(side="right", fill="y", padx=(3, 0))
        right.pack_propagate(False)
        self._right_lbl = tk.Label(right, text="OCR 결과 (테두리를 선택하세요)", bg="#242424", fg="#888",
                                    font=("Segoe UI", 9))
        self._right_lbl.pack(anchor="w")
        text_frame = tk.Frame(right, bg="#242424")
        text_frame.pack(fill="both", expand=True)
        yscroll = tk.Scrollbar(text_frame)
        yscroll.pack(side="right", fill="y")
        self._text = tk.Text(text_frame, bg="#1a1a1a", fg="white", insertbackground="white",
                              font=("Consolas", 11), wrap="word", yscrollcommand=yscroll.set,
                              undo=True)
        self._text.pack(side="left", fill="both", expand=True)
        yscroll.config(command=self._text.yview)
        self._text.bind("<FocusOut>", lambda e: self._sync_text_from_widget())

        self._st = tk.Label(self, text="이미지를 열거나 창에 드래그 & 드롭하세요.", bg="#2e2e2e", fg="#888",
                             anchor="w", font=("Segoe UI", 9), padx=8, pady=4)
        self._st.pack(fill="x", side="bottom")

    # ── 파일 목록 빈 상태 / 로드 ─────────────────────────────────────────

    def _on_files_empty(self):
        self._cv_img = None
        self._current_path = None
        self._rect_texts.clear()
        self._text_idx = None
        self._history.clear()
        self._orig_canvas.clear()
        self._text.delete("1.0", tk.END)
        self._right_lbl.config(text="OCR 결과 (테두리를 선택하세요)")
        self._st.config(text="파일을 열거나 창에 드래그 & 드롭하세요.")

    def _on_key_delete_file(self, event):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Spinbox, ttk.Entry, tk.Text)):
            return
        self._files.remove_current()

    # ── 실행 취소 / 다시 실행 (테두리 기하만 대상 — 텍스트 교정은 스코프 밖) ──

    def _sync_rect_texts_len(self):
        n = len(self._orig_canvas.get_rects())
        if len(self._rect_texts) < n:
            self._rect_texts.extend([""] * (n - len(self._rect_texts)))
        elif len(self._rect_texts) > n:
            del self._rect_texts[n:]

    def _restore_rects(self, snapshot):
        self._orig_canvas.set_rects(snapshot)
        self._sync_rect_texts_len()
        self._text_idx = None
        self._text.delete("1.0", tk.END)
        self._right_lbl.config(text="OCR 결과 (테두리를 선택하세요)")

    def _history_status(self, action, ok):
        n = len(self._orig_canvas.get_rects())
        if action == "undo":
            self._st.config(text=f"실행 취소함 (테두리 {n}개)" if ok else "더 되돌릴 내용이 없습니다.")
        else:
            self._st.config(text=f"다시 실행함 (테두리 {n}개)" if ok else "다시 실행할 내용이 없습니다.")

    # ── 테두리 편집 콜백 (RectCanvas) ─────────────────────────────────────

    def _on_rect_edit(self, kind, pre_snapshot, index=None):
        self._history.push(pre_snapshot)
        if kind == "add":
            self._rect_texts.append("")
        elif kind == "delete":
            del self._rect_texts[index]
        elif kind == "clear":
            self._rect_texts.clear()

    def _rect_badge(self, idx):
        has_text = bool(self._rect_texts[idx].strip()) if idx < len(self._rect_texts) else False
        return str(idx), ("#4CAF50" if has_text else "#888")

    # ── 선택 전환 (텍스트 박스 ↔ rect_texts 동기화) ─────────────────────

    def _sync_text_from_widget(self):
        if self._text_idx is not None and 0 <= self._text_idx < len(self._rect_texts):
            self._rect_texts[self._text_idx] = self._text.get("1.0", "end-1c")

    def _on_rect_select(self, idx):
        self._sync_text_from_widget()
        self._text_idx = idx
        if idx is not None:
            self._thick_var.set(self._orig_canvas.selected_thickness())
        self._text.delete("1.0", tk.END)
        if idx is not None and 0 <= idx < len(self._rect_texts):
            self._text.insert("1.0", self._rect_texts[idx])
            self._right_lbl.config(text=f"OCR 결과 — 테두리 [{idx}]  (자유롭게 수정 가능)")
        else:
            self._right_lbl.config(text="OCR 결과 (테두리를 선택하세요)")

    def _add_rect(self):
        if self._cv_img is None:
            messagebox.showwarning("알림", "먼저 이미지를 열어주세요.")
            return
        self._orig_canvas.add_rect(hw_ratio=0.2, hh_ratio=0.1, thickness=self._thick_var.get())

    def _delete_selected_rect(self):
        idx = self._orig_canvas.selected_index()
        if idx is None:
            messagebox.showinfo("알림", "선택된 테두리가 없습니다. 테두리를 클릭해 선택하세요.")
            return
        self._orig_canvas.delete_selected()
        self._text_idx = None
        self._text.delete("1.0", tk.END)
        self._right_lbl.config(text="OCR 결과 (테두리를 선택하세요)")

    def _clear_all_rects(self):
        if not self._orig_canvas.clear_rects():
            return
        self._text_idx = None
        self._text.delete("1.0", tk.END)
        self._right_lbl.config(text="OCR 결과 (테두리를 선택하세요)")
        self._st.config(text="테두리를 모두 지웠습니다.")

    def _on_thickness_change(self, *args):
        if self._orig_canvas.selected_index() is not None:
            try:
                self._orig_canvas.set_selected_thickness(self._thick_var.get())
            except tk.TclError:
                return

    # ── DnD ─────────────────────────────────────────────────────────────

    def _setup_dnd(self):
        for w in (self, self._orig_canvas):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event):
        files = self.tk.splitlist(event.data)
        images = [f for f in files if Path(f).suffix.lower() in IMAGE_EXT]
        others = [f for f in files if f not in images]
        if images:
            self._files.add_files(images)
        if others:
            self._st.config(text=f"지원하지 않는 파일 형식: {Path(others[0]).name}")

    # ── 파일 열기 ──────────────────────────────────────────────────────

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
        self._cv_img = img
        self._rect_texts.clear()
        self._text_idx = None
        self._history.clear()
        self._text.delete("1.0", tk.END)
        self._right_lbl.config(text="OCR 결과 (테두리를 선택하세요)")
        self._st.config(text="'+ 테두리 추가'로 인식할 영역을 지정한 뒤 'OCR 인식'을 눌러주세요.")

        self._orig_canvas.show(img)
        self._orig_canvas.set_rects([])

    # ── 클립보드 붙여넣기 ────────────────────────────────────────────────

    def _on_paste_shortcut(self, event):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Spinbox, ttk.Entry, tk.Text)):
            return None
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
        self._current_path = None
        self._cv_img = img
        self._rect_texts.clear()
        self._text_idx = None
        self._history.clear()
        self._text.delete("1.0", tk.END)
        self._right_lbl.config(text="OCR 결과 (테두리를 선택하세요)")
        self._st.config(text="클립보드에서 이미지를 붙여넣었습니다.")
        self._orig_canvas.show(img)
        self._orig_canvas.set_rects([])

    # ── OCR 인식 ───────────────────────────────────────────────────────

    def _run_ocr_selected(self):
        if self._cv_img is None:
            messagebox.showwarning("알림", "먼저 이미지를 열어주세요.")
            return
        idx = self._orig_canvas.selected_index()
        if idx is None:
            messagebox.showinfo("알림", "먼저 테두리를 클릭해 선택하세요.")
            return
        rect = self._orig_canvas.get_rects()[idx]
        self._st.config(text="OCR 인식 중...")
        self.update_idletasks()
        try:
            lines = recognize_lines(
                self._cv_img, rect,
                psm=self._psm_var.get(), scale=self._scale_var.get(),
                enhance_contrast=self._contrast_var.get())
        except Exception as e:
            messagebox.showerror("오류", f"OCR 실패: {e}")
            self._st.config(text="OCR 실패")
            return

        text = "\n".join(lines)
        self._rect_texts[idx] = text
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", text)
        self._right_lbl.config(text=f"OCR 결과 — 테두리 [{idx}]  (자유롭게 수정 가능)")
        self._st.config(text=f"[{idx}] OCR 인식 완료 ({len(lines)}줄) — 오류를 직접 수정하세요.")

    # ── 결과 내보내기 (엑셀 양식 미정 — 우선 CSV로) ────────────────────────

    def _export_csv(self):
        if not self._orig_canvas.get_rects():
            messagebox.showinfo("알림", "테두리가 없습니다.")
            return
        self._sync_text_from_widget()

        if self._current_path:
            p = Path(self._current_path)
            out_dir = p.parent / EXPORT_FOLDER
            stem = p.stem
        else:
            out_dir = Path.cwd() / EXPORT_FOLDER
            stem = "붙여넣은이미지"
        out_dir.mkdir(exist_ok=True)
        out = unique_path(out_dir, stem, ".csv")

        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["테두리", "줄번호", "텍스트"])
            for ridx, text in enumerate(self._rect_texts):
                for lidx, line in enumerate(text.split("\n")):
                    w.writerow([ridx, lidx, line])

        self._st.config(text=f"내보냄: {out}")


if __name__ == "__main__":
    App().mainloop()
