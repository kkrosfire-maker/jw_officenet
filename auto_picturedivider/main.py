import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import json
import threading
import openpyxl
from pathlib import Path
from tkinterdnd2 import TkinterDnD, DND_FILES

import photo_sort

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


# ── 엑셀 파싱 ─────────────────────────────────────────────────────────────────

class ExcelParseError(Exception):
    pass


def parse_excel(filepath: str) -> list[dict]:
    """엑셀에서 거래처명/담당자 목록을 파싱해 반환.

    Raises:
        ExcelParseError: 빈 파일이거나 유효한 데이터 행이 없을 때
        Exception: openpyxl 읽기 실패
    """
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        raise ExcelParseError("엑셀 파일이 비어 있습니다.")

    # 첫 행 헤더 여부 자동 감지
    start_row = 0
    first = [str(c).strip() if c else "" for c in rows[0]]
    if any(k in " ".join(first) for k in ["거래처", "담당자", "이름", "성명"]):
        start_row = 1

    data = []
    for row in rows[start_row:]:
        if len(row) < 2:
            continue
        name = str(row[0]).strip() if row[0] else ""
        manager = str(row[1]).strip() if row[1] else ""
        if name and manager:
            data.append({"거래처명": name, "담당자": manager})

    if not data:
        raise ExcelParseError("유효한 데이터가 없습니다.\n(거래처명, 담당자 열을 확인하세요)")

    return data


# ── 분류기 ───────────────────────────────────────────────────────────────────

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


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

        # 버튼
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=3, column=0, pady=8)
        btn_zip = ttk.Button(btn_frame, text="①  제약사별 ZIP 만들기", command=self._zip_pharma, width=22)
        btn_zip.grid(row=0, column=0, padx=6, pady=(0, 4))
        btn_sort = ttk.Button(btn_frame, text="②  병원별 사진 분류", command=self._sort_photos, width=20)
        btn_sort.grid(row=0, column=1, padx=6, pady=(0, 4))
        btn_clear = ttk.Button(btn_frame, text="로그 지우기", command=self._clear_log, width=12)
        btn_clear.grid(row=1, column=0, padx=6)
        btn_reset = ttk.Button(btn_frame, text="초기화", command=self._reset, width=10)
        btn_reset.grid(row=1, column=1, padx=6)
        self._buttons = [btn_zip, btn_sort, btn_clear, btn_reset]

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
        for item in data:
            self.tree.insert("", "end", values=(item["거래처명"], item["담당자"]))
        self._save_cfg()

        msg = f"엑셀 로드 완료 — {len(data)}개 거래처"
        self.status_var.set(msg)
        if not silent:
            self._log(f"[엑셀] {msg}", "info")

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

    # ── 제약사별 ZIP ──────────────────────────────────────────────────────────

    def _zip_pharma(self):
        if not _PIL_AVAILABLE:
            messagebox.showerror("오류", "Pillow 라이브러리가 필요합니다.\n터미널에서 'pip install Pillow' 실행 후 재시작하세요.")
            return

        photo_dir = self.photo_dir.get().strip()
        if not photo_dir or not os.path.isdir(photo_dir):
            messagebox.showwarning("경고", "사진 폴더를 선택해주세요.")
            return

        files = self._list_images(photo_dir)
        if not files:
            self._log("[제약사ZIP] 이미지 파일이 없습니다.", "fail")
            return

        out_dir = Path(photo_dir).parent / (Path(photo_dir).name + "_제약사ZIP")
        self._run_in_thread(self._zip_pharma_worker, photo_dir, files, out_dir)

    def _zip_pharma_worker(self, photo_dir: str, files: list[str], out_dir: Path):
        def on_event(e: pharma_zip.ZipEvent):
            if e.kind == "start":
                self._log(f"\n{'─'*50}", "info")
                self._log(f"[제약사ZIP 시작]  파일: {e.total_files}개  /  제약사: {e.total_pharma}개", "info")
                self._log(f"출력 폴더: {e.out_dir}", "info")
                self._log(f"{'─'*50}", "info")
            elif e.kind == "convert_failed":
                self._log(f"  ✗  변환 실패: {e.filename} ({e.error})", "fail")
            elif e.kind == "zip_created":
                tag = "fail" if e.over_limit else "ok"
                self._log(
                    f"  ✓  {e.folder_name}  ({e.file_count}개 JPG)  →  {e.folder_name}.zip  [{e.zip_mb:.1f} MB]",
                    tag,
                )
            elif e.kind == "summary":
                self._log(f"{'─'*50}", "info")
                self._log(f"[제약사ZIP 완료]  ZIP {e.total_zips}개 생성  →  {e.out_dir}", "info")
                self.root.after(0, lambda: self.status_var.set(f"제약사ZIP 완료 — {e.total_zips}개 ZIP 생성"))

        pharma_zip.build_pharma_zips(photo_dir, files, out_dir, on_event=on_event)

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
        files = self._list_images(photo_dir)
        if not files:
            self._log("[분류] 이미지 파일이 없습니다.", "fail")
            return

        self._run_in_thread(self._sort_photos_worker, photo_dir, files, lookup)

    def _sort_photos_worker(self, photo_dir: str, files: list[str], lookup: dict[str, str]):
        self._log(f"\n{'─'*50}", "info")
        self._log(f"[분류 시작]  폴더: {photo_dir}  /  파일: {len(files)}개", "info")
        self._log(f"{'─'*50}", "info")

        results = photo_sort.classify(files, lookup)
        skipped_events: list[photo_sort.SortEvent] = []

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
            elif e.kind == "skipped":
                skipped_events.append(e)
            elif e.kind == "summary":
                self._log(f"{'─'*50}", "info")
                self._log(
                    f"[완료]  정확 매칭: {e.moved_exact}개  /  유사 매칭: {e.moved_fuzzy}개  /  미매칭: {e.skipped_count}개",
                    "info",
                )
                if skipped_events:
                    self._log(f"\n[미매칭 목록] 유사도 {int(photo_sort.FUZZY_THRESHOLD*100)}% 미만 — 수동 확인 필요:", "fail")
                    for se in skipped_events:
                        self._log(f"  ✗  {se.filename}  (추출된 거래처명: '{se.hospital}')", "fail")

                msg = f"완료 — 정확 {e.moved_exact}개 / 유사 {e.moved_fuzzy}개 / 미매칭 {e.skipped_count}개"
                self.root.after(0, lambda: self.status_var.set(msg))

        photo_sort.execute_moves(photo_dir, results, on_event=on_event)

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

    def _list_images(self, photo_dir: str) -> list[str]:
        return [
            f for f in os.listdir(photo_dir)
            if os.path.isfile(os.path.join(photo_dir, f))
            and Path(f).suffix.lower() in IMAGE_EXTS
        ]

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


def main():
    root = TkinterDnD.Tk()
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
