import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import json
import threading
from pathlib import Path
from tkinterdnd2 import TkinterDnD, DND_FILES

import photo_sort
import photos
from review import format_review
from roster import ExcelParseError, add_entry, parse_excel, update_entry

try:
    import pharma_zip
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# ── PyInstaller 경로 처리 ─────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    _APP_DIR = Path(sys.executable).parent
else:
    _APP_DIR = Path(__file__).parent

CONFIG_FILE = _APP_DIR / "config.json"


# ── 설정 ─────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(data: dict) -> None:
    try:
        CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ── DnD 헬퍼 ─────────────────────────────────────────────────────────────────

def _parse_dnd_path(data: str) -> str:
    data = data.strip()
    if data.startswith("{"):
        return data[1 : data.index("}")]
    return data.split()[0]


def register_drop_zone(
    frame: ttk.LabelFrame,
    widgets: list,
    default_label: str,
    hover_label: str,
    on_drop,
) -> None:
    """frame + widgets를 DnD 드롭 대상으로 등록하고 hover 상태를 관리."""
    def _enter(e): frame.config(text=hover_label)
    def _leave(e): frame.config(text=default_label)
    def _drop(e):
        frame.config(text=default_label)
        on_drop(e)

    for w in widgets:
        w.drop_target_register(DND_FILES)
        w.dnd_bind("<<DragEnter>>", _enter)
        w.dnd_bind("<<DragLeave>>", _leave)
        w.dnd_bind("<<Drop>>", _drop)


# ── GUI ──────────────────────────────────────────────────────────────────────

class PictureDivider:
    _DIR_LABEL   = " ① 사진 폴더 선택  (끌어다 놓기 가능) "
    _EXCEL_LABEL = " ② 분류 기준 엑셀 업로드  (끌어다 놓기 가능) "

    def __init__(self, root):
        self.root = root
        self.root.title("사진 분류 프로그램")
        self.root.geometry("900x720")
        self.root.resizable(True, True)

        self.photo_dir  = tk.StringVar()
        self.excel_path = tk.StringVar()
        self.excel_data: list[dict] = []
        self.unmatched_hospitals: list[str] = []
        self.status_var = tk.StringVar(value="준비")

        cfg = load_config()
        if cfg.get("excel_path") and os.path.exists(cfg["excel_path"]):
            self.excel_path.set(cfg["excel_path"])
        if cfg.get("photo_dir") and os.path.exists(cfg.get("photo_dir", "")):
            self.photo_dir.set(cfg["photo_dir"])

        self._setup_ui()

        if self.excel_path.get():
            self._load_excel(self.excel_path.get(), silent=True)

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=2)
        main.rowconfigure(4, weight=1)

        # ① 사진 폴더
        self.dir_frame = ttk.LabelFrame(main, text=self._DIR_LABEL, padding=8)
        self.dir_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.dir_frame.columnconfigure(0, weight=1)

        dir_row = ttk.Frame(self.dir_frame)
        dir_row.grid(row=0, column=0, sticky="ew")
        dir_row.columnconfigure(0, weight=1)

        dir_entry = ttk.Entry(dir_row, textvariable=self.photo_dir, font=("", 10))
        dir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(dir_row, text="폴더 선택", command=self._browse_dir, width=10).grid(row=0, column=1)

        register_drop_zone(
            self.dir_frame, [self.dir_frame, dir_entry],
            self._DIR_LABEL, " ① 사진 폴더 ← 여기에 놓으세요 ",
            self._on_dir_drop,
        )

        # ② 엑셀 파일
        self.excel_frame = ttk.LabelFrame(main, text=self._EXCEL_LABEL, padding=8)
        self.excel_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.excel_frame.columnconfigure(0, weight=1)

        excel_row = ttk.Frame(self.excel_frame)
        excel_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        excel_row.columnconfigure(0, weight=1)

        excel_entry = ttk.Entry(excel_row, textvariable=self.excel_path, state="readonly", font=("", 10))
        excel_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(excel_row, text="엑셀 업로드", command=self._browse_excel, width=10).grid(row=0, column=1)

        register_drop_zone(
            self.excel_frame, [self.excel_frame, excel_entry],
            self._EXCEL_LABEL, " ② 엑셀 파일 ← 여기에 놓으세요 ",
            self._on_excel_drop,
        )

        # 거래처 테이블
        tbl_frame = ttk.Frame(self.excel_frame)
        tbl_frame.grid(row=1, column=0, sticky="nsew")
        tbl_frame.columnconfigure(0, weight=1)
        tbl_frame.rowconfigure(0, weight=1)
        self.excel_frame.rowconfigure(1, weight=1)

        cols = ("거래처명", "담당자")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=8)
        self._sort_reverse = {col: False for col in cols}
        for col in cols:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by_column(c))
        self.tree.column("거래처명", width=380, anchor="w")
        self.tree.column("담당자", width=180, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", lambda e: self._edit_entry())

        edit_row = ttk.Frame(self.excel_frame)
        edit_row.grid(row=2, column=0, sticky="e", pady=(6, 0))
        ttk.Button(edit_row, text="병원 추가", command=self._add_entry, width=10).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(edit_row, text="선택 수정", command=self._edit_entry, width=10).grid(row=0, column=1)

        # 버튼
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=3, column=0, pady=8)
        btn_zip = ttk.Button(btn_frame, text="①  제약사별 폴더 만들기", command=self._zip_pharma, width=22)
        btn_zip.grid(row=0, column=0, padx=6, pady=(0, 4))
        btn_sort = ttk.Button(btn_frame, text="②  병원별 사진 분류", command=self._sort_photos, width=20)
        btn_sort.grid(row=0, column=1, padx=6, pady=(0, 4))
        btn_undo = ttk.Button(btn_frame, text="③  병원별 분류 되돌리기", command=self._undo_sort, width=22)
        btn_undo.grid(row=0, column=2, padx=6, pady=(0, 4))
        btn_clear = ttk.Button(btn_frame, text="로그 지우기", command=self._clear_log, width=12)
        btn_clear.grid(row=1, column=0, padx=6)
        btn_reset = ttk.Button(btn_frame, text="초기화", command=self._reset, width=10)
        btn_reset.grid(row=1, column=1, padx=6)
        self._buttons = [btn_zip, btn_sort, btn_undo, btn_clear, btn_reset]

        # 로그
        log_frame = ttk.LabelFrame(main, text=" 분류 결과 ", padding=8)
        log_frame.grid(row=4, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=10, wrap=tk.WORD, font=("Consolas", 9), state="normal"
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.tag_config("ok",    foreground="#1a7a1a")
        self.log_text.tag_config("fuzzy", foreground="#b36b00")
        self.log_text.tag_config("fail",  foreground="#cc2200")
        self.log_text.tag_config("info",  foreground="#0055aa")

        # 상태바
        ttk.Label(
            self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=(6, 2)
        ).grid(row=1, column=0, sticky="ew")

    # ── DnD 드롭 핸들러 ──────────────────────────────────────────────────────

    def _on_dir_drop(self, event):
        path = _parse_dnd_path(event.data)
        if os.path.isdir(path):
            self.photo_dir.set(path)
            self._save_cfg()
            self.status_var.set(f"폴더 드롭: {path}")
        else:
            messagebox.showwarning("경고", "폴더를 끌어다 놓아주세요.\n(파일이 아닌 폴더를 선택하세요)")

    def _on_excel_drop(self, event):
        path = _parse_dnd_path(event.data)
        if Path(path).suffix.lower() in (".xlsx", ".xls"):
            self._load_excel(path)
        else:
            messagebox.showwarning("경고", "엑셀 파일(.xlsx, .xls)만 지원합니다.")

    # ── 파일 다이얼로그 ───────────────────────────────────────────────────────

    def _browse_dir(self):
        initial = self.photo_dir.get() or os.path.expanduser("~")
        d = filedialog.askdirectory(title="사진 폴더를 선택하세요", initialdir=initial)
        if d:
            self.photo_dir.set(d)
            self._save_cfg()
            self.status_var.set(f"폴더 선택: {d}")

    def _browse_excel(self):
        initial = os.path.dirname(self.excel_path.get()) if self.excel_path.get() else os.path.expanduser("~")
        fp = filedialog.askopenfilename(
            title="엑셀 파일을 선택하세요",
            initialdir=initial,
            filetypes=[("Excel 파일", "*.xlsx *.xls"), ("모든 파일", "*.*")],
        )
        if fp:
            self._load_excel(fp)

    # ── 엑셀 로드 ────────────────────────────────────────────────────────────

    def _load_excel(self, filepath: str, silent: bool = False) -> None:
        try:
            data = parse_excel(filepath)
        except ExcelParseError as e:
            if not silent:
                messagebox.showwarning("경고", str(e))
            return
        except Exception as e:
            if not silent:
                messagebox.showerror("오류", f"엑셀 파일 읽기 오류:\n{e}")
            return

        self.excel_data = data
        self.excel_path.set(filepath)
        self.tree.delete(*self.tree.get_children())
        for i, item in enumerate(data):
            self.tree.insert("", "end", iid=str(i), values=(item["거래처명"], item["담당자"]))
        self._save_cfg()

        msg = f"엑셀 로드 완료 — {len(data)}개 거래처"
        self.status_var.set(msg)
        if not silent:
            self._log(f"[엑셀] {msg}", "info")

    # ── 거래처 추가/수정 ──────────────────────────────────────────────────────

    def _ask_entry(self, title: str, name: str = "", manager: str = "", suggestions: list[str] = ()):
        """거래처명/담당자 입력창. 확인하면 (거래처명, 담당자), 취소하면 None."""
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.transient(self.root)
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg, padding=12)
        frm.grid()
        name_var, mgr_var = tk.StringVar(value=name), tk.StringVar(value=manager)
        ttk.Label(frm, text="거래처명").grid(row=0, column=0, sticky="w", pady=4)
        name_cb = ttk.Combobox(frm, textvariable=name_var, values=list(suggestions), width=40)
        name_cb.grid(row=0, column=1, padx=(8, 0))
        ttk.Label(frm, text="담당자").grid(row=1, column=0, sticky="w", pady=4)
        managers = sorted({d["담당자"] for d in self.excel_data})
        ttk.Combobox(frm, textvariable=mgr_var, values=managers, width=40).grid(row=1, column=1, padx=(8, 0))
        if suggestions:
            ttk.Label(frm, text="※ 거래처명 목록: 직전 분류에서 매칭되지 않은 병원", foreground="#666").grid(
                row=2, column=0, columnspan=2, sticky="w")

        result = []
        def ok(_e=None):
            n, m = name_var.get().strip(), mgr_var.get().strip()
            if not n or not m:
                messagebox.showwarning("경고", "거래처명과 담당자를 모두 입력하세요.", parent=dlg)
                return
            result.append((n, m))
            dlg.destroy()
        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="확인", command=ok, width=8).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="취소", command=dlg.destroy, width=8).grid(row=0, column=1)
        dlg.bind("<Return>", ok)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        name_cb.focus_set()
        dlg.grab_set()
        self.root.wait_window(dlg)
        return result[0] if result else None

    def _write_excel(self, action) -> bool:
        """엑셀 파일에 반영. 실패해도 화면(메모리)에는 반영하되 사용자에게 알린다."""
        path = self.excel_path.get()
        if not path:
            messagebox.showwarning("경고", "엑셀 파일을 먼저 업로드해주세요.")
            return False
        if Path(path).suffix.lower() != ".xlsx":
            messagebox.showwarning("안내", "xls 파일은 엑셀에 저장할 수 없어 이번 실행 동안만 반영됩니다.")
            return True
        try:
            if action(path) is False:
                messagebox.showwarning("안내", "엑셀에서 해당 줄을 찾지 못해 이번 실행 동안만 반영됩니다.")
        except PermissionError:
            messagebox.showwarning("안내", "엑셀 파일이 열려 있어 저장하지 못했습니다.\n이번 실행 동안만 반영됩니다. 엑셀을 닫고 다시 시도하세요.")
        except Exception as e:
            messagebox.showwarning("안내", f"엑셀 저장 실패 ({e})\n이번 실행 동안만 반영됩니다.")
        return True

    def _add_entry(self):
        if not self.excel_path.get():
            messagebox.showwarning("경고", "엑셀 파일을 먼저 업로드해주세요.")
            return
        known = {d["거래처명"] for d in self.excel_data}
        got = self._ask_entry("병원 추가", suggestions=[h for h in self.unmatched_hospitals if h not in known])
        if not got:
            return
        name, manager = got
        if not self._write_excel(lambda p: add_entry(p, name, manager)):
            return
        self.excel_data.append({"거래처명": name, "담당자": manager})
        i = len(self.excel_data) - 1
        self.tree.insert("", "end", iid=str(i), values=(name, manager))
        self.tree.see(str(i))
        self.status_var.set(f"추가: {name} → {manager}")
        self._log(f"[엑셀] 추가: {name} → {manager}", "info")

    def _edit_entry(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("안내", "수정할 병원을 목록에서 선택하세요.")
            return
        i = int(sel[0])
        old = self.excel_data[i]
        got = self._ask_entry("병원 수정", old["거래처명"], old["담당자"])
        if not got:
            return
        name, manager = got
        if (name, manager) == (old["거래처명"], old["담당자"]):
            return
        if not self._write_excel(lambda p: update_entry(p, old["거래처명"], old["담당자"], name, manager)):
            return
        self.excel_data[i] = {"거래처명": name, "담당자": manager}
        self.tree.item(sel[0], values=(name, manager))
        self.status_var.set(f"수정: {old['거래처명']} → {name} / {manager}")
        self._log(f"[엑셀] 수정: {old['거래처명']}({old['담당자']}) → {name}({manager})", "info")

    def _sort_by_column(self, col: str) -> None:
        reverse = self._sort_reverse[col]
        rows = [(self.tree.set(iid, col), iid) for iid in self.tree.get_children("")]
        rows.sort(key=lambda r: r[0], reverse=reverse)
        for index, (_, iid) in enumerate(rows):
            self.tree.move(iid, "", index)
        self._sort_reverse[col] = not reverse

        cols = ("거래처명", "담당자")
        arrow = " ▼" if reverse else " ▲"
        for c in cols:
            self.tree.heading(c, text=(c + arrow) if c == col else c)

    # ── 제약사별 폴더 ─────────────────────────────────────────────────────────

    def _zip_pharma(self):
        if not _PIL_AVAILABLE:
            messagebox.showerror("오류", "Pillow 라이브러리가 필요합니다.\n터미널에서 'pip install Pillow' 실행 후 재시작하세요.")
            return

        photo_dir = self.photo_dir.get().strip()
        if not photo_dir or not os.path.isdir(photo_dir):
            messagebox.showwarning("경고", "사진 폴더를 선택해주세요.")
            return

        files = photos.list_images(photo_dir)
        if not files:
            self._log("[제약사폴더] 이미지 파일이 없습니다.", "fail")
            return

        out_dir = Path(photo_dir).parent / (Path(photo_dir).name + "_제약사폴더")
        self._run_in_thread(self._zip_pharma_worker, photo_dir, files, out_dir)

    def _zip_pharma_worker(self, photo_dir: str, files: list[str], out_dir: Path):
        def on_event(e: pharma_zip.FolderEvent):
            if e.kind == "start":
                self._log(f"\n{'─'*50}", "info")
                self._log(f"[제약사폴더 시작]  파일: {e.total_files}개  /  제약사: {e.total_pharma}개", "info")
                self._log(f"출력 폴더: {e.out_dir}", "info")
                self._log(f"{'─'*50}", "info")
            elif e.kind == "convert_failed":
                self._log(f"  ✗  변환 실패: {e.filename} ({e.error})", "fail")
            elif e.kind == "folder_created":
                self._log(
                    f"  ✓  {e.folder_name}  ({e.file_count}개 JPG)  →  {e.folder_name}\\",
                    "ok",
                )
            elif e.kind == "summary":
                self._log(f"{'─'*50}", "info")
                self._log(f"[제약사폴더 완료]  폴더 {e.total_folders}개 생성  →  {e.out_dir}", "info")
                for text, tag in format_review(e.review):
                    self._log(text, tag)
                self.root.after(0, lambda: self.status_var.set(f"제약사폴더 완료 — {e.total_folders}개 폴더 생성"))

        pharma_zip.build_pharma_folders(photo_dir, files, out_dir, on_event=on_event)

    # ── 분류 실행 ────────────────────────────────────────────────────────────

    def _sort_photos(self):
        photo_dir = self.photo_dir.get().strip()
        if not photo_dir:
            messagebox.showwarning("경고", "사진 폴더를 선택해주세요.")
            return
        if not os.path.isdir(photo_dir):
            messagebox.showwarning("경고", "선택한 폴더가 존재하지 않습니다.")
            return
        if not self.excel_data:
            messagebox.showwarning("경고", "엑셀 파일을 먼저 업로드해주세요.")
            return

        lookup = {item["거래처명"]: item["담당자"] for item in self.excel_data}
        files = photos.list_images(photo_dir)
        if not files:
            self._log("[분류] 이미지 파일이 없습니다.", "fail")
            return

        self._run_in_thread(self._sort_photos_worker, photo_dir, files, lookup)

    def _sort_photos_worker(self, photo_dir: str, files: list[str], lookup: dict[str, str]):
        self._log(f"\n{'─'*50}", "info")
        self._log(f"[분류 시작]  폴더: {photo_dir}  /  파일: {len(files)}개", "info")
        self._log(f"{'─'*50}", "info")

        results = photo_sort.classify(files, lookup)
        self.unmatched_hospitals = sorted({r.hospital for r in results if r.match_type == "none"})

        def on_event(e: photo_sort.SortEvent):
            if e.kind == "moved":
                if e.match_type == "exact":
                    self._log(f"  ✓  {e.filename}  →  [{e.manager}]", "ok")
                else:
                    pct = int(e.ratio * 100)
                    self._log(
                        f"  ~  {e.filename}  →  [{e.manager}]"
                        f"  (유사매칭: '{e.hospital}' ≈ '{e.matched_key}'  {pct}%)",
                        "fuzzy",
                    )
            elif e.kind == "summary":
                self._log(f"{'─'*50}", "info")
                self._log(
                    f"[완료]  정확 매칭: {e.moved_exact}개  /  유사 매칭: {e.moved_fuzzy}개  /  미매칭: {e.skipped_count}개",
                    "info",
                )
                for text, tag in format_review(e.review):
                    self._log(text, tag)

                msg = f"완료 — 정확 {e.moved_exact}개 / 유사 {e.moved_fuzzy}개 / 미매칭 {e.skipped_count}개"
                self.root.after(0, lambda: self.status_var.set(msg))

        photo_sort.execute_moves(photo_dir, results, on_event=on_event)

    # ── 분류 되돌리기 ─────────────────────────────────────────────────────────

    def _undo_sort(self):
        photo_dir = self.photo_dir.get().strip()
        if not photo_dir or not os.path.isdir(photo_dir):
            messagebox.showwarning("경고", "사진 폴더를 선택해주세요.")
            return
        if not photo_sort.has_undo(photo_dir):
            messagebox.showinfo("안내", "되돌릴 분류 기록이 없습니다.\n(이 폴더에서 병원별 분류를 실행한 적이 없거나 이미 되돌렸습니다)")
            return
        if not messagebox.askyesno("되돌리기 확인", "마지막 병원별 분류를 되돌릴까요?\n담당자 폴더의 사진이 원래 위치로 돌아옵니다."):
            return
        self._run_in_thread(self._undo_sort_worker, photo_dir)

    def _undo_sort_worker(self, photo_dir: str):
        self._log(f"\n{'─'*50}", "info")
        restored, errors = photo_sort.undo_last_sort(photo_dir)
        self._log(f"[되돌리기 완료]  {restored}개 파일을 원래 위치로 복원", "info")
        for msg in errors:
            self._log(f"  ✗  {msg}", "fail")
        self.root.after(0, lambda: self.status_var.set(f"되돌리기 완료 — {restored}개 복원"))

    # ── 처리 중 상태 관리 / 스레드 헬퍼 ─────────────────────────────────────

    def _set_processing(self, active: bool):
        state = "disabled" if active else "normal"
        for btn in self._buttons:
            btn.configure(state=state)
        if active:
            self.status_var.set("처리 중…")

    def _run_in_thread(self, worker, *args):
        self._set_processing(True)
        def _run():
            try:
                worker(*args)
            except Exception as e:
                self._log(f"[오류] {e}", "fail")
            finally:
                self.root.after(0, lambda: self._set_processing(False))
        threading.Thread(target=_run, daemon=True).start()

    # ── 로그 (스레드 안전) ────────────────────────────────────────────────────

    def _log(self, msg: str, tag: str | None = None):
        def _insert():
            self.log_text.configure(state="normal")
            if tag:
                self.log_text.insert(tk.END, msg + "\n", tag)
            else:
                self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
        self.root.after(0, _insert)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)

    # ── 초기화 ───────────────────────────────────────────────────────────────

    def _reset(self):
        if not messagebox.askyesno("초기화 확인", "폴더 경로, 엑셀 데이터, 로그를 모두 초기화할까요?"):
            return
        self.photo_dir.set("")
        self.excel_path.set("")
        self.excel_data = []
        self.tree.delete(*self.tree.get_children())
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.status_var.set("초기화 완료")
        save_config({})

    def _save_cfg(self):
        save_config({"photo_dir": self.photo_dir.get(), "excel_path": self.excel_path.get()})


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


def _apply_window_icon(win):
    """소스 실행·exe 실행 모두에서 app.ico를 창 아이콘으로 적용한다."""
    here = Path(__file__).resolve().parent
    for root in (Path(getattr(sys, "_MEIPASS", here)), here, here.parent):
        ico = root / "app.ico"
        if ico.exists():
            try:
                win.iconbitmap(default=str(ico))
                _crisp_taskbar_icon(win, ico)
            except Exception:
                pass
            return


def main():
    root = TkinterDnD.Tk()
    _apply_window_icon(root)
    style = ttk.Style(root)
    available = style.theme_names()
    for theme in ("vista", "winnative", "clam", "alt"):
        if theme in available:
            style.theme_use(theme)
            break
    PictureDivider(root)
    root.mainloop()


if __name__ == "__main__":
    main()
