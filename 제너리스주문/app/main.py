"""제너리스 주문 변환·관리 프로그램 (Phase 1 MVP)."""
import datetime as dt
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, excel_export, grid_edit, importer, matching, theme
from app.config import EXPORT_DIR, SOURCE_MASTER_SHEET
from app.dialogs import (CandidatePickerDialog, MasterReplaceDialog, NewItemDialog,
                         PriceHistoryDialog)
from app.order import TAG_DANGER, TAG_NORMAL, TAG_WARNING, OrderEditSession, find_danger_lines, find_price_updates


try:  # 탐색기에서 파일을 끌어다 놓는 기능(없어도 나머지 기능은 그대로 동작)
    from tkinterdnd2 import DND_FILES, TkinterDnD

    BaseTk = TkinterDnD.Tk
except ImportError:  # pragma: no cover - 배포 환경에 따라 없을 수 있다
    DND_FILES = None
    BaseTk = tk.Tk


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
        self.session = OrderEditSession()
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
        dividers = theme.setup_grid_columns(self.tree, self.COLUMNS, self.HEADINGS, self.WIDTHS,
                                            self.CENTERED, on_sort=self._sort_by)
        theme.track_column_resize(self.tree, self.COLUMNS, dividers)
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure(TAG_DANGER, background=theme.DANGER_SOFT)
        self.tree.tag_configure(TAG_WARNING, background=theme.WARNING_SOFT)
        self.tree.tag_configure("normal_even", background="#FFFFFF")
        self.tree.tag_configure("normal_odd", background="#F5F7FB")
        self.tree.tag_configure("new_row", background="#FAFBFD", foreground=theme.TEXT_SECONDARY)
        self.editor = grid_edit.InlineCellEditor(
            self.tree, self.COLUMNS, on_commit=self._commit_cell_edit,
            is_editable=self._is_editable, left_aligned={"raw", "remark"},
            initial_value=self._editor_value,
        )
        self.tree.bind("<Button-1>", self.editor.handle_click)
        self.tree.bind("<Delete>", lambda e: self._delete_selected())

        hint = ttk.Label(
            grid_card,
            text="빈 줄의 품목 칸에 입력 후 Enter로 추가 · 셀 클릭으로 수정 · Delete로 행 삭제 · "
                 "헤더 경계선 드래그로 칸 너비 조절",
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
        ttk.Button(action_row, text="새로 작성하기", style="Secondary.TButton",
                   command=self._reset_order).pack(side="left", padx=8)

        self._refresh_grid()

    # ---- 매칭 공통 로직 ----
    def _resolve_item_for_text(self, raw_text: str):
        """raw_text에 대한 매칭 품목을 결정. 완전 일치라도 항상 확인 창을 띄운다.
        취소 시 None, 아니면 (item, match_type)."""
        candidates = matching.find_candidates(raw_text)

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

        match_type = matching.classify_match_type(candidates, result["id"])
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
        self.session.add_line(raw_text, qty, item, match_type)
        self.session.pending_qty = "1"
        self._refresh_grid()
        new_idx = len(self.session.lines) - 1
        self.tree.selection_set(str(new_idx))
        self.editor.begin(str(new_idx), "qty")

    def _rematch_line(self, idx: int, new_raw_text: str):
        resolved = self._resolve_item_for_text(new_raw_text)
        if resolved is None:
            self._refresh_grid()  # 취소 시 원래 표시로 되돌림
            return
        item, match_type = resolved
        self.session.rematch_line(idx, new_raw_text, item, match_type)
        self._refresh_grid()
        self.tree.selection_set(str(idx))
        self.editor.begin(str(idx), "qty")

    # ---- 그리드 렌더링 ----
    def _refresh_grid(self):
        self.tree.delete(*self.tree.get_children())
        for idx, line in enumerate(self.session.lines):
            tag = line.tag()
            if tag == TAG_NORMAL:
                tag = "normal_even" if idx % 2 == 0 else "normal_odd"
            self.tree.insert("", "end", iid=str(idx), tags=(tag,), values=(
                line.raw_text, f"{line.quantity:g}", line.requirement_text, line.spec_text,
                f"{line.buy_price:,.0f}", f"{line.sell_price:,.0f}", line.remark,
            ))
        self.tree.insert("", "end", iid=self.NEW_ROW_IID, tags=("new_row",), values=(
            "", self.session.pending_qty, "", "", "", "", "",
        ))

    def _sort_by(self, col: str):
        self.session.sort(col)
        theme.update_sort_headings(self.tree, self.COLUMNS, self.HEADINGS,
                                    self.session.sort_col, self.session.sort_reverse)
        self._refresh_grid()

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel or sel[0] == self.NEW_ROW_IID:
            return None
        return int(sel[0])

    def _delete_selected(self):
        idx = self._selected_index()
        if idx is None:
            return
        self.session.delete_line(idx)
        self._refresh_grid()

    def _reset_order(self):
        """입력한 내용을 모두 비우고 새 주문 작성 상태로 되돌린다."""
        if self.session.lines and not messagebox.askyesno(
            "새로 작성하기", "입력한 내용을 모두 지우고 새로 작성할까요?"
        ):
            return
        self.editor.cancel_active()
        self.session = OrderEditSession()
        theme.update_sort_headings(self.tree, self.COLUMNS, self.HEADINGS, None, False)
        self.date_var.set(dt.date.today().strftime("%y%m%d"))
        self._refresh_grid()
        self.tree.selection_remove(*self.tree.selection())

    # ---- 셀 인라인 편집 ----
    def _is_editable(self, row_iid: str, col_name: str) -> bool:
        if row_iid == self.NEW_ROW_IID:
            return col_name in ("raw", "qty")
        return col_name in self.EDITABLE

    def _editor_value(self, row_iid: str, col_name: str) -> str:
        """빈 줄이 아닌 raw 칸은 화면에 보이는 정식 품목명 대신 병원 원문을 편집한다."""
        if col_name == "raw" and row_iid != self.NEW_ROW_IID:
            return self.session.lines[int(row_iid)].origin_text
        return self.tree.set(row_iid, col_name)

    def _commit_cell_edit(self, row_iid: str, col_name: str, new_value: str):
        new_value = new_value.strip()

        if row_iid == self.NEW_ROW_IID:
            if col_name == "qty":
                self.session.pending_qty = new_value or "1"
                self._refresh_grid()
            elif col_name == "raw" and new_value:
                qty = self._parse_qty(self.session.pending_qty)
                self._create_line_from_input(new_value, qty)
            return None

        idx = int(row_iid)
        line = self.session.lines[idx]

        if col_name == "raw":
            if new_value and new_value != line.origin_text:
                self._rematch_line(idx, new_value)
            return None

        error = None
        if col_name == "qty":
            error = self.session.set_quantity(idx, new_value)
        elif col_name == "buy":
            error = self.session.set_price(idx, "buy", new_value)
        elif col_name == "sell":
            error = self.session.set_price(idx, "sell", new_value)
        elif col_name == "remark":
            self.session.set_remark(idx, new_value)

        if error:
            messagebox.showwarning("입력 오류", error)

        self._refresh_grid()
        self.tree.selection_set(row_iid)
        # Enter로 넘어갈 다음 칸: 수량 → 특이사항 → 새 줄의 품목
        if col_name == "qty":
            return row_iid, "remark"
        if col_name == "remark":
            return self.NEW_ROW_IID, "raw"
        return None

    # ---- 저장/내보내기 ----
    def _save_order(self):
        if not self.session.lines:
            messagebox.showinfo("안내", "저장할 항목이 없습니다.")
            return

        danger_lines = find_danger_lines(self.session.lines)
        if danger_lines:
            names = ", ".join(l.raw_text for l in danger_lines)
            if not messagebox.askyesno("역마진 경고", f"다음 항목은 매입가가 매출가보다 큽니다:\n{names}\n\n그대로 저장할까요?"):
                return

        price_updates = find_price_updates(self.session.lines)
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
        for line in self.session.lines:
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
        if not self.session.lines:
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
            [l.as_export_dict() for l in self.session.lines],
            Path(path),
        )
        messagebox.showinfo("내보내기 완료", f"저장되었습니다:\n{path}")


class MasterTab(ttk.Frame):
    COLUMNS = ("category", "order_name", "manufacturer", "product_name", "spec", "buy", "sell", "base_date")
    HEADINGS = {"category": "항목", "order_name": "제너리스주문명", "manufacturer": "제조사",
                "product_name": "제품명", "spec": "규격", "buy": "매입가", "sell": "매출가", "base_date": "기준일자"}
    WIDTHS = {"category": 100, "order_name": 150, "manufacturer": 110,
              "product_name": 150, "spec": 110, "buy": 90, "sell": 90, "base_date": 90}
    CENTERED = {"category", "spec", "buy", "sell", "base_date"}
    # 기준일자는 가격을 고칠 때 자동으로 갱신되므로 직접 편집하지 않는다.
    EDITABLE = ("category", "order_name", "manufacturer", "product_name", "spec", "buy", "sell")
    TEXT_FIELDS = {"category": "category", "order_name": "order_name",
                   "manufacturer": "manufacturer", "product_name": "product_name", "spec": "spec"}
    SORT_KEYS = {
        "category": lambda item: item["category"] or "",
        "order_name": lambda item: item["order_name"] or "",
        "manufacturer": lambda item: item["manufacturer"] or "",
        "product_name": lambda item: item["product_name"] or "",
        "spec": lambda item: item["spec"] or "",
        "buy": lambda item: item["buy_price"],
        "sell": lambda item: item["sell_price"],
        "base_date": lambda item: item["base_date"] or "",
    }

    def __init__(self, parent):
        super().__init__(parent, style="TFrame", padding=16)
        self._items: list = []
        self._sort_col: str | None = None
        self._sort_reverse = False
        self._build()
        self._load(db.all_items())

    def _build(self):
        self._build_master_file_card()

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

        detail_card = theme.card(self)
        detail_card.pack(side="bottom", fill="x")

        grid_card = theme.card(self)
        grid_card.pack(fill="both", expand=True, pady=(0, 12))
        self.tree = ttk.Treeview(grid_card, columns=self.COLUMNS, show="headings", height=10)
        dividers = theme.setup_grid_columns(self.tree, self.COLUMNS, self.HEADINGS, self.WIDTHS,
                                             self.CENTERED, on_sort=self._sort_by)
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("normal_even", background="#FFFFFF")
        self.tree.tag_configure("normal_odd", background="#F5F7FB")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        theme.track_column_resize(self.tree, self.COLUMNS, dividers)

        self.editor = grid_edit.InlineCellEditor(
            self.tree, self.COLUMNS, on_commit=self._commit_cell_edit,
            is_editable=lambda row_iid, col: col in self.EDITABLE,
            left_aligned={"order_name", "manufacturer", "product_name"},
            initial_value=self._editor_value,
        )
        self.tree.bind("<Button-1>", self.editor.handle_click)

        ttk.Label(grid_card,
                  text="셀을 클릭하면 그 자리에서 수정됩니다 · Enter로 같은 행의 다음 칸 이동 · Esc 취소",
                  style="CardSecondary.TLabel").pack(anchor="w", pady=(8, 0))

        self.detail_label = ttk.Label(detail_card, text="품목을 선택하세요.", style="Card.TLabel",
                                       font=theme.FONT_BOLD)
        self.detail_label.grid(row=0, column=0, columnspan=4, sticky="w")

        self.alias_var = tk.StringVar()
        ttk.Label(detail_card, text="별칭 추가", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        alias_entry = ttk.Entry(detail_card, textvariable=self.alias_var, width=20)
        alias_entry.grid(row=2, column=0, sticky="w")
        alias_entry.bind("<Return>", lambda e: self._add_alias())
        ttk.Button(detail_card, text="추가", style="Secondary.TButton",
                   command=self._add_alias).grid(row=2, column=1, sticky="w", padx=4)
        ttk.Button(detail_card, text="가격 이력", style="Secondary.TButton",
                   command=self._show_history).grid(row=2, column=2, sticky="w", padx=8)

        self.alias_list_label = ttk.Label(detail_card, text="", style="CardSecondary.TLabel", wraplength=700)
        self.alias_list_label.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))

        self._selected_item = None

    # ---- 마스터 엑셀 파일 ----
    def _build_master_file_card(self):
        card = theme.card(self)
        card.pack(fill="x", pady=(0, 12))

        head = ttk.Frame(card, style="Card.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="마스터 엑셀", style="Card.TLabel", font=theme.FONT_BOLD).pack(side="left")
        ttk.Button(head, text="다른 파일로 교체", style="Accent.TButton",
                   command=self._choose_master_file).pack(side="right")
        ttk.Button(head, text="지금 다시 불러오기", style="Secondary.TButton",
                   command=lambda: self._apply_master_file(importer.current_master_path())).pack(side="right", padx=8)
        ttk.Button(head, text="폴더 열기", style="Secondary.TButton",
                   command=self._open_master_folder).pack(side="right")

        self.master_path_label = ttk.Label(card, text="", style="Card.TLabel",
                                           font=(theme.FONT_FAMILY, 10, "underline"),
                                           foreground=theme.ACCENT, cursor="hand2", wraplength=900)
        self.master_path_label.pack(anchor="w", pady=(6, 0))
        self.master_path_label.bind("<Button-1>", lambda e: self._open_master_file())

        self.master_hint_label = ttk.Label(card, text="", style="CardSecondary.TLabel")
        self.master_hint_label.pack(anchor="w", pady=(4, 0))

        self._master_drop_targets = (card, head, self.master_path_label, self.master_hint_label)
        self._refresh_master_card()

    def enable_file_drop(self, register) -> None:
        """App이 넘겨준 등록 함수로 마스터 카드 영역을 파일 드롭 대상으로 만든다."""
        for widget in self._master_drop_targets:
            register(widget, self._on_files_dropped)

    def _refresh_master_card(self):
        path = importer.current_master_path()
        self.master_path_label.configure(text=str(path))
        count = len(db.all_items())
        status = f"품목 {count:,}개 등록됨 · 시트 [{SOURCE_MASTER_SHEET}]"
        if not path.exists():
            status = "⚠ 파일을 찾을 수 없습니다 · " + status
        self.master_hint_label.configure(
            text=status + " · 경로를 클릭하면 엑셀이 열립니다 · 엑셀 파일을 이 영역에 끌어다 놓아도 교체됩니다."
        )

    def _open_master_file(self):
        path = importer.current_master_path()
        if not path.exists():
            messagebox.showwarning("안내", f"마스터 파일을 찾을 수 없습니다:\n{path}")
            return
        os.startfile(str(path))

    def _open_master_folder(self):
        folder = importer.current_master_path().parent
        if not folder.exists():
            messagebox.showwarning("안내", f"폴더를 찾을 수 없습니다:\n{folder}")
            return
        os.startfile(str(folder))

    def _choose_master_file(self):
        path = filedialog.askopenfilename(
            title="마스터 엑셀 선택",
            initialdir=str(importer.current_master_path().parent),
            filetypes=[("Excel 파일", "*.xlsx *.xlsm"), ("모든 파일", "*.*")],
        )
        if path:
            self._apply_master_file(Path(path))

    def _on_files_dropped(self, paths):
        candidates = [Path(p) for p in paths if Path(p).suffix.lower() in (".xlsx", ".xlsm")]
        if not candidates:
            messagebox.showwarning("안내", "엑셀 파일(.xlsx/.xlsm)만 마스터로 사용할 수 있습니다.")
            return
        self._apply_master_file(candidates[0])

    def _apply_master_file(self, path: Path):
        """선택/드롭된 엑셀로 마스터 DB를 갱신한다."""
        path = Path(path)
        if not path.exists():
            messagebox.showwarning("안내", f"파일을 찾을 수 없습니다:\n{path}")
            return
        dialog = MasterReplaceDialog(self, path)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        try:
            result = importer.sync_master(path, replace=(dialog.result == "replace"))
        except Exception as exc:  # 시트 구조가 다른 파일을 고른 경우 등
            messagebox.showerror("불러오기 실패", f"엑셀을 읽지 못했습니다:\n{exc}")
            return

        importer.remember_master_path(path)
        self._load(db.all_items())
        self._refresh_master_card()
        messagebox.showinfo(
            "불러오기 완료",
            f"신규 {result['added']}개 · 갱신 {result['updated']}개 (엑셀 {result['total']}행)",
        )

    # ---- 목록 ----
    def _load(self, items):
        self._items = list(items)
        if self._sort_col:
            self._items.sort(key=self.SORT_KEYS[self._sort_col], reverse=self._sort_reverse)
        self._render()

    def _sort_by(self, col: str):
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._items.sort(key=self.SORT_KEYS[col], reverse=self._sort_reverse)
        theme.update_sort_headings(self.tree, self.COLUMNS, self.HEADINGS, self._sort_col, self._sort_reverse)
        self._render()

    def _row_values(self, item):
        return (item["category"], item["order_name"], item["manufacturer"], item["product_name"] or "",
                item["spec"], f'{item["buy_price"]:,.0f}', f'{item["sell_price"]:,.0f}',
                item["base_date"] or "")

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        for idx, item in enumerate(self._items):
            tag = "normal_even" if idx % 2 == 0 else "normal_odd"
            self.tree.insert("", "end", iid=str(item["id"]), tags=(tag,), values=self._row_values(item))

    def _search(self):
        keyword = self.search_var.get().strip()
        self._load(db.search_items(keyword) if keyword else db.all_items())

    def _clear_search(self):
        self.search_var.set("")
        self._load(db.all_items())

    # ---- 셀 인라인 편집 ----
    def _editor_value(self, row_iid: str, col_name: str) -> str:
        """가격은 천단위 콤마를 뺀 숫자를 그대로 편집한다."""
        item = self._item_by_iid(row_iid)
        if item is None:
            return self.tree.set(row_iid, col_name)
        if col_name == "buy":
            return f'{item["buy_price"]:g}'
        if col_name == "sell":
            return f'{item["sell_price"]:g}'
        return self.tree.set(row_iid, col_name)

    def _item_by_iid(self, row_iid: str):
        item_id = int(row_iid)
        for item in self._items:
            if item["id"] == item_id:
                return item
        return None

    def _commit_cell_edit(self, row_iid: str, col_name: str, new_value: str):
        new_value = new_value.strip()
        item = self._item_by_iid(row_iid)
        if item is None:
            return None

        if col_name in self.TEXT_FIELDS:
            self._save_text_field(item, self.TEXT_FIELDS[col_name], new_value)
        else:
            self._save_price_field(item, col_name, new_value)

        self.tree.item(row_iid, values=self._row_values(item))
        self.tree.selection_set(row_iid)
        return self._next_editable(row_iid, col_name)

    def _next_editable(self, row_iid: str, col_name: str):
        idx = self.EDITABLE.index(col_name)
        if idx + 1 < len(self.EDITABLE):
            return row_iid, self.EDITABLE[idx + 1]
        return None

    def _save_text_field(self, item, field: str, value: str):
        if field == "order_name" and not value:
            messagebox.showwarning("입력 오류", "제너리스주문명은 비울 수 없습니다.")
            return
        if item[field] == value:
            return
        db.update_item_fields(item["id"], **{field: value})
        item[field] = value
        if field == "order_name":
            db.add_alias(item["id"], value)  # 바뀐 이름으로도 매칭되도록 별칭에 남긴다

    def _save_price_field(self, item, col_name: str, value: str):
        try:
            number = float(value.replace(",", ""))
        except ValueError:
            messagebox.showwarning("입력 오류", "매입가/매출가는 숫자여야 합니다.")
            return
        buy = number if col_name == "buy" else item["buy_price"]
        sell = number if col_name == "sell" else item["sell_price"]
        if buy == item["buy_price"] and sell == item["sell_price"]:
            return
        if buy > sell and not messagebox.askyesno("역마진 경고", "매입가가 매출가보다 큽니다. 그대로 수정할까요?"):
            return
        db.update_item_prices(item["id"], buy, sell, memo="품목 마스터 관리 화면에서 수정")
        item.update(db.get_item(item["id"]))

    # ---- 선택 품목 상세 ----
    def _on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        item = db.get_item(int(sel[0]))
        if item is None:
            return
        self._selected_item = item
        self.detail_label.configure(
            text=f'{item["order_name"]}  |  {item["manufacturer"]}  |  {item["product_name"]}'
        )
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

    def _show_history(self):
        if not self._selected_item:
            return
        PriceHistoryDialog(self, self._selected_item)


def _apply_window_icon(win):
    """소스 실행·exe 실행 모두에서 app.ico를 창 아이콘으로 적용한다."""
    here = Path(__file__).resolve().parent
    for root in (Path(getattr(sys, "_MEIPASS", here)), here, here.parent):
        ico = root / "app.ico"
        if ico.exists():
            try:
                win.iconbitmap(default=str(ico))
            except Exception:
                pass
            return


class App(BaseTk):
    def __init__(self):
        super().__init__()
        self.title("제너리스 주문 변환·관리")
        _apply_window_icon(self)
        self.geometry("1180x780")
        theme.apply(self)

        db.init_db()
        if db.is_empty():
            try:
                result = importer.sync_master(importer.current_master_path())
                messagebox.showinfo("초기 설정", f"마스터 엑셀에서 {result['total']}개 품목을 불러왔습니다.")
            except FileNotFoundError:
                messagebox.showwarning(
                    "안내",
                    "마스터 엑셀 파일을 찾지 못해 빈 DB로 시작합니다.\n"
                    "품목 마스터 관리 화면에서 마스터 파일을 지정해주세요.",
                )

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        notebook.add(OrderTab(notebook), text="새 주문 처리")
        master_tab = MasterTab(notebook)
        notebook.add(master_tab, text="품목 마스터 관리")
        master_tab.enable_file_drop(self._register_file_drop)

    def _register_file_drop(self, widget, handler) -> None:
        """탐색기에서 끌어다 놓은 파일 경로 목록을 handler로 넘긴다.

        tkinterdnd2가 없으면 드롭만 동작하지 않고 나머지 기능은 그대로 쓴다.
        """
        if DND_FILES is None:
            return
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", lambda event: handler(list(self.tk.splitlist(event.data))))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
