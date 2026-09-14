"""제너리스 주문 변환·관리 프로그램 (Phase 1 MVP)."""
import datetime as dt
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, excel_export, importer, matching, theme
from app.config import AUTO_MATCH_THRESHOLD, EXPORT_DIR, STALE_PRICE_DAYS
from app.dialogs import CandidatePickerDialog, NewItemDialog, PriceHistoryDialog

TAG_DANGER = "danger"
TAG_WARNING = "warning"
TAG_NORMAL = "normal"


def _is_stale(base_date: str | None) -> bool:
    if not base_date:
        return True
    try:
        d = dt.date.fromisoformat(base_date)
    except ValueError:
        return True
    return (dt.date.today() - d).days > STALE_PRICE_DAYS


class OrderLine:
    def __init__(self, raw_text, item, quantity=1, requirement_text="", spec_text="",
                 buy_price=0, sell_price=0, match_type="수동", remark=""):
        self.raw_text = raw_text
        self.origin_text = raw_text  # 병원이 실제로 표현한 원문(별칭 학습/이력용, 화면 표시는 raw_text 사용)
        self.item = item  # dict 또는 None
        self.quantity = quantity
        self.requirement_text = requirement_text
        self.spec_text = spec_text
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.match_type = match_type
        self.remark = remark

    def tag(self):
        if self.buy_price and self.sell_price and self.buy_price > self.sell_price:
            return TAG_DANGER
        if not self.item or (self.item and _is_stale(self.item.get("base_date"))):
            return TAG_WARNING
        return TAG_NORMAL

    def as_export_dict(self):
        return {
            "raw_text": self.raw_text,
            "quantity": self.quantity,
            "requirement_text": self.requirement_text,
            "spec_text": self.spec_text,
            "buy_price": self.buy_price,
            "sell_price": self.sell_price,
        }


class OrderTab(ttk.Frame):
    COLUMNS = ("raw", "qty", "req", "spec", "buy", "sell", "remark")
    HEADINGS = {"raw": "품목(원문)", "qty": "수량", "req": "제품명",
                "spec": "규격", "buy": "매입가", "sell": "매출가", "remark": "특이사항"}
    WIDTHS = {"raw": 110, "qty": 48, "req": 250, "spec": 90, "buy": 90, "sell": 90, "remark": 160}
    CENTERED = {"raw", "qty", "spec", "buy", "sell"}
    EDITABLE = {"raw", "qty", "buy", "sell", "remark"}
    NEW_ROW_IID = "new"

    def __init__(self, parent):
        super().__init__(parent, style="TFrame", padding=16)
        self.lines: list[OrderLine] = []
        self._pending_qty = "1"
        self._active_editor: tuple | None = None
        self._build()

    def _build(self):
        top_card = theme.card(self)
        top_card.pack(fill="x", pady=(0, 12))

        date_row = ttk.Frame(top_card, style="Card.TFrame")
        date_row.pack(fill="x")
        ttk.Label(date_row, text="주문일자", style="Card.TLabel").pack(side="left")
        self.date_var = tk.StringVar(value=dt.date.today().strftime("%y%m%d"))
        ttk.Entry(date_row, textvariable=self.date_var, width=10).pack(side="left", padx=8)
        ttk.Label(date_row, text="품목 칸에 입력 후 Enter를 누르면 매칭됩니다.",
                  style="CardSecondary.TLabel").pack(side="left", padx=(16, 0))

        # 그리드
        grid_card = theme.card(self)
        grid_card.pack(fill="both", expand=True, pady=(0, 12))

        self.tree = ttk.Treeview(grid_card, columns=self.COLUMNS, show="headings", height=16)
        for col in self.COLUMNS:
            anchor = "center" if col in self.CENTERED else "w"
            self.tree.heading(col, text=self.HEADINGS[col], anchor=anchor)
            self.tree.column(col, width=self.WIDTHS[col], minwidth=self.WIDTHS[col], anchor=anchor, stretch=False)
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure(TAG_DANGER, background=theme.DANGER_SOFT)
        self.tree.tag_configure(TAG_WARNING, background=theme.WARNING_SOFT)
        self.tree.tag_configure("normal_even", background="#FFFFFF")
        self.tree.tag_configure("normal_odd", background="#F5F7FB")
        self.tree.tag_configure("new_row", background="#FAFBFD", foreground=theme.TEXT_SECONDARY)
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Delete>", lambda e: self._delete_selected())
        theme.add_column_dividers(self.tree, self.COLUMNS, self.WIDTHS)

        hint = ttk.Label(
            grid_card, text="빈 줄의 품목 칸에 입력 후 Enter로 추가 · 셀 클릭으로 수정 · Delete로 행 삭제",
            style="CardSecondary.TLabel",
        )
        hint.pack(anchor="w", pady=(8, 0))

        # 하단 액션
        action_row = ttk.Frame(self)
        action_row.pack(fill="x")
        ttk.Button(action_row, text="저장 (마스터 DB 학습 반영)", style="Accent.TButton",
                   command=self._save_order).pack(side="left")
        ttk.Button(action_row, text="엑셀로 내보내기", style="Secondary.TButton",
                   command=self._export_excel).pack(side="left", padx=8)
        ttk.Button(action_row, text="선택 행 삭제", style="Secondary.TButton",
                   command=self._delete_selected).pack(side="left", padx=8)

        self._refresh_grid()

    # ---- 매칭 공통 로직 ----
    def _resolve_item_for_text(self, raw_text: str):
        """raw_text에 대한 매칭 품목을 결정. 완전 일치라도 항상 확인 창을 띄운다.
        취소 시 None, 아니면 (item, match_type)."""
        candidates = matching.find_candidates(raw_text)
        top_item_id = candidates[0].item["id"] if candidates else None
        top_score = candidates[0].score if candidates else 0.0

        dialog = CandidatePickerDialog(self, raw_text, candidates)
        self.wait_window(dialog)
        result = dialog.result
        if result is None:
            return None
        if result.get("action") == "new":
            new_dialog = NewItemDialog(self, default_order_name=raw_text)
            self.wait_window(new_dialog)
            if new_dialog.result is None:
                return None
            return new_dialog.result, "신규등록"

        if result["id"] == top_item_id and top_score >= AUTO_MATCH_THRESHOLD:
            match_type = "자동확인"
        else:
            match_type = "수동선택"
        return result, match_type

    def _parse_qty(self, text: str) -> float:
        try:
            return float(text)
        except (TypeError, ValueError):
            return 1

    def _create_line_from_input(self, raw_text: str, qty: float):
        resolved = self._resolve_item_for_text(raw_text)
        if resolved is None:
            return
        item, match_type = resolved
        line = OrderLine(
            raw_text=item.get("order_name", raw_text), item=item, quantity=qty,
            requirement_text=item.get("product_name", ""), spec_text=item.get("spec", ""),
            buy_price=item.get("buy_price", 0), sell_price=item.get("sell_price", 0),
            match_type=match_type,
        )
        line.origin_text = raw_text  # 병원 원문 표현(별칭 학습용) 보존
        self.lines.append(line)
        self._pending_qty = "1"
        self._refresh_grid()
        new_idx = len(self.lines) - 1
        self.tree.selection_set(str(new_idx))
        self._begin_cell_edit(str(new_idx), "qty")

    def _rematch_line(self, idx: int, new_raw_text: str):
        resolved = self._resolve_item_for_text(new_raw_text)
        if resolved is None:
            self._refresh_grid()  # 취소 시 원래 표시로 되돌림
            return
        item, match_type = resolved
        line = self.lines[idx]
        line.origin_text = new_raw_text
        line.raw_text = item.get("order_name", new_raw_text)
        line.item = item
        line.requirement_text = item.get("product_name", "")
        line.spec_text = item.get("spec", "")
        line.buy_price = item.get("buy_price", 0)
        line.sell_price = item.get("sell_price", 0)
        line.match_type = match_type
        self._refresh_grid()
        self.tree.selection_set(str(idx))
        self._begin_cell_edit(str(idx), "qty")

    # ---- 그리드 렌더링 ----
    def _refresh_grid(self):
        self.tree.delete(*self.tree.get_children())
        for idx, line in enumerate(self.lines):
            tag = line.tag()
            if tag == TAG_NORMAL:
                tag = "normal_even" if idx % 2 == 0 else "normal_odd"
            self.tree.insert("", "end", iid=str(idx), tags=(tag,), values=(
                line.raw_text, f"{line.quantity:g}", line.requirement_text, line.spec_text,
                f"{line.buy_price:,.0f}", f"{line.sell_price:,.0f}", line.remark,
            ))
        self.tree.insert("", "end", iid=self.NEW_ROW_IID, tags=("new_row",), values=(
            "", self._pending_qty, "", "", "", "", "",
        ))

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel or sel[0] == self.NEW_ROW_IID:
            return None
        return int(sel[0])

    def _delete_selected(self):
        idx = self._selected_index()
        if idx is None:
            return
        del self.lines[idx]
        self._refresh_grid()

    # ---- 셀 인라인 편집 ----
    def _on_tree_click(self, event):
        if theme.block_column_resize(self.tree, event) == "break":
            return "break"
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_iid = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_iid or not col_id:
            return
        col_index = int(col_id.replace("#", "")) - 1
        if col_index < 0 or col_index >= len(self.COLUMNS):
            return
        col_name = self.COLUMNS[col_index]

        if row_iid == self.NEW_ROW_IID:
            if col_name not in ("raw", "qty"):
                return
        elif col_name not in self.EDITABLE:
            return

        if self._active_editor is not None:
            self._active_editor[1]()  # 이전 편집을 즉시 커밋

        self.after(1, lambda: self._begin_cell_edit(row_iid, col_name))

    def _begin_cell_edit(self, row_iid: str, col_name: str):
        if not self.tree.exists(row_iid):
            return
        bbox = self.tree.bbox(row_iid, col_name)
        if not bbox:
            return
        x, y, width, height = bbox
        current_value = self.tree.set(row_iid, col_name)
        if col_name == "raw" and row_iid != self.NEW_ROW_IID:
            current_value = self.lines[int(row_iid)].origin_text

        left_aligned = col_name in ("raw", "remark")
        entry = tk.Entry(self.tree, font=theme.FONT_BASE, justify="left" if left_aligned else "center")
        entry.insert(0, current_value)
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()
        entry.select_range(0, "end")

        def commit(_event=None):
            if self._active_editor is None or self._active_editor[0] is not entry:
                return
            new_value = entry.get()
            is_return = _event is not None and getattr(_event, "keysym", None) in ("Return", "KP_Enter")
            self._active_editor = None
            entry.destroy()
            self._commit_cell_edit(row_iid, col_name, new_value)
            if is_return and row_iid != self.NEW_ROW_IID:
                if col_name == "qty":
                    self._begin_cell_edit(row_iid, "remark")
                elif col_name == "remark":
                    self._begin_cell_edit(self.NEW_ROW_IID, "raw")

        def cancel(_event=None):
            if self._active_editor is None or self._active_editor[0] is not entry:
                return
            self._active_editor = None
            entry.destroy()

        self._active_editor = (entry, commit)
        entry.bind("<Return>", commit)
        entry.bind("<KP_Enter>", commit)
        entry.bind("<Escape>", cancel)
        entry.bind("<FocusOut>", commit)

    def _commit_cell_edit(self, row_iid: str, col_name: str, new_value: str):
        new_value = new_value.strip()

        if row_iid == self.NEW_ROW_IID:
            if col_name == "qty":
                self._pending_qty = new_value or "1"
                self._refresh_grid()
            elif col_name == "raw" and new_value:
                qty = self._parse_qty(self._pending_qty)
                self._create_line_from_input(new_value, qty)
            return

        idx = int(row_iid)
        line = self.lines[idx]

        if col_name == "raw":
            if new_value and new_value != line.origin_text:
                self._rematch_line(idx, new_value)
            return
        if col_name == "qty":
            try:
                line.quantity = float(new_value)
            except ValueError:
                messagebox.showwarning("입력 오류", "수량은 숫자여야 합니다.")
        elif col_name == "buy":
            try:
                line.buy_price = float(new_value)
            except ValueError:
                messagebox.showwarning("입력 오류", "매입가는 숫자여야 합니다.")
        elif col_name == "sell":
            try:
                line.sell_price = float(new_value)
            except ValueError:
                messagebox.showwarning("입력 오류", "매출가는 숫자여야 합니다.")
        elif col_name == "remark":
            line.remark = new_value

        self._refresh_grid()
        self.tree.selection_set(row_iid)

    # ---- 저장/내보내기 ----
    def _save_order(self):
        if not self.lines:
            messagebox.showinfo("안내", "저장할 항목이 없습니다.")
            return

        danger_lines = [l for l in self.lines if l.buy_price and l.sell_price and l.buy_price > l.sell_price]
        if danger_lines:
            names = ", ".join(l.raw_text for l in danger_lines)
            if not messagebox.askyesno("역마진 경고", f"다음 항목은 매입가가 매출가보다 큽니다:\n{names}\n\n그대로 저장할까요?"):
                return

        price_updates = []
        for line in self.lines:
            if not line.item:
                continue
            if line.buy_price != line.item.get("buy_price") or line.sell_price != line.item.get("sell_price"):
                price_updates.append(line)

        if price_updates:
            preview = "\n".join(
                f'- {l.item["order_name"]}: '
                f'{l.item.get("buy_price", 0):,.0f}/{l.item.get("sell_price", 0):,.0f} '
                f'→ {l.buy_price:,.0f}/{l.sell_price:,.0f}'
                for l in price_updates
            )
            if not messagebox.askyesno("마스터 가격 업데이트", f"다음 품목의 마스터 단가를 갱신합니다:\n{preview}\n\n계속할까요?"):
                return

        order_id = db.create_order(self.date_var.get().strip())
        for line in self.lines:
            item_id = None
            if line.item:
                item_id = line.item["id"]
                # 별칭 학습: 병원 원문 표현이 새로운 것이면 별칭으로 추가
                db.add_alias(item_id, line.origin_text)
                if line in price_updates:
                    db.update_item_prices(
                        item_id, line.buy_price, line.sell_price,
                        memo=f"주문 화면에서 수정({self.date_var.get()})",
                    )
            db.add_order_line(
                order_id, line.origin_text, item_id, line.quantity,
                line.requirement_text, line.spec_text, line.buy_price, line.sell_price,
                line.match_type, line.remark,
            )
        messagebox.showinfo("저장 완료", "마스터 DB에 학습 반영이 완료되었습니다.")

    def _export_excel(self):
        if not self.lines:
            messagebox.showinfo("안내", "내보낼 항목이 없습니다.")
            return
        default_name = f"{self.date_var.get().strip()} 제너리스 주문.xlsx"
        path = filedialog.asksaveasfilename(
            initialdir=str(EXPORT_DIR), initialfile=default_name,
            defaultextension=".xlsx", filetypes=[("Excel 파일", "*.xlsx")],
        )
        if not path:
            return
        excel_export.export_order(
            self.date_var.get().strip(),
            [l.as_export_dict() for l in self.lines],
            Path(path),
        )
        messagebox.showinfo("내보내기 완료", f"저장되었습니다:\n{path}")


class MasterTab(ttk.Frame):
    COLUMNS = ("category", "order_name", "manufacturer", "spec", "buy", "sell", "base_date")
    HEADINGS = {"category": "항목", "order_name": "제너리스주문명", "manufacturer": "제조사",
                "spec": "규격", "buy": "매입가", "sell": "매출가", "base_date": "기준일자"}
    WIDTHS = {"category": 100, "order_name": 150, "manufacturer": 110,
              "spec": 110, "buy": 90, "sell": 90, "base_date": 90}
    CENTERED = {"category", "spec", "buy", "sell", "base_date"}

    def __init__(self, parent):
        super().__init__(parent, style="TFrame", padding=16)
        self._build()
        self._load(db.all_items())

    def _build(self):
        search_card = theme.card(self)
        search_card.pack(fill="x", pady=(0, 12))
        ttk.Label(search_card, text="검색", style="Card.TLabel").pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(search_card, textvariable=self.search_var, width=30)
        entry.pack(side="left", padx=8)
        entry.bind("<Return>", lambda e: self._search())
        entry.bind("<Escape>", lambda e: self._clear_search())
        ttk.Button(search_card, text="검색", style="Accent.TButton",
                   command=self._search).pack(side="left")
        ttk.Button(search_card, text="전체보기", style="Secondary.TButton",
                   command=lambda: self._load(db.all_items())).pack(side="left", padx=8)

        grid_card = theme.card(self)
        grid_card.pack(fill="both", expand=True, pady=(0, 12))
        self.tree = ttk.Treeview(grid_card, columns=self.COLUMNS, show="headings", height=14)
        for col in self.COLUMNS:
            anchor = "center" if col in self.CENTERED else "w"
            self.tree.heading(col, text=self.HEADINGS[col], anchor=anchor)
            self.tree.column(col, width=self.WIDTHS[col], minwidth=self.WIDTHS[col], anchor=anchor, stretch=False)
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("normal_even", background="#FFFFFF")
        self.tree.tag_configure("normal_odd", background="#F5F7FB")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Button-1>", lambda e: theme.block_column_resize(self.tree, e))
        theme.add_column_dividers(self.tree, self.COLUMNS, self.WIDTHS)

        detail_card = theme.card(self)
        detail_card.pack(fill="x")
        self.detail_label = ttk.Label(detail_card, text="품목을 선택하세요.", style="Card.TLabel",
                                       font=theme.FONT_BOLD)
        self.detail_label.grid(row=0, column=0, columnspan=6, sticky="w")

        self.alias_var = tk.StringVar()
        ttk.Label(detail_card, text="별칭 추가", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(detail_card, textvariable=self.alias_var, width=20).grid(row=2, column=0, sticky="w")
        ttk.Button(detail_card, text="추가", style="Secondary.TButton",
                   command=self._add_alias).grid(row=2, column=1, sticky="w", padx=4)

        self.buy_var = tk.StringVar()
        self.sell_var = tk.StringVar()
        ttk.Label(detail_card, text="매입가", style="Card.TLabel").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(8, 0))
        ttk.Entry(detail_card, textvariable=self.buy_var, width=10).grid(row=2, column=2, sticky="w", padx=(16, 0))
        ttk.Label(detail_card, text="매출가", style="Card.TLabel").grid(row=1, column=3, sticky="w", pady=(8, 0))
        ttk.Entry(detail_card, textvariable=self.sell_var, width=10).grid(row=2, column=3, sticky="w")
        ttk.Button(detail_card, text="가격 수정", style="Accent.TButton",
                   command=self._update_price).grid(row=2, column=4, sticky="w", padx=8)
        ttk.Button(detail_card, text="가격 이력", style="Secondary.TButton",
                   command=self._show_history).grid(row=2, column=5, sticky="w", padx=4)

        self.alias_list_label = ttk.Label(detail_card, text="", style="CardSecondary.TLabel", wraplength=700)
        self.alias_list_label.grid(row=3, column=0, columnspan=6, sticky="w", pady=(8, 0))

        self._selected_item = None

    def _load(self, items):
        self.tree.delete(*self.tree.get_children())
        for idx, item in enumerate(items):
            tag = "normal_even" if idx % 2 == 0 else "normal_odd"
            self.tree.insert("", "end", iid=str(item["id"]), tags=(tag,), values=(
                item["category"], item["order_name"], item["manufacturer"], item["spec"],
                f'{item["buy_price"]:,.0f}', f'{item["sell_price"]:,.0f}', item["base_date"] or "",
            ))

    def _search(self):
        keyword = self.search_var.get().strip()
        self._load(db.search_items(keyword) if keyword else db.all_items())

    def _clear_search(self):
        self.search_var.set("")
        self._load(db.all_items())

    def _on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        item = db.get_item(int(sel[0]))
        self._selected_item = item
        self.detail_label.configure(
            text=f'{item["order_name"]}  |  {item["manufacturer"]}  |  {item["product_name"]}'
        )
        self.buy_var.set(str(item["buy_price"]))
        self.sell_var.set(str(item["sell_price"]))
        aliases = db.get_aliases(item["id"])
        self.alias_list_label.configure(text="별칭: " + (", ".join(aliases) if aliases else "(없음)"))

    def _add_alias(self):
        if not self._selected_item:
            return
        alias = self.alias_var.get().strip()
        if not alias:
            return
        db.add_alias(self._selected_item["id"], alias)
        self.alias_var.set("")
        self._on_select(None)

    def _update_price(self):
        if not self._selected_item:
            return
        try:
            buy = float(self.buy_var.get())
            sell = float(self.sell_var.get())
        except ValueError:
            messagebox.showwarning("입력 오류", "매입가/매출가는 숫자여야 합니다.")
            return
        if buy > sell:
            if not messagebox.askyesno("역마진 경고", "매입가가 매출가보다 큽니다. 그대로 수정할까요?"):
                return
        db.update_item_prices(self._selected_item["id"], buy, sell, memo="품목 마스터 관리 화면에서 수정")
        self._search()
        messagebox.showinfo("완료", "가격이 수정되었습니다.")

    def _show_history(self):
        if not self._selected_item:
            return
        PriceHistoryDialog(self, self._selected_item)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("제너리스 주문 변환·관리")
        self.geometry("1180x780")
        theme.apply(self)

        db.init_db()
        if db.is_empty():
            try:
                n = importer.import_master()
                messagebox.showinfo("초기 설정", f"마스터 엑셀에서 {n}개 품목을 불러왔습니다.")
            except FileNotFoundError:
                messagebox.showwarning(
                    "안내",
                    "마스터 엑셀 파일을 찾지 못해 빈 DB로 시작합니다.\n"
                    "품목 마스터 관리 화면에서 직접 등록해주세요.",
                )

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        notebook.add(OrderTab(notebook), text="새 주문 처리")
        notebook.add(MasterTab(notebook), text="품목 마스터 관리")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
