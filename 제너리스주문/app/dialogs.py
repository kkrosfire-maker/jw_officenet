"""보조 팝업 다이얼로그들: 후보 선택, 신규 품목 등록, 가격 이력."""
import tkinter as tk
from tkinter import messagebox, ttk

from app import db, matching, theme


class CandidatePickerDialog(tk.Toplevel):
    """유사 품목 후보 목록에서 하나를 선택하거나, 검색/신규등록으로 전환."""

    def __init__(self, parent, query_text: str):
        super().__init__(parent)
        self.title("품목 매칭 선택")
        self.configure(bg=theme.APP_BG)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.bind("<Escape>", lambda e: self._cancel())

        self.result = None  # dict(item) 또는 {"action": "new"} 또는 None(취소)

        header = ttk.Label(self, text=f'"{query_text}" 와(과) 유사한 품목', style="Heading.TLabel")
        header.pack(anchor="w", padx=16, pady=(16, 4))

        search_row = ttk.Frame(self)
        search_row.pack(fill="x", padx=16, pady=(0, 8))
        ttk.Label(search_row, text="직접 검색:").pack(side="left")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=40)
        search_entry.pack(side="left", padx=8)
        search_entry.bind("<Return>", lambda e: self._do_search())
        ttk.Button(search_row, text="검색", style="Secondary.TButton",
                   command=self._do_search).pack(side="left")

        columns = ("score", "category", "order_name", "manufacturer", "spec", "buy", "sell")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=10)
        headings = {"score": "유사도", "category": "항목", "order_name": "제너리스주문명",
                    "manufacturer": "제조사", "spec": "규격", "buy": "매입가", "sell": "매출가"}
        widths = {"score": 60, "category": 90, "order_name": 150, "manufacturer": 110,
                  "spec": 120, "buy": 80, "sell": 80}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.tree.bind("<Double-1>", lambda e: self._confirm())
        self.tree.bind("<Return>", lambda e: self._confirm())

        self._rows: dict[str, dict] = {}
        self._populate_candidates(query_text)
        self.tree.focus_set()

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=16, pady=(0, 16))
        ttk.Button(btn_row, text="신규 품목으로 등록", style="Secondary.TButton",
                   command=self._new_item).pack(side="left")
        ttk.Button(btn_row, text="취소", style="Secondary.TButton",
                   command=self._cancel).pack(side="right")
        ttk.Button(btn_row, text="선택", style="Accent.TButton",
                   command=self._confirm).pack(side="right", padx=8)

        theme.autosize(self, min_w=780, min_h=380)

    def _populate_candidates(self, query_text):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._rows.clear()
        candidates = matching.find_candidates(query_text)
        for c in candidates:
            iid = str(c.item["id"])
            self.tree.insert("", "end", iid=iid, values=(
                f'{c.score*100:.0f}%', c.item["category"], c.item["order_name"],
                c.item["manufacturer"], c.item["spec"],
                f'{c.item["buy_price"]:,.0f}', f'{c.item["sell_price"]:,.0f}',
            ))
            self._rows[iid] = c.item
        if candidates:
            top_iid = str(candidates[0].item["id"])
            self.tree.selection_set(top_iid)
            self.tree.focus(top_iid)

    def _do_search(self):
        keyword = self.search_var.get().strip()
        if not keyword:
            return
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._rows.clear()
        for item in db.search_items(keyword):
            iid = str(item["id"])
            self.tree.insert("", "end", iid=iid, values=(
                "-", item["category"], item["order_name"], item["manufacturer"],
                item["spec"], f'{item["buy_price"]:,.0f}', f'{item["sell_price"]:,.0f}',
            ))
            self._rows[iid] = item

    def _confirm(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("안내", "품목을 선택해주세요.", parent=self)
            return
        self.result = self._rows[sel[0]]
        self.destroy()

    def _new_item(self):
        self.result = {"action": "new"}
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class NewItemDialog(tk.Toplevel):
    """마스터 DB에 없는 신규 품목 등록 폼."""

    def __init__(self, parent, default_order_name: str = ""):
        super().__init__(parent)
        self.title("신규 품목 등록")
        self.configure(bg=theme.APP_BG)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.bind("<Escape>", lambda e: self._cancel())

        self.result = None
        self.vars = {
            "order_name": tk.StringVar(value=default_order_name),
            "category": tk.StringVar(),
            "manufacturer": tk.StringVar(),
            "product_name": tk.StringVar(),
            "spec": tk.StringVar(),
            "buy_price": tk.StringVar(value="0"),
            "sell_price": tk.StringVar(value="0"),
        }
        labels = {
            "order_name": "제너리스주문명(병원 표현)*",
            "category": "항목(대분류)",
            "manufacturer": "제조사",
            "product_name": "제품명(표준)",
            "spec": "규격",
            "buy_price": "매입가",
            "sell_price": "매출가",
        }

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        for key, label in labels.items():
            row = ttk.Frame(body)
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, width=20).pack(side="left")
            ttk.Entry(row, textvariable=self.vars[key]).pack(side="left", fill="x", expand=True)

        btn_row = ttk.Frame(body)
        btn_row.pack(fill="x", pady=(16, 0))
        ttk.Button(btn_row, text="취소", style="Secondary.TButton",
                   command=self._cancel).pack(side="right")
        ttk.Button(btn_row, text="등록", style="Accent.TButton",
                   command=self._submit).pack(side="right", padx=8)

        theme.autosize(self, min_w=420, min_h=380)

    def _submit(self):
        order_name = self.vars["order_name"].get().strip()
        if not order_name:
            messagebox.showwarning("입력 필요", "제너리스주문명은 필수입니다.", parent=self)
            return
        try:
            buy = float(self.vars["buy_price"].get() or 0)
            sell = float(self.vars["sell_price"].get() or 0)
        except ValueError:
            messagebox.showwarning("입력 오류", "매입가/매출가는 숫자여야 합니다.", parent=self)
            return
        if buy > sell:
            if not messagebox.askyesno("역마진 경고", "매입가가 매출가보다 큽니다. 그대로 등록할까요?", parent=self):
                return
        item_id = db.insert_new_item_from_order(
            order_name=order_name,
            manufacturer=self.vars["manufacturer"].get().strip(),
            product_name=self.vars["product_name"].get().strip(),
            spec=self.vars["spec"].get().strip(),
            buy_price=buy, sell_price=sell,
            category=self.vars["category"].get().strip(),
        )
        self.result = db.get_item(item_id)
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class PriceHistoryDialog(tk.Toplevel):
    def __init__(self, parent, item: dict):
        super().__init__(parent)
        self.title(f'가격 변경 이력 - {item["order_name"]}')
        self.configure(bg=theme.APP_BG)
        self.resizable(True, True)
        self.transient(parent)
        self.bind("<Escape>", lambda e: self.destroy())

        columns = ("changed_at", "old_buy", "new_buy", "old_sell", "new_sell", "memo")
        headings = {"changed_at": "변경일시", "old_buy": "이전 매입가", "new_buy": "이후 매입가",
                    "old_sell": "이전 매출가", "new_sell": "이후 매출가", "memo": "메모"}
        tree = ttk.Treeview(self, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=headings[col])
            tree.column(col, width=90 if col != "memo" else 160)
        tree.pack(fill="both", expand=True, padx=16, pady=16)

        history = db.get_price_history(item["id"])
        if not history:
            ttk.Label(self, text="변경 이력이 없습니다.", style="Secondary.TLabel").pack(pady=8)
        for h in history:
            tree.insert("", "end", values=(
                h["changed_at"], h["old_buy"], h["new_buy"], h["old_sell"], h["new_sell"], h["memo"] or "",
            ))

        theme.autosize(self, min_w=560, min_h=280)
