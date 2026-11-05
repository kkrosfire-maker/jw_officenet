"""이미지 작업창 공용 껍데기 — annotate_app.py / ocr_grid_app.py(테두리 편집 앱)가 공유.

파일 목록·실행취소·클립보드 붙여넣기·드래그앤드롭·삭제키 연결을 한 곳에서 맡는다.
앱은 다음만 제공한다:
  - self._orig_canvas (RectCanvas), self._thumb_panel, self._nav, self._nav_lbl, self._st, self._thick_var
  - _load_image(path), _on_files_empty(), _restore_rects(snapshot), _load_clipboard_image(img)
  - (선택) _drop_targets(), _handle_dropped_extras(files)
"""
import tkinter as tk
from collections import namedtuple
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import ImageGrab
from tkinterdnd2 import DND_FILES

from file_list_controller import FileListController
from undo_stack import HistoryController

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
IMAGE_FILETYPES = [("이미지", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp"), ("모든 파일", "*.*")]
TEXT_INPUT_TYPES = (tk.Entry, tk.Spinbox, ttk.Entry, tk.Text)

Clipboard = namedtuple("Clipboard", ["kind", "files", "image"])
"""kind: "files"(지원 이미지 파일 목록) | "no_images"(파일은 있으나 지원 형식 없음) | "empty" | "image"(BGR ndarray)"""


def images_in_folder(folder) -> list:
    return sorted(str(f) for f in Path(folder).iterdir() if f.suffix.lower() in IMAGE_EXT)


def read_clipboard(grab=ImageGrab.grabclipboard) -> Clipboard:
    data = grab()
    if isinstance(data, list) and data:
        images = [f for f in data if Path(f).suffix.lower() in IMAGE_EXT]
        return Clipboard("files", images, None) if images else Clipboard("no_images", [], None)
    if data is None or isinstance(data, list):
        return Clipboard("empty", [], None)
    rgb = np.array(data.convert("RGB"))
    return Clipboard("image", [], cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def history_status_text(action, ok, rect_count) -> str:
    if action == "undo":
        return f"실행 취소함 (테두리 {rect_count}개)" if ok else "더 되돌릴 내용이 없습니다."
    return f"다시 실행함 (테두리 {rect_count}개)" if ok else "다시 실행할 내용이 없습니다."


class RectEditorShell:
    """tk 창(TkinterDnD.Tk)과 함께 상속하는 믹스인."""

    def _wire_shell(self, undo_limit=50):
        """_build_ui() 이후에 호출."""
        self._history = HistoryController(
            snapshot_fn=self._orig_canvas.get_rects,
            restore_fn=self._restore_rects,
            limit=undo_limit,
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
        self._history.bind_keys(self, ignore_types=TEXT_INPUT_TYPES,
                                status_fn=self._history_status)
        self._setup_dnd()
        self.bind_all("<Control-v>", self._on_paste_shortcut)
        self.bind("<Delete>", self._on_key_delete_file)

    # ── 실행취소 / 키 ────────────────────────────────────────────────────

    def _history_status(self, action, ok):
        self._st.config(text=history_status_text(action, ok, len(self._orig_canvas.get_rects())))

    def _on_key_delete_file(self, event):
        if isinstance(self.focus_get(), TEXT_INPUT_TYPES):
            return
        self._files.remove_current()

    def _on_thickness_change(self, *args):
        if self._orig_canvas.selected_index() is not None:
            try:
                self._orig_canvas.set_selected_thickness(self._thick_var.get())
            except tk.TclError:
                return

    # ── 드래그앤드롭 ─────────────────────────────────────────────────────

    def _drop_targets(self):
        return (self, self._orig_canvas)

    def _setup_dnd(self):
        for w in self._drop_targets():
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self._on_drop)

    def _handle_dropped_extras(self, files):
        """이미지가 아닌 드롭 파일을 처리하고, 처리하지 못한 나머지를 반환한다."""
        return files

    def _on_drop(self, event):
        files = list(self.tk.splitlist(event.data))
        images = [f for f in files if Path(f).suffix.lower() in IMAGE_EXT]
        rest = self._handle_dropped_extras([f for f in files if f not in images])
        if images:
            self._files.add_files(images)
        if rest:
            self._st.config(text=f"지원하지 않는 파일 형식: {Path(rest[0]).name}")

    # ── 파일 열기 ────────────────────────────────────────────────────────

    def _open_file(self):
        paths = filedialog.askopenfilenames(filetypes=IMAGE_FILETYPES)
        if paths:
            self._files.add_files(list(paths))

    def _open_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        files = images_in_folder(folder)
        if not files:
            messagebox.showinfo("알림", "지원하는 이미지가 없습니다.")
            return
        self._files.add_files(files)

    # ── 클립보드 붙여넣기 ────────────────────────────────────────────────

    def _on_paste_shortcut(self, event):
        if isinstance(self.focus_get(), TEXT_INPUT_TYPES):
            return None   # 입력창에서의 Ctrl+V는 기본 텍스트 붙여넣기에 맡긴다
        self._paste_from_clipboard()
        return "break"

    def _paste_from_clipboard(self):
        try:
            clip = read_clipboard()
        except Exception as e:
            messagebox.showerror("오류", f"클립보드를 읽을 수 없습니다: {e}")
            return
        if clip.kind == "files":
            self._files.add_files(clip.files)
        elif clip.kind == "no_images":
            self._st.config(text="클립보드의 파일 중 지원하는 이미지가 없습니다.")
        elif clip.kind == "empty":
            self._st.config(text="클립보드에 이미지가 없습니다.")
        else:
            self._load_clipboard_image(clip.image)
