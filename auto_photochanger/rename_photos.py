import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from pathlib import Path

from tkinterdnd2 import TkinterDnD, DND_FILES

import settings
from extractor import AnthropicExtractor, CreditExhaustedError
from renamer import ClinicMap, Renamer

_DEFAULT_EXCEL = r"C:\Users\JW\Desktop\사진리네임\사진이름 변경 툴.xlsx"


def _parse_drop(data: str) -> str:
    """tkinterdnd2 드롭 이벤트 데이터에서 첫 번째 경로 추출."""
    data = data.strip()
    if data.startswith("{"):
        return data[1:data.index("}")]
    return data.split()[0]


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("사진 자동 리네임")
        self.resizable(False, False)
        self._cfg = settings.load()
        self.running = False
        self._build_ui()

    def _build_ui(self):
        p = {"padx": 8, "pady": 5}

        # API 키
        f1 = ttk.LabelFrame(self, text="API 키 설정")
        f1.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        ttk.Label(f1, text="Anthropic API 키:").grid(row=0, column=0, **p, sticky="w")
        self.api_var = tk.StringVar(value=self._cfg.get("api_key", ""))
        ttk.Entry(f1, textvariable=self.api_var, width=48, show="*").grid(row=0, column=1, **p)
        ttk.Button(f1, text="저장", command=self._save_api_key, width=8).grid(row=0, column=2, **p)

        # 실행 설정
        f2 = ttk.LabelFrame(self, text="실행 설정")
        f2.grid(row=1, column=0, sticky="ew", padx=10, pady=4)

        # 원본 폴더
        ttk.Label(f2, text="원본 폴더:").grid(row=0, column=0, **p, sticky="w")
        self.folder_var = tk.StringVar()
        folder_entry = ttk.Entry(f2, textvariable=self.folder_var, width=42)
        folder_entry.grid(row=0, column=1, **p)
        ttk.Button(f2, text="찾아보기", command=self._browse_folder, width=8).grid(row=0, column=2, **p)
        self._register_drop(folder_entry, self.folder_var, kind="folder")

        # 엑셀 파일
        ttk.Label(f2, text="엑셀 파일:").grid(row=1, column=0, **p, sticky="w")
        default_excel = self._cfg.get("excel_path", _DEFAULT_EXCEL)
        self.excel_var = tk.StringVar(value=default_excel)
        excel_entry = ttk.Entry(f2, textvariable=self.excel_var, width=42)
        excel_entry.grid(row=1, column=1, **p)
        ttk.Button(f2, text="찾아보기", command=self._browse_excel, width=8).grid(row=1, column=2, **p)
        self._register_drop(excel_entry, self.excel_var, kind="excel")

        # 저장 폴더
        ttk.Label(f2, text="저장 폴더:").grid(row=2, column=0, **p, sticky="w")
        self.output_var = tk.StringVar(value=self._cfg.get("output_path", ""))
        output_entry = ttk.Entry(f2, textvariable=self.output_var, width=42)
        output_entry.grid(row=2, column=1, **p)
        ttk.Button(f2, text="찾아보기", command=self._browse_output, width=8).grid(row=2, column=2, **p)
        ttk.Label(f2, text="(비우면 원본 폴더에 저장)", foreground="gray").grid(
            row=3, column=1, sticky="w", padx=8, pady=(0, 2))
        self._register_drop(output_entry, self.output_var, kind="output")

        # 월 + 실행
        ttk.Label(f2, text="월:").grid(row=4, column=0, **p, sticky="w")
        self.month_var = tk.StringVar()
        ttk.Entry(f2, textvariable=self.month_var, width=10).grid(row=4, column=1, **p, sticky="w")
        self.run_btn = ttk.Button(f2, text="▶  실행", command=self._run, width=12)
        self.run_btn.grid(row=4, column=2, **p)

        # 로그
        f3 = ttk.LabelFrame(self, text="처리 로그")
        f3.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 10))
        self.log = scrolledtext.ScrolledText(f3, height=14, width=70, state="disabled",
                                             font=("Consolas", 9))
        self.log.pack(padx=6, pady=6)

    def _register_drop(self, widget, var: tk.StringVar, kind: str):
        widget.drop_target_register(DND_FILES)

        def on_drop(event):
            path = _parse_drop(event.data)
            var.set(path)
            if kind == "excel":
                self._cfg["excel_path"] = path
                settings.save(self._cfg)
            elif kind == "output":
                self._cfg["output_path"] = path
                settings.save(self._cfg)

        widget.dnd_bind("<<Drop>>", on_drop)

    def _save_api_key(self):
        self._cfg["api_key"] = self.api_var.get().strip()
        settings.save(self._cfg)
        messagebox.showinfo("저장 완료", "API 키가 저장되었습니다.")

    def _browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def _browse_excel(self):
        path = filedialog.askopenfilename(
            filetypes=[("Excel 파일", "*.xlsx *.xls"), ("모든 파일", "*.*")]
        )
        if path:
            self.excel_var.set(path)
            self._cfg["excel_path"] = path
            settings.save(self._cfg)

    def _browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)
            self._cfg["output_path"] = folder
            settings.save(self._cfg)

    def _log(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _run(self):
        if self.running:
            return
        api_key = self.api_var.get().strip()
        folder  = self.folder_var.get().strip()
        excel   = self.excel_var.get().strip()
        output  = self.output_var.get().strip()
        month   = self.month_var.get().strip()

        if not api_key:
            messagebox.showwarning("확인", "API 키를 입력하고 저장해주세요.")
            return
        if not folder:
            messagebox.showwarning("확인", "원본 폴더를 선택해주세요.")
            return
        if not excel:
            messagebox.showwarning("확인", "엑셀 파일을 선택해주세요.")
            return
        if not month:
            messagebox.showwarning("확인", "월을 입력해주세요.")
            return

        try:
            clinic_map = ClinicMap.from_excel(excel)
        except Exception as e:
            messagebox.showerror("엑셀 오류", f"엑셀 파일을 읽을 수 없습니다:\n{e}")
            return

        output_path = Path(output) if output else None
        if output_path:
            output_path.mkdir(parents=True, exist_ok=True)

        self.running = True
        self.run_btn.configure(state="disabled", text="처리 중...")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

        threading.Thread(
            target=self._process,
            args=(api_key, folder, clinic_map, month, output_path),
            daemon=True,
        ).start()

    def _process(self, api_key, folder, clinic_map, month, output_path):
        try:
            extractor = AnthropicExtractor(api_key=api_key)
            renamer   = Renamer(extractor)
            try:
                results = renamer.rename(Path(folder), clinic_map, month, output_path)
            except CreditExhaustedError as e:
                self._log("━" * 40)
                self._log(f"[크레딧부족] 처리 중단 — {e}")
                self._log("console.anthropic.com → Billing에서 충전 후 재실행하세요.")
                self._log("━" * 40)
                return

            if not results:
                self._log("처리할 파일이 없습니다.")
                return

            self._log(f"총 {len(results)}개 파일 처리 시작\n")
            for r in results:
                if r.success:
                    self._log(f"[완료] → {r.new_name}\n")
                elif r.error_kind == "mapping":
                    self._log(f"[매핑없음] {r.original}: {r.error}\n")
                else:
                    self._log(f"[API오류] {r.original}: {r.error}\n")

            success  = sum(1 for r in results if r.success)
            mapping_fail = sum(1 for r in results if r.error_kind == "mapping")
            api_fail = sum(1 for r in results if r.error_kind == "api")
            self._log("─" * 40)
            self._log(f"완료 {success}  매핑없음 {mapping_fail}  API오류 {api_fail}")

        finally:
            self.running = False
            self.run_btn.configure(state="normal", text="▶  실행")


if __name__ == "__main__":
    App().mainloop()
