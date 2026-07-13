"""
처방약 사용량 분석기 v1.1
의약품 소모 현황 및 제약사별통계 이미지를 AI로 분석하여
제약사별 품목 수량을 자동 집계합니다.

아키텍처:
  DrugDataStore       — 집계 데이터 저장소 (비즈니스 모델)
  ImageAnalyzer       — AI 분석 인터페이스 (seam)
  ClaudeImageAnalyzer — Anthropic API 어댑터
  run_analysis()      — UI 없는 순수 분석 루프
  RxAnalyzer          — tkinter GUI 셸 (표시·입력만 담당)
"""
from __future__ import annotations

import base64
import csv
import io
import json
import os
import re
import threading
from collections import defaultdict
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import anthropic
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic"])
    import anthropic

# ── 상수 ──────────────────────────────────────────────────────────────────────

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".rx_analyzer_settings.json")
DEFAULT_MODEL = "claude-sonnet-4-6"

ANALYSIS_PROMPT = """이 이미지는 한국 의원의 처방약 관련 문서입니다.

다음 두 가지 문서 유형 중 하나입니다:
1. 제약사별통계: 제목에 "제약사별통계" 포함, 제약사명이 "[제약사 : ...]" 형식으로 표시,
   표에 "총사용량" 컬럼이 있음
2. 소모현황: 제목에 "약품 소모 현황" 포함, 회사명이 제목 앞에 붙음(예: "휴니즈 약품 소모 현황"),
   표에 "수 량" 컬럼이 있음

아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{
  "document_type": "제약사별통계" 또는 "소모현황",
  "company": "제약사 또는 회사명",
  "items": [
    {"name": "품목명", "quantity": 숫자},
    ...
  ]
}

규칙:
- 합계/소계/총계 행은 items에 절대 포함하지 않습니다
- 제약사별통계: 각 품목의 "총사용량" 열 값을 quantity로 사용
- 소모현황: 각 품목의 "수 량" 열 값을 quantity로 사용
- quantity는 반드시 정수(숫자만, 쉼표 없이)
- 품목이 없으면 items를 빈 배열로"""


# ════════════════════════════════════════════════════════════════════════
# 1. DrugDataStore — 집계 데이터 저장소
# ════════════════════════════════════════════════════════════════════════

class DrugDataStore:
    """제약사별·품목별 수량 집계.

    내부 구조(중첩 dict)를 외부에 노출하지 않으며,
    add / companies / drugs / totals / clear 인터페이스만 공개한다.
    """

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: {"stat": 0, "usage": 0})
        )

    def add(self, company: str, drug: str, qty: int, kind: str) -> None:
        """kind: "stat"(제약사별통계) | "usage"(소모현황)"""
        self._data[company][drug][kind] += qty

    def companies(self) -> list[str]:
        return sorted(self._data)

    def drugs(self, company: str) -> list[str]:
        return sorted(self._data.get(company, {}))

    def totals(self, company: str, drug: str) -> tuple[int, int]:
        """(stat, usage) 반환"""
        entry = self._data.get(company, {}).get(drug, {})
        return entry.get("stat", 0), entry.get("usage", 0)

    def company_total(self, company: str) -> int:
        return sum(s + u for drug in self.drugs(company)
                   for s, u in [self.totals(company, drug)])

    def grand_total(self) -> int:
        return sum(self.company_total(c) for c in self.companies())

    def item_count(self) -> int:
        return sum(len(self.drugs(c)) for c in self.companies())

    def is_empty(self) -> bool:
        return not self._data

    def clear(self) -> None:
        self._data.clear()


# ════════════════════════════════════════════════════════════════════════
# 2. ImageAnalyzer — AI 분석 seam
# ════════════════════════════════════════════════════════════════════════

@runtime_checkable
class ImageAnalyzer(Protocol):
    """이미지 한 장을 분석해 처방약 데이터 dict를 반환하는 인터페이스.

    반환값 형식: {"document_type": str, "company": str, "items": [...]}
    분석 불가 시 None 반환.
    """
    def analyze(self, path: str) -> dict | None: ...


class ClaudeImageAnalyzer:
    """Anthropic Claude API를 사용하는 ImageAnalyzer 어댑터."""

    _MAX_PX    = 1568
    _MAX_BYTES = 4 * 1024 * 1024

    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model  = model

    def analyze(self, path: str) -> dict | None:
        b64, mime = self._prepare_image(path)
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": ANALYSIS_PROMPT},
                ]
            }]
        )
        return extract_json(resp.content[0].text.strip())

    def _prepare_image(self, path: str) -> tuple[str, str]:
        """이미지를 JPEG base64로 변환. 크기·품질 자동 조정."""
        try:
            from PIL import Image
            img = Image.open(path)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            if max(img.size) > self._MAX_PX:
                img.thumbnail((self._MAX_PX, self._MAX_PX), Image.LANCZOS)
            quality = 88
            while True:
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                if buf.tell() <= self._MAX_BYTES or quality <= 30:
                    break
                quality -= 15
            return base64.standard_b64encode(buf.getvalue()).decode(), "image/jpeg"
        except ImportError:
            with open(path, "rb") as f:
                data = f.read()
            ext = Path(path).suffix.lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
            return base64.standard_b64encode(data).decode(), mime
        except Exception as e:
            raise RuntimeError(f"이미지 변환 실패: {Path(path).name} — {e}") from e


# ════════════════════════════════════════════════════════════════════════
# 3. 모듈 수준 순수 함수
# ════════════════════════════════════════════════════════════════════════

def extract_json(text: str) -> dict | None:
    """Claude 응답 텍스트에서 첫 번째 유효한 JSON 객체를 추출.

    그리디 regex({.*}) 대신 JSONDecoder.raw_decode를 사용해
    응답에 설명 텍스트가 섞여도 올바른 JSON만 반환한다.
    """
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, m.start())
            if isinstance(obj, dict) and obj.get("company"):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def aggregate(data: dict, store: DrugDataStore) -> None:
    """API 응답 dict를 DrugDataStore에 누적."""
    company  = (data.get("company")       or "").strip()
    doc_type = (data.get("document_type") or "").strip()
    if not company or not doc_type:
        return
    kind = "stat" if doc_type == "제약사별통계" else "usage"
    for item in data.get("items", []):
        name = (item.get("name") or "").strip()
        qty  = item.get("quantity", 0)
        if name and isinstance(qty, (int, float)) and qty > 0:
            store.add(company, name, int(qty), kind)


# ════════════════════════════════════════════════════════════════════════
# 4. run_analysis — UI 없는 순수 분석 루프
# ════════════════════════════════════════════════════════════════════════

def run_analysis(
    files:       list[str],
    analyzer:    ImageAnalyzer,
    store:       DrugDataStore,
    on_progress: Callable[[int, int, str], None],
    on_error:    Callable[[str, str], None],
) -> None:
    """파일 목록을 순회하며 분석·집계한다. tkinter 의존성 없음.

    on_progress(current, total, message) — 진행 상황 콜백
    on_error(filename, error_message)    — 오류 콜백
    """
    n = len(files)
    for i, path in enumerate(files):
        name = Path(path).name
        on_progress(i, n, f"({i+1}/{n}) {name} 분석 중...")
        try:
            data = analyzer.analyze(path)
            if data:
                aggregate(data, store)
        except Exception as e:
            on_error(name, str(e)[:120])
    on_progress(n, n, f"완료! {n}개 파일 처리됨")


# ════════════════════════════════════════════════════════════════════════
# 5. RxAnalyzer — tkinter GUI 셸
# ════════════════════════════════════════════════════════════════════════

class RxAnalyzer:
    """표시·입력만 담당. 비즈니스 로직은 run_analysis / DrugDataStore / ClaudeImageAnalyzer에 위임."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("처방약 사용량 분석기 v1.1")
        self.root.geometry("1160x770")
        self.root.minsize(920, 620)

        self.image_files: list[str] = []
        self.store = DrugDataStore()
        self.is_analyzing = False

        self.api_key_var    = tk.StringVar()
        self.model_var      = tk.StringVar(value=DEFAULT_MODEL)
        self.status_var     = tk.StringVar(value="파일을 추가한 후 분석을 시작하세요.")
        self.file_count_var = tk.StringVar(value="0개 파일 선택됨")
        self.summary_var    = tk.StringVar()

        self._load_settings()
        self._build_ui()

    # ── 설정 ──────────────────────────────────────────────────────────

    def _load_settings(self) -> None:
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
            self.api_key_var.set(s.get("api_key", ""))
            self.model_var.set(s.get("model", DEFAULT_MODEL))
        except Exception:
            pass

    def _save_settings(self) -> None:
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({"api_key": self.api_key_var.get(),
                           "model":   self.model_var.get()}, f)
            messagebox.showinfo("저장 완료", "API 설정이 저장되었습니다.")
        except Exception as e:
            messagebox.showerror("오류", f"설정 저장 실패:\n{e}")

    # ── UI 구성 ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.root.configure(bg="#ECEFF1")

        hdr = tk.Frame(self.root, bg="#1565C0", height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  처방약 사용량 분석기",
                 bg="#1565C0", fg="white",
                 font=("맑은 고딕", 16, "bold")).pack(side="left", padx=16)
        tk.Label(hdr, text="AI 기반 제약사별 품목 수량 자동 집계",
                 bg="#1565C0", fg="#90CAF9",
                 font=("맑은 고딕", 10)).pack(side="left")

        body = tk.Frame(self.root, bg="#ECEFF1")
        body.pack(fill="both", expand=True, padx=12, pady=10)

        left = tk.Frame(body, bg="#ECEFF1", width=295)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        right = tk.Frame(body, bg="#ECEFF1")
        right.pack(side="left", fill="both", expand=True)

        self._build_left_panel(left)
        self._build_right_panel(right)

    def _build_left_panel(self, parent: tk.Frame) -> None:
        # API 설정
        api_box = tk.LabelFrame(parent, text="  API 설정  ", bg="#ECEFF1",
                                 font=("맑은 고딕", 9), pady=8, padx=8)
        api_box.pack(fill="x", pady=(0, 8))

        tk.Label(api_box, text="API Key:", bg="#ECEFF1",
                 font=("맑은 고딕", 9)).grid(row=0, column=0, sticky="w")
        tk.Entry(api_box, textvariable=self.api_key_var, show="*",
                 font=("맑은 고딕", 9), width=22).grid(row=0, column=1,
                                                        sticky="ew", padx=(5, 0))

        tk.Label(api_box, text="모  델:", bg="#ECEFF1",
                 font=("맑은 고딕", 9)).grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Combobox(api_box, textvariable=self.model_var, state="readonly",
                     font=("맑은 고딕", 8), width=21,
                     values=["claude-sonnet-4-6",
                             "claude-opus-4-8",
                             "claude-haiku-4-5-20251001"]
                     ).grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=(5, 0))
        api_box.columnconfigure(1, weight=1)

        self._btn(api_box, "설정 저장", self._save_settings, "#1E88E5").grid(
            row=2, column=1, sticky="e", pady=(8, 0))

        # 파일 목록
        file_box = tk.LabelFrame(parent, text="  분석 이미지  ", bg="#ECEFF1",
                                  font=("맑은 고딕", 9), pady=6, padx=8)
        file_box.pack(fill="both", expand=True, pady=(0, 8))

        btn_row = tk.Frame(file_box, bg="#ECEFF1")
        btn_row.pack(fill="x", pady=(0, 4))
        self._btn(btn_row, "+ 파일 추가",  self._add_files,       "#43A047").pack(side="left")
        self._btn(btn_row, "선택 제거",    self._remove_selected, "#757575").pack(side="left", padx=4)
        self._btn(btn_row, "전체 삭제",    self._clear_files,     "#E53935").pack(side="right")

        tk.Label(file_box, textvariable=self.file_count_var, bg="#ECEFF1",
                 fg="#546E7A", font=("맑은 고딕", 8)).pack(anchor="w")

        lb_frame = tk.Frame(file_box, bg="#ECEFF1")
        lb_frame.pack(fill="both", expand=True, pady=(4, 0))
        self.file_listbox = tk.Listbox(
            lb_frame, font=("맑은 고딕", 8), selectmode="extended",
            bg="white", relief="groove", bd=1, activestyle="dotbox"
        )
        sb = ttk.Scrollbar(lb_frame, orient="vertical", command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=sb.set)
        self.file_listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # 분석 버튼
        self.analyze_btn = tk.Button(
            parent, text="▶   분석 시작", command=self._start_analysis,
            bg="#1565C0", fg="white", font=("맑은 고딕", 13, "bold"),
            relief="flat", pady=11, cursor="hand2",
            activebackground="#0D47A1", activeforeground="white"
        )
        self.analyze_btn.pack(fill="x", pady=(0, 7))

        self.progress = ttk.Progressbar(parent, mode="determinate", length=275)
        self.progress.pack(fill="x")
        tk.Label(parent, textvariable=self.status_var, bg="#ECEFF1",
                 fg="#546E7A", font=("맑은 고딕", 8),
                 wraplength=280, justify="left").pack(anchor="w", pady=(3, 0))

    def _build_right_panel(self, parent: tk.Frame) -> None:
        bar = tk.Frame(parent, bg="#ECEFF1")
        bar.pack(fill="x", pady=(0, 6))
        tk.Label(bar, text="분석 결과", bg="#ECEFF1",
                 font=("맑은 고딕", 11, "bold")).pack(side="left")

        self.clear_btn = self._btn(bar, "결과 초기화", self._clear_results, "#757575")
        self.clear_btn.pack(side="right")
        self._btn(bar, "CSV 저장", self._export_csv, "#FB8C00").pack(side="right", padx=(0, 6))

        tree_frame = tk.Frame(parent, bg="#ECEFF1")
        tree_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("Rx.Treeview", font=("맑은 고딕", 9), rowheight=26,
                         fieldbackground="white")
        style.configure("Rx.Treeview.Heading", font=("맑은 고딕", 9, "bold"),
                         background="#E3F2FD")
        style.map("Rx.Treeview", background=[("selected", "#BBDEFB")])

        cols = ("제약사", "품목명", "통계수량", "소모수량", "합계")
        self.tree = ttk.Treeview(tree_frame, columns=cols,
                                  show="headings", style="Rx.Treeview")
        widths  = {"제약사": 145, "품목명": 240, "통계수량": 95, "소모수량": 95, "합계": 95}
        anchors = {"제약사": "w",  "품목명": "w",  "통계수량": "e", "소모수량": "e", "합계": "e"}
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=widths[c], anchor=anchors[c], minwidth=60)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree.tag_configure("subtotal", background="#BBDEFB",
                                 font=("맑은 고딕", 9, "bold"), foreground="#0D47A1")
        self.tree.tag_configure("even", background="#FAFAFA")
        self.tree.tag_configure("odd",  background="#FFFFFF")

        tk.Label(parent, textvariable=self.summary_var,
                 bg="#E8EAF6", fg="#283593",
                 font=("맑은 고딕", 9, "bold"),
                 anchor="w", padx=10, pady=5).pack(fill="x", pady=(6, 0))

    def _btn(self, parent: tk.Widget, text: str,
             cmd: Callable, color: str) -> tk.Button:
        return tk.Button(parent, text=text, command=cmd,
                         bg=color, fg="white", font=("맑은 고딕", 8),
                         relief="flat", padx=8, pady=3, cursor="hand2",
                         activebackground=color, activeforeground="white")

    # ── 파일 관리 ──────────────────────────────────────────────────────

    def _add_files(self) -> None:
        files = filedialog.askopenfilenames(
            title="이미지 파일 선택",
            filetypes=[("이미지", "*.jpg *.jpeg *.png *.bmp"), ("전체", "*.*")]
        )
        for f in files:
            if f not in self.image_files:
                self.image_files.append(f)
                self.file_listbox.insert("end", Path(f).name)
        self._update_count()

    def _remove_selected(self) -> None:
        for i in reversed(self.file_listbox.curselection()):
            self.file_listbox.delete(i)
            self.image_files.pop(i)
        self._update_count()

    def _clear_files(self) -> None:
        self.image_files.clear()
        self.file_listbox.delete(0, "end")
        self._update_count()

    def _update_count(self) -> None:
        self.file_count_var.set(f"{len(self.image_files)}개 파일 선택됨")

    # ── 분석 ───────────────────────────────────────────────────────────

    def _start_analysis(self) -> None:
        if not self.api_key_var.get().strip():
            messagebox.showerror("오류", "Anthropic API Key를 입력하고 저장해주세요.")
            return
        if not self.image_files:
            messagebox.showerror("오류", "분석할 이미지 파일을 추가해주세요.")
            return
        if self.is_analyzing:
            return

        self.is_analyzing = True
        self.analyze_btn.configure(state="disabled", text="분석 중... ⏳")
        self.clear_btn.configure(state="disabled")
        self._clear_results()

        analyzer = ClaudeImageAnalyzer(
            api_key=self.api_key_var.get().strip(),
            model=self.model_var.get(),
        )
        files = list(self.image_files)

        threading.Thread(
            target=self._run_in_thread,
            args=(files, analyzer),
            daemon=True,
        ).start()

    def _run_in_thread(self, files: list[str], analyzer: ImageAnalyzer) -> None:
        """백그라운드 스레드: run_analysis 호출 후 UI 콜백."""
        errors: list[tuple[str, str]] = []

        def on_progress(cur: int, total: int, msg: str) -> None:
            val = cur / total * 100 if total else 0
            self.root.after(0, lambda: self.status_var.set(msg))
            self.root.after(0, lambda: self.progress.configure(value=val))

        def on_error(name: str, msg: str) -> None:
            errors.append((name, msg))

        try:
            run_analysis(files, analyzer, self.store, on_progress, on_error)
            self.root.after(0, self._display_results)
            if errors:
                self.root.after(0, lambda: self._show_errors(errors))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("분석 오류", str(e)))
        finally:
            self.is_analyzing = False
            self.root.after(0, lambda: self.analyze_btn.configure(
                state="normal", text="▶   분석 시작"))
            self.root.after(0, lambda: self.clear_btn.configure(state="normal"))

    @staticmethod
    def _show_errors(errors: list[tuple[str, str]]) -> None:
        body = "\n".join(f"• {n}: {m}" for n, m in errors[:8])
        if len(errors) > 8:
            body += f"\n... 외 {len(errors) - 8}건"
        messagebox.showwarning("일부 파일 오류",
                               f"다음 파일 처리 중 오류가 발생했습니다:\n\n{body}")

    # ── 결과 표시 ──────────────────────────────────────────────────────

    def _display_results(self) -> None:
        for r in self.tree.get_children():
            self.tree.delete(r)

        for company in self.store.companies():
            for idx, drug in enumerate(self.store.drugs(company)):
                s, u = self.store.totals(company, drug)
                tag = "even" if idx % 2 == 0 else "odd"
                self.tree.insert("", "end", values=(
                    company if idx == 0 else "",
                    drug,
                    f"{s:,}" if s else "—",
                    f"{u:,}" if u else "—",
                    f"{s + u:,}",
                ), tags=(tag,))

            self.tree.insert("", "end", values=(
                "", f"  ▶  {company} 소계", "", "",
                f"{self.store.company_total(company):,}",
            ), tags=("subtotal",))
            self.tree.insert("", "end", values=("", "", "", "", ""))

        self.summary_var.set(
            f"   총 {len(self.store.companies())}개 제약사  |"
            f"  {self.store.item_count()}개 품목  |"
            f"  전체 합계: {self.store.grand_total():,}"
        )

    def _clear_results(self) -> None:
        for r in self.tree.get_children():
            self.tree.delete(r)
        self.store.clear()
        self.summary_var.set("")

    # ── CSV 내보내기 ────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        if self.store.is_empty():
            messagebox.showwarning("경고", "먼저 분석을 실행하세요.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 파일", "*.csv"), ("전체", "*.*")],
            initialfile="처방약_사용량_분석결과.csv",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["제약사", "품목명", "통계수량(제약사별통계)", "소모수량(소모현황)", "합계"])
                for company in self.store.companies():
                    for drug in self.store.drugs(company):
                        s, u = self.store.totals(company, drug)
                        w.writerow([company, drug, s or 0, u or 0, s + u])
                    w.writerow([f"{company} 소계", "", "", "",
                                self.store.company_total(company)])
                    w.writerow([])
            messagebox.showinfo("저장 완료", f"저장되었습니다:\n{path}")
        except Exception as e:
            messagebox.showerror("저장 오류", f"저장 실패:\n{e}")


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main() -> None:
    root = tk.Tk()
    RxAnalyzer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
