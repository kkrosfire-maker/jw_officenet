"""통계 사진 문구 삽입 프로그램: 사진 하단에 '병원명 월 제약사명' 문구 + 빨간 박스 → 가로 2500px JPG."""
import os
import queue
import shutil
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk
from tkinterdnd2 import TkinterDnD, DND_FILES

import labeling
import ledger
import period_check
import rxmonth
import saving
import suggest
from file_list_controller import FileListController
from imageio_utils import make_copy, read_image, unique_path
from ledger import Ledger, clean_names
from notes_panel import NotesPanel, PANEL_W as NOTES_W
from photos import PhotoBook
from rect_canvas import RectCanvas
from settings import MemoStore, Settings
from shortcuts import Shortcuts
from suggest_entry import SuggestEntry
from thumb_panel import ThumbPanel
from undo_stack import HistoryController

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
CANVAS_W = CANVAS_H = 620
UNDO_LIMIT = 50
DEFAULT_EXCEL = Path(r"C:\Users\JW\Desktop\통계 참고파일.xlsx")     # 최초 1회 기본파일로 복사할 원본
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
BASE_EXCEL = APP_DIR / "기본파일.xlsx"        # 기본(마스터) 엑셀 (exe 로 실행하면 exe 옆 파일)
CONFIG = Path(os.environ.get("PHOTO_RENAME_CONFIG")
              or Path(os.environ.get("APPDATA") or Path.home()) / "photo_rename" / "config.json")
MONTHS = [f"{i}월" for i in range(1, 13)]
MEMO_FILE = CONFIG.parent / "특이사항메모.json"   # 병원·제약사별 메모(월이 바뀌어도 이어서 보인다, 설정과 같은 폴더)
INPUT_TYPES = (tk.Entry, tk.Spinbox, ttk.Entry, ttk.Combobox, tk.Text)   # 글자 입력 중엔 단축키(방향키·Delete·Ctrl+Z) 무시


def _crisp_taskbar_icon(win, ico):
    """tkinter iconbitmap은 32/16px만 등록해 작업표시줄(24px)에서 흐려진다.
    ICO에서 작업표시줄 크기 프레임을 직접 읽어 창에 등록한다."""
    try:
        import ctypes
        win.update_idletasks()
        u = ctypes.windll.user32
        u.LoadImageW.restype = ctypes.c_void_p
        u.GetParent.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
        scale = max(1.0, win.winfo_fpixels("1i") / 96)
        big = u.LoadImageW(None, str(ico), 1, round(24 * scale), round(24 * scale), 0x10)
        small = u.LoadImageW(None, str(ico), 1, 16, 16, 0x10)
        if big:
            u.SendMessageW(hwnd, 0x80, 1, big)
        if small:
            u.SendMessageW(hwnd, 0x80, 0, small)
    except Exception:
        pass


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("통계 사진 문구 삽입")
        self.geometry("1480x860")
        self.configure(bg="#242424")
        try:
            _ico = str(Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "app.ico")
            self.iconbitmap(_ico)
            _crisp_taskbar_icon(self, _ico)
        except Exception:
            pass

        self._settings = Settings(CONFIG)     # 저장 폴더·최근 제약사 표기·지운 제약사 (파일 키는 모두 여기)
        self._ledger = Ledger(BASE_EXCEL)     # 기본파일 이력 + 이번 달 작업 엑셀 (엑셀 규칙은 모두 여기)
        self._ledger.hidden = self._settings.hidden      # 지운 제약사 집합을 같이 쓴다
        self._xl_fail = []
        self._copy_dir = Path(tempfile.gettempdir()) / f"사진문구넣기_원본복사_{os.getpid()}"
        self._cv_img = None
        self._cv_result = None
        self._tk_res = None
        self._current_path = None
        self._photos = PhotoBook()    # 사진별 작업 기록 (병원·제약사·박스·통계기간·읽은 제약사)
        self._ocr_q = queue.Queue()
        self._memos = MemoStore(MEMO_FILE)
        self._notes_job = None
        self._apply_job = None

        self._build_ui()

        self._file_undo = []          # 삭제한 파일 묶음 [(위치, 경로), ...] — Ctrl+Z로 복원
        self._file_redo = []
        self._file_msg = None
        self._history = HistoryController(snapshot_fn=self._canvas.get_rects,
                                          restore_fn=self._restore_rects, limit=UNDO_LIMIT,
                                          fallback_undo=self._undo_file_delete,
                                          fallback_redo=self._redo_file_delete)
        self._files = FileListController(
            self._thumb_panel, on_load=self._load_image, on_empty=self._on_files_empty,
            nav=self._nav, nav_label=self._nav_lbl, status=lambda t: self._st.config(text=t),
            on_removed=self._note_removed)
        keys = Shortcuts(self, INPUT_TYPES)       # 글자 입력칸에서는 단축키를 무시하는 규칙은 여기서 한 번만
        self._canvas.bind_keyboard(keys)
        self._history.bind_keys(keys, status_fn=self._history_status)
        keys.bind("<Control-KeyPress>", self._on_ctrl_key)       # Ctrl+C / Ctrl+V = 박스 복사·붙여넣기
        keys.bind("<Delete>", self._on_key_delete_file)

        for w in (self, self._canvas, self._res_canvas):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self._on_drop)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._poll_ocr)
        self._show_out_dir()

        if not BASE_EXCEL.exists() and DEFAULT_EXCEL.exists():
            shutil.copy2(DEFAULT_EXCEL, BASE_EXCEL)
        try:
            n = clean_names(str(BASE_EXCEL))             # 분류용 끝 번호 제거 (최초 1회, 백업 후)
            if n:
                self._st.config(text=f"기본파일 제약사명 끝 번호 {n}건 제거 (백업 폴더에 원본 보관)")
        except Exception:
            pass
        self.after(100, self._reload_source)

    # ── UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        B = dict(bg="#3d4043", fg="white", relief="flat", padx=10, pady=4, cursor="hand2",
                 font=("Segoe UI", 9), bd=0, activebackground="#4e5255", activeforeground="white")
        L = dict(bg="#2e2e2e", fg="#aaa", font=("Segoe UI", 9))

        top = tk.Frame(self, bg="#2e2e2e", pady=6)
        top.pack(fill="x")
        tk.Button(top, text="파일 열기", command=self._open_file, **B).pack(side="left", padx=4)
        tk.Button(top, text="폴더 열기", command=self._open_folder, **B).pack(side="left", padx=4)
        self._excel_lbl = tk.Label(top, text="엑셀: 없음", **L)
        self._excel_lbl.pack(side="left", padx=10)
        self._nav = tk.Frame(top, bg="#2e2e2e")
        self._hosp_lbl = tk.Label(self._nav, text="", **L)          # 완료거래처 : 완료/전체
        self._hosp_lbl.pack(side="left", padx=(0, 14))
        tk.Button(self._nav, text="◀", command=lambda: self._files.prev(), **B).pack(side="left", padx=2)
        self._nav_lbl = tk.Label(self._nav, text="", width=10, **L)
        self._nav_lbl.pack(side="left")
        tk.Button(self._nav, text="▶", command=lambda: self._files.next(), **B).pack(side="left", padx=2)

        form = tk.Frame(self, bg="#2e2e2e", pady=6)
        form.pack(fill="x")
        self._month_var = tk.StringVar(value=rxmonth.label(rxmonth.default_month()))
        self._hospital_var = tk.StringVar()
        self._pharma_var = tk.StringVar()
        self._thick_var = tk.IntVar(value=4)

        tk.Label(form, text="월", **L).pack(side="left", padx=(10, 2))
        self._month_cb = ttk.Combobox(form, textvariable=self._month_var, values=MONTHS, width=5,
                                      state="readonly", font=("Segoe UI", 10))
        self._month_cb.pack(side="left")
        self._month_cb.bind("<<ComboboxSelected>>", self._on_month_change)

        tk.Label(form, text="병원명", **L).pack(side="left", padx=(12, 2))
        self._hospital_cb = SuggestEntry(form, self._hospital_var, width=22, font=("Segoe UI", 10),
                                         on_pick=self._on_hospital_pick)
        self._hospital_cb.pack(side="left")

        tk.Label(form, text="제약사명", **L).pack(side="left", padx=(12, 2))
        self._pharma_cb = SuggestEntry(form, self._pharma_var, width=22, font=("Segoe UI", 10),
                                       marked_fn=self._checked_pharma_norms)
        self._pharma_cb.pack(side="left")
        for v in (self._hospital_var, self._pharma_var):
            v.trace_add("write", self._on_text_change)

        tk.Label(form, text="선택 박스 두께", **L).pack(side="left", padx=(14, 2))
        tk.Spinbox(form, from_=1, to=30, textvariable=self._thick_var, width=4, font=("Segoe UI", 10),
                   command=self._on_thickness_change).pack(side="left")
        self._thick_var.trace_add("write", self._on_thickness_change)
        tk.Button(form, text="+ 박스 추가", command=self._add_rect, **B).pack(side="left", padx=(14, 4))
        tk.Button(form, text="선택 박스 삭제", command=self._delete_selected_rect, **B).pack(side="left", padx=4)
        tk.Button(form, text="⟲ 5°", command=lambda: self._rotate(-5), **B).pack(side="left", padx=(8, 2))
        tk.Button(form, text="⟳ 5°", command=lambda: self._rotate(5), **B).pack(side="left", padx=2)

        form2 = tk.Frame(self, bg="#2e2e2e", pady=4)
        form2.pack(fill="x")
        tk.Button(form2, text="저장 (JPG)", command=self._save_current, **B).pack(side="left", padx=10)
        tk.Button(form2, text="전체 저장", command=self._save_all, **B).pack(side="left", padx=4)
        tk.Button(form2, text="원본 복사", command=self._copy_original, **B).pack(side="left", padx=4)
        tk.Button(form2, text="정산불가", command=lambda: self._save_current(ledger.NOSETTLE),
                  **B).pack(side="left", padx=4)
        tk.Button(form2, text="↶ 실행 취소", command=lambda: self._history_status("undo", self._history.undo()),
                  **B).pack(side="left", padx=(14, 4))
        tk.Button(form2, text="↷ 다시 실행", command=lambda: self._history_status("redo", self._history.redo()),
                  **B).pack(side="left", padx=4)
        tk.Button(form2, text="박스 전체 지우기", command=self._clear_all_rects, **B).pack(side="left", padx=4)
        tk.Button(form2, text="원래대로", command=lambda: self._canvas.reset_view(), **B).pack(side="left", padx=4)
        tk.Button(form2, text="통계완료(업데이트)", command=self._complete_stats, **B).pack(side="left", padx=(14, 4))
        tk.Button(form2, text="저장 폴더 지정", command=self._choose_out_dir, **B).pack(side="left", padx=(14, 4))
        self._out_lbl = tk.Label(form2, text="", bg="#2e2e2e", fg="#aaa", font=("Segoe UI", 9))
        self._out_lbl.pack(side="left")
        self._label_lbl = tk.Label(form2, text="", bg="#2e2e2e", fg="#7fd1ff", font=("Segoe UI", 10, "bold"))
        self._label_lbl.pack(side="left", padx=16)

        body = tk.Frame(self, bg="#242424")
        body.pack(fill="both", expand=True, padx=6, pady=6)
        self._thumb_panel = ThumbPanel(
            body, on_select=self._on_thumb_select, on_delete=lambda i: self._files.remove(i),
            on_delete_selected=lambda: self._files.remove_selected(), checkbox_default=False,
            on_reorder=lambda a, b: self._files.move(a, b), on_check=self._schedule_notes_done,
            extra_menu_items=[("원본 복사", lambda i: self._copy_original(i))])

        self._notes = NotesPanel(body, on_edit=self._on_note_edit, on_delete=self._on_pharma_delete, width=NOTES_W)
        self._notes.panel.pack(side="right", fill="y", padx=(4, 0))
        self._pw = tk.PanedWindow(body, orient="horizontal", sashwidth=8, sashrelief="flat", bg="#242424",
                                  bd=0, opaqueresize=True)       # 가운데 바를 끌어 좌우 창 크기 조절
        self._pw.pack(side="left", fill="both", expand=True)

        left = tk.Frame(self._pw, bg="#242424")
        self._pw.add(left, minsize=260, stretch="always")
        wrap = tk.Frame(left, bg="#242424")
        wrap.pack(fill="both", expand=True)
        self._canvas = RectCanvas(wrap, width=CANVAS_W, height=CANVAS_H,
                                  on_edit=self._on_rect_edit, on_select=self._on_rect_select)
        self._canvas.pack(fill="both", expand=True)
        self._warn = tk.Label(wrap, text="통계기간확인", fg="#ff2222", bg="#1a1a1a",
                              font=("Malgun Gothic", 16, "bold"), padx=8, pady=2)

        right = tk.Frame(self._pw, bg="#242424")
        self._pw.add(right, minsize=260, stretch="always")
        self._res_canvas = tk.Canvas(right, bg="#1a1a1a", width=CANVAS_W, height=CANVAS_H,
                                     highlightthickness=1, highlightbackground="#3a3a3a")
        self._res_canvas.pack(fill="both", expand=True)
        self._res_canvas.bind("<Configure>", lambda e: self._render_result())

        self._st = tk.Label(self, text="사진을 열거나 창에 드래그 & 드롭하세요.", bg="#2e2e2e", fg="#888",
                            anchor="w", font=("Segoe UI", 9), padx=8, pady=4)
        self._st.pack(fill="x", side="bottom")

    # ── 기준 엑셀 ────────────────────────────────────────────────────────

    @property
    def _out_dir(self):
        return self._settings.out_dir

    def _work_excel(self):
        """JPG 저장 폴더의 이번 달 작업 엑셀 (폴더 미지정이면 None)."""
        return ledger.work_excel_path(self._out_dir)

    @property
    def _master(self):
        """병원·제약사 이력 (기본파일 + 이번 달 작업본). 아직 못 읽었으면 None."""
        return self._ledger.master

    def _reload_source(self):
        """드롭다운 후보의 기준을 다시 읽는다: 기본파일 전체 이력 + 이번 달 작업 엑셀(새로 추가한 제약사 포함)."""
        try:
            self._ledger.load()
        except Exception:
            return
        self._ledger.set_work_path(self._work_excel())
        self._apply_master()

    def _apply_master(self):
        """후보(병원·제약사)와 특이사항 패널을 현재 이력으로 갱신."""
        master = self._ledger.master
        work = self._ledger.work
        self._hospital_cb.set_candidates(master.hospitals())
        self._refresh_pharma_candidates()
        self._excel_lbl.config(text=f"엑셀: {work.name if work and work.exists() else BASE_EXCEL.name}"
                                    f"  (병원 {len(master.hospitals())}곳)")
        self._refresh_notes()

    # ── 특이사항 메모 ────────────────────────────────────────────────────

    def _refresh_notes(self):
        h = self._hospital_var.get().strip()
        if not self._master or h not in set(self._master.hospitals()):
            self._notes.set_data(h if h else "", [], "")
            return
        self._notes.set_data(h, self._master.notes_for(h, self._memos.data, self._month_var.get()),
                             self._pharma_var.get())
        self._refresh_notes_done()

    def _schedule_notes_done(self):
        """체크가 바뀌면(한꺼번에 바뀌어도 한 번만) 특이사항 칸의 제약사 이름 앞 ✓ 를 갱신한다."""
        if getattr(self, "_notes_done_job", None):
            self.after_cancel(self._notes_done_job)
        self._notes_done_job = self.after(50, self._refresh_notes_done)

    def _refresh_notes_done(self):
        self._notes_done_job = None
        self._notes.set_done(self._checked_pharma_norms())
        done, total = self._photos.hospital_progress(self._files.files, self._thumb_panel.checked_paths)
        self._hosp_lbl.config(text=f"완료거래처 : {done}/{total}")

    def _schedule_notes(self):
        if self._notes_job:
            self.after_cancel(self._notes_job)
        self._notes_job = self.after(300, self._refresh_notes)

    def _on_note_edit(self, hospital, pharma, text):
        """메모를 고치면 ① 메모 파일에 저장(월이 바뀌어도 유지) ② 이번 달 작업 엑셀의 특이사항 열에도 반영."""
        try:
            self._memos.set(hospital, pharma, text)
        except Exception as e:
            messagebox.showwarning("메모", f"메모 저장 실패: {e}")
            return
        self._ledger.set_work_path(self._work_excel())
        self._ledger.set_note(hospital, pharma, text)
        self._st.config(text=f"메모 저장: {hospital} / {pharma}")

    def _on_pharma_delete(self, hospital, pharma):
        """특이사항의 ✕: 이 병원의 제약사 목록(특이사항·입력 후보)에서 뺀다. 엑셀 기록은 지우지 않고, 새로 저장하면 다시 나타난다."""
        if not messagebox.askyesno("제약사 삭제", f"'{pharma}' 을(를) {hospital} 의 제약사 목록에서 삭제할까요?\n"
                                   "(엑셀 기록은 그대로이고, 나중에 이 제약사로 저장하면 다시 나타납니다)"):
            return False
        self._settings.hide_pharma(hospital, pharma)
        self._refresh_pharma_candidates()
        self._st.config(text=f"목록에서 삭제: {hospital} / {pharma}")
        return True

    def _complete_stats(self):
        """통계완료: 이번 달 작업 엑셀(JPG폴더/1.통계입력_yymm.xlsx)의 입력완료 내용을 기본파일에 반영."""
        work = self._work_excel()
        if self._ledger.pending:
            messagebox.showinfo("알림", "엑셀에 반영 중인 저장 건이 있습니다. 잠시 후 다시 눌러주세요.")
            return
        if not work or not work.exists():
            messagebox.showinfo("알림", "반영할 통계입력 엑셀이 없습니다.\n(JPG 저장 폴더에 1.통계입력_yymm.xlsx 필요)")
            return
        if not messagebox.askyesno("통계완료(업데이트)",
                                   f"{work.name} 의 입력완료 내용을\n{BASE_EXCEL.name} 에 반영할까요?\n"
                                   "(기본파일은 백업 폴더에 복사본을 남기고 수정합니다)"):
            return
        self._ledger.set_work_path(work)
        try:
            upd, add = self._ledger.complete()
        except PermissionError:
            messagebox.showerror("엑셀", "엑셀 파일이 열려 있습니다. 닫고 다시 눌러주세요.")
            return
        except Exception as e:
            messagebox.showerror("오류", f"반영 실패: {e}")
            return
        self._st.config(text=f"통계완료: 기본파일에 상태 변경 {upd}건, 새 행 추가 {add}건 반영")
        messagebox.showinfo("통계완료(업데이트)", f"기본파일에 반영했습니다.\n상태 변경 {upd}건 / 새 행 추가 {add}건")

    def _refresh_pharma_candidates(self):
        """제약사 칸의 후보를 현재 병원·처방월에 맞게 갱신 (규칙은 suggest.candidates)."""
        if not self._master:
            return
        primary, secondary = suggest.candidates(self._master, self._hospital_var.get().strip(),
                                                self._month_var.get(), self._settings.recent_pharma)
        self._pharma_cb.set_candidates(primary, secondary)

    def _apply_ocr_pharma(self, path):
        """사진에서 읽은 제약사 글자와 비슷한 제약사를 찾아, 비어 있으면 일단 넣어 둔다 (틀리면 직접 수정)."""
        if not path or path != self._current_path or not self._master:
            return
        raw = self._photos.get(path).ocr_pharma
        name = suggest.autofill(self._master, self._hospital_var.get(), self._pharma_var.get(), raw,
                                self._settings.recent_pharma)
        if name:
            self._pharma_var.set(name)
            self._st.config(text=f"사진에서 읽은 제약사 '{raw}' → '{name}' 자동 입력 (틀리면 고쳐 주세요)")

    def _checked_pharma_norms(self):
        """현재 병원에서 이미 체크된(작업 끝낸) 사진들의 제약사 이름(정규화) — 드롭다운 ✓ 표시용."""
        self._remember()
        return self._photos.pharma_norms_done(self._hospital_var.get(), self._thumb_panel.checked_paths)

    def _on_hospital_pick(self, value=None):
        self._refresh_pharma_candidates()
        self._apply_ocr_pharma(self._current_path)
        # 이번 월에 그 병원 제약사가 하나뿐이면 자동 입력
        if self._master:
            month = self._month_var.get()
            name = suggest.sole_pharma(self._master, self._hospital_var.get(), month,
                                       rxmonth.year_for(rxmonth.parse(month)), self._pharma_var.get())
            if name:
                self._pharma_var.set(name)

    # ── 파일 로드 / 상태 ─────────────────────────────────────────────────

    def _remember(self):
        if self._current_path:
            self._photos.record(self._current_path, self._hospital_var.get(), self._pharma_var.get(),
                                self._canvas.get_rects(), self._month_var.get())

    def _load_image(self, path):
        prev = self._current_path
        self._remember()
        if prev and prev != path and self._photos.is_ready(prev):
            self._thumb_panel.set_checked(prev, True)      # 병원·제약사명을 넣고 다음 그림으로 넘어가면 자동 체크
        img = read_image(path)
        if img is None:
            messagebox.showerror("오류", "이미지를 읽을 수 없습니다.")
            return
        self._current_path, self._cv_img = path, img
        self._history.clear()
        ph = self._photos.get(path)
        first_open = not ph.opened
        self._hospital_var.set(ph.hospital)
        self._pharma_var.set(ph.pharma)
        self._month_var.set(ph.month or self._default_month_label())      # 처방월은 사진마다 따로 (처음 여는 사진은 지난달)
        self._schedule_notes()
        guessed = ""
        if first_open and self._master:                    # 처음 여는 사진: 파일명에서 병원명 추측
            h, p = self._master.guess_from_filename(path)
            if h:
                self._hospital_var.set(h)
                self._refresh_pharma_candidates()
                if p:
                    self._pharma_var.set(p)
                else:
                    self._on_hospital_pick()
                guessed = f"파일명에서 병원명 입력: {h}" + (f" / {p}" if p else "")
        self._canvas.show(img)
        self._canvas.set_rects(ph.rects)
        self._refresh_pharma_candidates()
        self._apply_ocr_pharma(path)
        self._update_warn()
        if not ph.period_read:
            threading.Thread(target=self._ocr_worker, args=(path, img), daemon=True).start()
        self._schedule_apply(now=True)
        if guessed:
            self._st.config(text=guessed)

    def _on_files_empty(self):
        self._current_path = self._cv_img = self._cv_result = None
        self._history.clear()
        self._canvas.clear()
        self._res_canvas.delete("all")
        self._warn.place_forget()
        self._label_lbl.config(text="")
        self._st.config(text="사진을 열거나 창에 드래그 & 드롭하세요.")

    def _on_thumb_select(self, i):
        self._files.select(i)
        self._thumb_panel.canvas.focus_set()      # 목록을 눌렀으니 Delete는 파일 삭제용이 된다

    def _on_ctrl_key(self, event):
        """Ctrl+C: 선택한 박스 복사 / Ctrl+V: 복사한 박스를 사진 한가운데에 붙임.
        글자 입력칸에서는 Shortcuts 가 걸러 주므로 원래의 복사·붙여넣기가 된다. 한글 자판에서도 되게 키코드(C=67, V=86)로 판별."""
        if event.state & 0x20000:                  # Alt 조합은 제외 (0x8은 NumLock이라 보지 않는다)
            return None
        if event.keycode == 67:
            n = self._canvas.copy_selected()
            if n:
                self._st.config(text=f"박스 {n}개 복사 — Ctrl+V로 가운데에 붙여넣기")
                return "break"
        elif event.keycode == 86:
            if self._cv_img is None:
                return None
            n = self._canvas.paste()
            if n:
                self._st.config(text=f"박스 {n}개 붙여넣기")
                self._canvas.focus_set()
                return "break"
            self._st.config(text="복사해 둔 박스가 없습니다 (박스를 선택하고 Ctrl+C)")
        return None

    def _on_key_delete_file(self, event):
        """Delete: 박스가 선택돼 있으면 박스 삭제 / 화면(캔버스)에 포커스가 있으면 아무것도 안 지움 /
        파일 목록 쪽에 포커스가 있을 때만 파일을 목록에서 뺀다."""
        f = self.focus_get()
        if self._canvas.selected_indices():
            n = len(self._canvas.selected_indices())
            self._canvas.delete_selected()
            self._st.config(text=f"박스 {n}개 삭제")
            return
        if f in (self._canvas, self._res_canvas):
            return
        self._files.remove_current()

    def _note_removed(self, items):
        self._schedule_notes_done()                      # 목록이 줄면 완료거래처 수도 다시 센다
        if getattr(self, "_quiet_removed", False):
            return
        self._file_undo.append(list(items))
        self._file_redo.clear()

    def _undo_file_delete(self):
        if not self._file_undo:
            return False
        items = self._file_undo.pop()
        self._files.restore(items)
        self._file_redo.append(items)
        self._file_msg = f"삭제한 파일 {len(items)}개를 되돌렸습니다."
        return True

    def _redo_file_delete(self):
        if not self._file_redo:
            return False
        items = self._file_redo.pop()
        self._quiet_removed = True
        try:
            gone = self._files.remove_paths([p for _, p in items])
        finally:
            self._quiet_removed = False
        self._file_undo.append(gone)
        self._file_msg = f"파일 {len(gone)}개를 다시 목록에서 뺐습니다."
        return True

    # ── 통계기간 OCR ─────────────────────────────────────────────────────

    def _ocr_worker(self, path, img):
        self._ocr_q.put(("period", path, period_check.read_period(img)))
        self._ocr_q.put(("pharma", path, period_check.read_pharma(img)))

    def _poll_ocr(self):
        try:
            while True:
                kind, path, val = self._ocr_q.get_nowait()
                if kind == "period":
                    self._photos.set_period(path, val)
                    if path == self._current_path:
                        self._update_warn()
                else:
                    self._photos.set_ocr_pharma(path, val)
                    self._apply_ocr_pharma(path)
        except queue.Empty:
            pass
        self._poll_excel()
        self.after(200, self._poll_ocr)

    def _selected_ym(self):
        m = rxmonth.parse(self._month_var.get())
        return rxmonth.year_for(m), m

    @staticmethod
    def _default_month_label():
        return rxmonth.label(rxmonth.default_month())

    @staticmethod
    def _ym_of(ph):
        """사진 한 장의 (처방 연도, 월) — 그 사진에 정해 둔 월 기준."""
        m = rxmonth.parse(ph.month or App._default_month_label())
        return rxmonth.year_for(m), m

    def _update_warn(self):
        """좌측 화면 우측상단에 빨간 '통계기간확인'. OCR 전에는 숨기고, 못 읽거나 다르면 표시."""
        p = self._current_path
        status = self._photos.period_status(p, *self._selected_ym()) if p else None
        if status is None:
            self._warn.place_forget()
            return
        ok, why = status
        if ok:
            self._warn.place_forget()
            self._st.config(text=f"통계기간 확인됨: {why}")
        else:
            self._warn.place(relx=1.0, x=-8, y=8, anchor="ne")
            self._warn.lift()
            self._st.config(text=f"통계기간확인 필요: {why}")

    # ── 입력 변경 ────────────────────────────────────────────────────────

    def _on_month_change(self, event=None):
        self._remember()                                    # 바꾼 월은 지금 보는 사진에만 기록된다
        self._refresh_pharma_candidates()
        self._refresh_notes()
        self._update_warn()
        self._schedule_apply()

    def _on_text_change(self, *a):
        if self._master and self._hospital_var.get().strip() != getattr(self, "_cand_for", None):
            self._cand_for = self._hospital_var.get().strip()
            self._refresh_pharma_candidates()
            self._schedule_notes()
        else:
            self._notes.highlight(self._pharma_var.get())
        self._schedule_apply()

    def _label(self):
        h, p = self._hospital_var.get().strip(), self._pharma_var.get().strip()
        if not (h and p):
            return None
        return labeling.build_label(h, self._month_var.get(), p)

    def _schedule_apply(self, now=False):
        if self._apply_job:
            self.after_cancel(self._apply_job)
        self._apply_job = self.after(1 if now else 150, self._apply)

    def _apply(self):
        self._apply_job = None
        if self._cv_img is None:
            return
        label = self._label()
        self._label_lbl.config(text=label or "")
        text = label or "(병원명 / 제약사명을 입력하세요)"
        self._cv_result = labeling.render(self._cv_img, text, self._canvas.get_rects())
        self._render_result()

    def _render_result(self):
        self._res_canvas.delete("all")
        if self._cv_result is None:
            return
        cw, ch = max(self._res_canvas.winfo_width(), 200), max(self._res_canvas.winfo_height(), 200)
        h, w = self._cv_result.shape[:2]
        s = min((cw - 4) / w, (ch - 4) / h)
        nw, nh = max(1, int(w * s)), max(1, int(h * s))
        small = cv2.resize(self._cv_result, (nw, nh), interpolation=cv2.INTER_AREA)
        self._tk_res = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)))
        self._res_canvas.create_image((cw - nw) // 2, (ch - nh) // 2, anchor="nw", image=self._tk_res)

    # ── 박스 편집 ────────────────────────────────────────────────────────

    def _restore_rects(self, snapshot):
        self._canvas.set_rects(snapshot)
        self._schedule_apply()

    def _history_status(self, action, ok):
        if self._file_msg:
            self._st.config(text=self._file_msg)
            self._file_msg = None
            return
        n = len(self._canvas.get_rects())
        word = "실행 취소함" if action == "undo" else "다시 실행함"
        self._st.config(text=f"{word} (박스 {n}개)" if ok else "더 할 수 있는 작업이 없습니다.")

    def _on_rect_edit(self, kind, pre, index=None):
        self._history.push(pre)
        self._schedule_apply()

    def _on_rect_select(self, idx):
        if idx is not None:
            self._thick_var.set(self._canvas.selected_thickness())

    def _add_rect(self):
        if self._cv_img is None:
            messagebox.showwarning("알림", "먼저 사진을 열어주세요.")
            return
        # 박스 두께는 결과(가로 2500px) 기준 값이라 원본 해상도 비율로 환산해서 저장하지 않고 그대로 쓴다
        self._canvas.add_rect(hw_ratio=0.3, hh_ratio=0.04, thickness=self._thick_var.get())
        self._canvas.focus_set()          # 바로 방향키로 움직일 수 있게

    def _rotate(self, deg):
        if self._canvas.selected_index() is None:
            messagebox.showinfo("알림", "회전할 박스를 먼저 클릭해 선택하세요.")
            return
        self._canvas.rotate_selected(deg)

    def _delete_selected_rect(self):
        if self._canvas.selected_index() is None:
            messagebox.showinfo("알림", "선택된 박스가 없습니다. 박스를 클릭해 선택하세요.")
            return
        self._canvas.delete_selected()

    def _clear_all_rects(self):
        if self._canvas.clear_rects():
            self._st.config(text="박스를 모두 지웠습니다.")

    def _on_thickness_change(self, *a):
        if self._canvas.selected_index() is not None:
            try:
                self._canvas.set_selected_thickness(self._thick_var.get())
            except tk.TclError:
                return
            self._schedule_apply()

    # ── 열기 / 드롭 ──────────────────────────────────────────────────────

    def _on_drop(self, event):
        files = self.tk.splitlist(event.data)
        imgs = [f for f in files if Path(f).suffix.lower() in IMAGE_EXT]
        if imgs:
            self._files.add_files(imgs)

    def _open_file(self):
        ps = filedialog.askopenfilenames(
            filetypes=[("이미지", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp"), ("모든 파일", "*.*")])
        if ps:
            self._files.add_files(list(ps))

    def _open_folder(self):
        d = filedialog.askdirectory()
        if not d:
            return
        fs = sorted(str(f) for f in Path(d).iterdir() if f.suffix.lower() in IMAGE_EXT)
        if fs:
            self._files.add_files(fs)
        else:
            messagebox.showinfo("알림", "지원하는 이미지가 없습니다.")

    # ── 저장 ─────────────────────────────────────────────────────────────

    def _save_one(self, path, img, hospital, pharma, rects, status=ledger.DONE, month=None):
        """사진 한 장 저장 (JPG + 장부 반영 맡기기). 순서는 saving.save_photo. (저장 경로, 엑셀 상태 문구)를 돌려준다."""
        return saving.save_photo(img, path, hospital, pharma, rects, month or self._month_var.get(),
                                 out_dir=self._out_dir, ledger=self._ledger, settings=self._settings, status=status)

    def _poll_excel(self):
        for ev in self._ledger.poll():
            if ev.kind == "done":
                self._apply_master()
                left = self._ledger.pending
                self._st.config(text=f"엑셀 반영 완료: {ev.message}" + (f"  (남은 {left}건)" if left else ""))
            elif ev.kind == "error":
                self._xl_fail.append(ev.message)
        if self._xl_fail and self._ledger.pending <= 0:
            msg, self._xl_fail = self._xl_fail[0], []
            messagebox.showwarning("엑셀", f"엑셀 반영 실패: {msg}")

    def _copy_original(self, idx=None):
        """같은 원본으로 통계를 여러 개 만들 수 있게, 사진을 복사해 파일 목록의 원본 바로 아래에 넣고 그 복사본으로 이동한다.
        복사본은 임시 폴더에 두므로 원본 폴더는 건드리지 않는다. 병원명만 이어받고 제약사·박스는 비워 둔다."""
        files = self._files.files
        if idx is None:
            idx = self._files.index
        if not files or not (0 <= idx < len(files)):
            messagebox.showwarning("알림", "먼저 사진을 열어주세요.")
            return
        self._remember()
        src = files[idx]
        try:
            dest = make_copy(src, self._copy_dir, files)
        except Exception as e:
            messagebox.showerror("오류", f"원본 복사 실패: {e}")
            return
        self._photos.copy_of(src, dest)
        self._files.insert_after(idx, dest)
        self._st.config(text=f"원본 복사: {Path(dest).name}  (병원명·박스를 이어받음 — 제약사를 새로 입력하세요)")

    def _on_close(self):
        shutil.rmtree(self._copy_dir, ignore_errors=True)       # 원본 복사본(임시 파일) 정리
        self._notes.flush()
        self._ledger.wait()                  # 엑셀 저장 도중에 창을 닫아 파일이 깨지는 일이 없게 기다린다
        self.destroy()

    def _choose_out_dir(self):
        """JPG 저장 폴더를 지정하고 기억한다. 취소하면 False."""
        d = filedialog.askdirectory(title="JPG 저장 폴더 선택",
                                    initialdir=str(self._out_dir) if self._out_dir else None)
        if not d:
            return False
        self._settings.set_out_dir(d)
        self._show_out_dir()
        self._reload_source()
        return True

    def _show_out_dir(self):
        self._out_lbl.config(text=f"JPG 저장: {self._out_dir}" if self._out_dir else "JPG 저장 폴더: 미지정")

    def _ensure_out_dir(self):
        return bool(self._out_dir) or self._choose_out_dir()

    def _save_current(self, status=ledger.DONE):
        if self._cv_img is None or not self._current_path:
            messagebox.showwarning("알림", "먼저 사진을 열어주세요.")
            return
        if not self._label():
            messagebox.showwarning("알림", "병원명과 제약사명을 입력해주세요.")
            return
        if not self._ensure_out_dir():
            return
        if self._warn.winfo_ismapped() and not messagebox.askyesno(
                "통계기간확인", "통계 기간이 선택한 월과 다르거나 읽지 못했습니다.\n그래도 저장할까요?"):
            return
        try:
            out, xl = self._save_one(self._current_path, self._cv_img, self._hospital_var.get().strip(),
                                     self._pharma_var.get().strip(), self._canvas.get_rects(), status)
        except Exception as e:
            messagebox.showerror("오류", f"저장 실패: {e}")
            return
        self._st.config(text=f"저장됨: {out.name}  |  {xl}")
        if status == ledger.NOSETTLE:       # 정산불가로 끝낸 제약사도 체크 -> 썸네일 체크 + 드롭다운 ✓ 로 구분
            self._remember()
            self._thumb_panel.set_checked(self._current_path, True)
        if "실패" in xl:
            messagebox.showwarning("엑셀", xl)

    def _save_all(self):
        self._remember()
        if not self._ensure_out_dir():
            return
        todo, skipped = self._photos.plan_save(self._files.files)
        if not todo:
            messagebox.showinfo("알림", "병원명·제약사명이 입력된 사진이 없습니다.")
            return
        bad = self._photos.period_problems(todo, self._ym_of)
        if bad and not messagebox.askyesno(
                "통계기간확인", f"통계기간 확인이 필요한 사진이 {len(bad)}장 있습니다.\n"
                               + "\n".join(bad[:8]) + "\n\n그래도 모두 저장할까요?"):
            return
        done, xl_fail = 0, []
        for ph in todo:
            p = ph.path
            img = self._cv_img if p == self._current_path else read_image(p)
            try:
                _, xl = self._save_one(p, img, ph.hospital.strip(), ph.pharma.strip(), ph.rects,
                                   month=ph.month or self._default_month_label())
                done += 1
                if "실패" in xl:
                    xl_fail.append(xl)
            except Exception as e:
                messagebox.showerror("오류", f"{Path(p).name} 저장 실패: {e}")
        if xl_fail:
            messagebox.showwarning("엑셀", f"{len(xl_fail)}건 엑셀 반영 실패\n{xl_fail[0]}")
        msg = f"{done}장 저장 완료"
        if skipped:
            msg += f" (입력 안 된 {len(skipped)}장은 건너뜀)"
        self._st.config(text=msg)


if __name__ == "__main__":
    App().mainloop()
