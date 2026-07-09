import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import os
import threading
import matching_engine


class FuzzyMatchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("유사 이름 매칭 도구")
        self.root.geometry("760x680")
        self.root.resizable(True, True)
        self.df = None
        self.result_df = None
        self._cancel_event = threading.Event()
        self._setup_ui()

    def _setup_ui(self):
        main = tk.Frame(self.root, padx=15, pady=10)
        main.pack(fill="both", expand=True)

        # ── 1. 파일 선택 ──────────────────────────────────────
        f1 = tk.LabelFrame(main, text=" 1. 파일 선택 ", font=("맑은 고딕", 10, "bold"), padx=10, pady=8)
        f1.pack(fill="x", pady=5)

        self.file_label = tk.Label(f1, text="파일을 선택해주세요", fg="#888", anchor="w")
        self.file_label.pack(side="left", expand=True, fill="x")
        tk.Button(f1, text="  파일 열기  ", command=self._load_file,
                  bg="#5C6BC0", fg="white", relief="flat", padx=6).pack(side="right")

        # ── 2. 열 선택 ──────────────────────────────────────
        f2 = tk.LabelFrame(main, text=" 2. 비교할 열 선택 ", font=("맑은 고딕", 10, "bold"), padx=10, pady=8)
        f2.pack(fill="x", pady=5)

        tk.Label(f2, text="A 목록 (기준 열):").grid(row=0, column=0, sticky="w", padx=5)
        self.col_a = ttk.Combobox(f2, width=22, state="disabled")
        self.col_a.grid(row=0, column=1, padx=5)

        tk.Label(f2, text="B 목록 (비교 열):").grid(row=0, column=2, sticky="w", padx=15)
        self.col_b = ttk.Combobox(f2, width=22, state="disabled")
        self.col_b.grid(row=0, column=3, padx=5)

        # ── 3. 설정 ──────────────────────────────────────
        f3 = tk.LabelFrame(main, text=" 3. 설정 ", font=("맑은 고딕", 10, "bold"), padx=10, pady=8)
        f3.pack(fill="x", pady=5)

        row1 = tk.Frame(f3)
        row1.pack(fill="x")
        tk.Label(row1, text="최소 유사도 (이 값 미만은 결과에서 제외):").pack(side="left")
        self.threshold_var = tk.IntVar(value=80)
        self.threshold_label = tk.Label(row1, text="80 %", width=5, font=("맑은 고딕", 10, "bold"), fg="#333")
        self.threshold_label.pack(side="right", padx=5)
        tk.Scale(row1, from_=0, to=100, orient="horizontal", length=180,
                 variable=self.threshold_var, showvalue=False,
                 command=lambda v: self.threshold_label.config(text=f"{int(float(v))} %")).pack(side="right")


        # ── 버튼 행 ──────────────────────────────────────
        btn_row = tk.Frame(main)
        btn_row.pack(fill="x", pady=8)

        self.run_btn = tk.Button(btn_row, text="▶  매칭 시작", bg="#43A047", fg="white",
                                  font=("맑은 고딕", 12, "bold"), relief="flat",
                                  command=self._run_matching, state="disabled", pady=6)
        self.run_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.cancel_btn = tk.Button(btn_row, text="⏹  취소", bg="#E53935", fg="white",
                                     font=("맑은 고딕", 12, "bold"), relief="flat",
                                     command=self._cancel_matching, pady=6)
        # 계산 중에만 표시

        self.reset_btn = tk.Button(btn_row, text="🔄  초기화", bg="#757575", fg="white",
                                    font=("맑은 고딕", 11, "bold"), relief="flat",
                                    command=self._reset, pady=6)
        self.reset_btn.pack(side="right", padx=(4, 0))

        # ── 진행 바 ──────────────────────────────────────
        self.progress_frame = tk.Frame(main)
        # 계산 중에만 표시

        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(self.progress_frame, variable=self.progress_var,
                        maximum=100, length=600).pack(side="left", expand=True, fill="x")
        self.progress_label = tk.Label(self.progress_frame, text="0%", width=5, anchor="e")
        self.progress_label.pack(side="right")

        # ── 4. 결과 미리보기 ──────────────────────────────────────
        f4 = tk.LabelFrame(main, text=" 4. 결과 미리보기 ", font=("맑은 고딕", 10, "bold"), padx=5, pady=8)
        f4.pack(fill="both", expand=True, pady=5)

        # 상태 텍스트 + 색상 범례
        info_row = tk.Frame(f4)
        info_row.pack(anchor="w", padx=5, pady=(0, 4), fill="x")

        self.status_label = tk.Label(info_row, text="", fg="#555", font=("맑은 고딕", 9))
        self.status_label.pack(side="left")

        # 색상 범례 (colored box + 설명 텍스트)
        legend_data = [
            ("#A5D6A7", "90% 이상"),
            ("#FFF176", "80% 이상"),
            ("#EF9A9A", "80% 미만"),
        ]
        for color, label_text in legend_data:
            tk.Label(info_row, bg=color, width=2, relief="solid", bd=1).pack(side="right", padx=(0, 2))
            tk.Label(info_row, text=label_text, fg="#444", font=("맑은 고딕", 9)).pack(side="right", padx=(6, 0))

        tree_frame = tk.Frame(f4)
        tree_frame.pack(fill="both", expand=True)

        cols = ("a_col", "b_col", "score")
        self._sort_state = {c: False for c in cols}  # False=오름차순
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=9)
        self.tree.heading("a_col", text="A 목록 (기준) ↕", command=lambda: self._sort_column("a_col"))
        self.tree.heading("b_col", text="B 목록 (매칭 결과) ↕", command=lambda: self._sort_column("b_col"))
        self.tree.heading("score", text="유사도 (%) ↕", command=lambda: self._sort_column("score"))
        self.tree.column("a_col", width=280)
        self.tree.column("b_col", width=280)
        self.tree.column("score", width=100, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("high", background="#A5D6A7")  # 90%+ 연녹색
        self.tree.tag_configure("mid",  background="#FFF176")  # 80%+ 연노란색
        self.tree.tag_configure("low",  background="#EF9A9A")  # 80%↓ 연붉은색

        # ── 저장 버튼 ──────────────────────────────────────
        self.save_btn = tk.Button(main, text="💾  결과를 엑셀로 저장", bg="#1E88E5", fg="white",
                                   font=("맑은 고딕", 11, "bold"), relief="flat",
                                   command=self._save_result, state="disabled", pady=5)
        self.save_btn.pack(fill="x", pady=5)

    # ─────────────────────────────────────────────────────────
    def _load_file(self):
        path = filedialog.askopenfilename(
            title="파일 선택",
            filetypes=[("Excel 파일", "*.xlsx *.xls"),
                       ("CSV / 텍스트", "*.csv *.txt"),
                       ("모든 파일", "*.*")]
        )
        if not path:
            return
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".xlsx", ".xls"):
                self.df = pd.read_excel(path, dtype=str)
            else:
                self.df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")

            cols = list(self.df.columns)
            for combo in (self.col_a, self.col_b):
                combo["values"] = cols
                combo["state"] = "readonly"
            if len(cols) >= 2:
                self.col_a.current(0)
                self.col_b.current(1)

            self.file_label.config(text=f"✔  {os.path.basename(path)}", fg="#333")
            self.run_btn["state"] = "normal"
            messagebox.showinfo("파일 불러오기 완료", f"파일을 불러왔습니다.\n총 {len(self.df)}행")
        except Exception as e:
            messagebox.showerror("오류", f"파일을 읽는 중 문제가 생겼어요:\n{e}")

    # ─────────────────────────────────────────────────────────
    def _run_matching(self):
        col_a, col_b = self.col_a.get(), self.col_b.get()
        if not col_a or not col_b:
            messagebox.showwarning("열 선택 필요", "A, B 열을 모두 선택해주세요.")
            return
        if col_a == col_b:
            messagebox.showwarning("열 선택 오류", "서로 다른 열을 선택해주세요.")
            return

        self._cancel_event.clear()
        self._set_computing(True)
        self.status_label.config(text="계산 중입니다. 잠시 기다려주세요...")
        self.progress_var.set(0)

        threading.Thread(target=self._do_matching, args=(col_a, col_b), daemon=True).start()

    def _do_matching(self, col_a, col_b):
        try:
            def dedup(lst: list[str]) -> list[str]:
                seen: set[str] = set()
                return [x for x in lst if not (x in seen or seen.add(x))]

            raw_a = self.df[col_a].dropna().astype(str).tolist()
            raw_b = self.df[col_b].dropna().astype(str).tolist()
            list_a = dedup(raw_a)
            list_b = dedup(raw_b)

            dedup_msg = (f"중복 제거 — A열: {len(raw_a)}→{len(list_a)}개 / "
                         f"B열: {len(raw_b)}→{len(list_b)}개")
            self.root.after(0, self.status_label.config, {"text": dedup_msg})

            results = matching_engine.match(
                list_a, list_b,
                threshold=self.threshold_var.get(),
                cancel_event=self._cancel_event,
                progress_cb=lambda pct: self.root.after(0, self._update_progress, pct),
            )

            if self._cancel_event.is_set():
                self.root.after(0, self._on_cancelled)
                return

            rows = [{col_a: r["a"], col_b: r["b"], "유사도 (%)": r["score"]}
                    for r in results]
            self.root.after(0, self._update_ui, rows, col_a, col_b, list_a)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("오류", f"매칭 중 문제가 생겼어요:\n{e}"))
            self.root.after(0, lambda: self._set_computing(False))

    def _update_progress(self, pct):
        self.progress_var.set(pct)
        self.progress_label.config(text=f"{int(pct)}%")

    def _update_ui(self, rows, col_a, col_b, list_a):
        self.result_df = pd.DataFrame(rows)

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree.heading("a_col", text=col_a)
        self.tree.heading("b_col", text=col_b)

        for _, row in self.result_df.iterrows():
            s = row["유사도 (%)"]
            tag = "high" if s >= 90 else "mid" if s >= 80 else "low"
            self.tree.insert("", "end",
                             values=(row[col_a], row[col_b], f"{s}%"),
                             tags=(tag,))

        total = len(list_a)
        matched = len(rows)
        self.status_label.config(text=f"총 {total}개 항목 중 {matched}개 매칭됨")
        self._set_computing(False)
        self.save_btn["state"] = "normal"

    def _on_cancelled(self):
        self.status_label.config(text="취소되었습니다.")
        self._set_computing(False)

    # ─────────────────────────────────────────────────────────
    def _cancel_matching(self):
        self._cancel_event.set()
        self.cancel_btn.config(state="disabled", text="취소 중...")

    def _reset(self):
        self._cancel_event.set()
        self.df = None
        self.result_df = None

        self.file_label.config(text="파일을 선택해주세요", fg="#888")
        for combo in (self.col_a, self.col_b):
            combo.set("")
            combo["state"] = "disabled"
        self.threshold_var.set(80)

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree.heading("a_col", text="A 목록 (기준)")
        self.tree.heading("b_col", text="B 목록 (매칭 결과)")

        self.status_label.config(text="")
        self.progress_var.set(0)
        self._set_computing(False)
        self.run_btn["state"] = "disabled"
        self.save_btn["state"] = "disabled"

    # ─────────────────────────────────────────────────────────
    def _set_computing(self, computing: bool):
        if computing:
            self.run_btn.pack_forget()
            self.cancel_btn.config(state="normal", text="⏹  취소")
            self.cancel_btn.pack(side="left", expand=True, fill="x", padx=(0, 4),
                                  in_=self.run_btn.master)
            self.progress_frame.pack(fill="x", pady=(0, 4))
        else:
            self.cancel_btn.pack_forget()
            self.run_btn.pack(side="left", expand=True, fill="x", padx=(0, 4),
                               in_=self.cancel_btn.master)
            self.progress_frame.pack_forget()

    # ─────────────────────────────────────────────────────────
    def _sort_column(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        reverse = self._sort_state[col]

        # 유사도 열은 숫자로 정렬
        if col == "score":
            items.sort(key=lambda x: float(x[0].rstrip("%")), reverse=reverse)
        else:
            items.sort(key=lambda x: x[0], reverse=reverse)

        for idx, (_, k) in enumerate(items):
            self.tree.move(k, "", idx)

        self._sort_state[col] = not reverse

        arrow = " ↓" if reverse else " ↑"
        labels = {"a_col": "A 목록 (기준)", "b_col": "B 목록 (매칭 결과)", "score": "유사도 (%)"}
        for c, base in labels.items():
            suffix = arrow if c == col else " ↕"
            self.tree.heading(c, text=base + suffix)

    # ─────────────────────────────────────────────────────────
    def _save_result(self):
        if self.result_df is None or self.result_df.empty:
            messagebox.showwarning("저장 불가", "저장할 결과가 없습니다.")
            return
        path = filedialog.asksaveasfilename(
            title="저장 위치 선택",
            defaultextension=".xlsx",
            filetypes=[("Excel 파일", "*.xlsx")],
            initialfile="매칭_결과.xlsx"
        )
        if path:
            self.result_df.to_excel(path, index=False)
            messagebox.showinfo("저장 완료", f"저장되었습니다:\n{path}")


if __name__ == "__main__":
    root = tk.Tk()
    FuzzyMatchApp(root)
    root.mainloop()
