"""정산 결과 엑셀: '정산요약' + '상세내역' 두 탭."""
from __future__ import annotations

import unicodedata
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .engine import AMOUNT_COLS, KIND_ORDER, Settlement, SummaryRow, to_number

SUMMARY_COLS = ["송하인명", "호실", "전화번호", "구분", "수량", "금액"]
DETAIL_COLS = ["송하인명", "구분", "운송장번호", "출고일", "품목명", "수하인명", *AMOUNT_COLS, "금액"]
MONEY_FMT = "#,##0"
FONT = "맑은 고딕"

HEADER_FILL = PatternFill("solid", fgColor="F1F1EF")
TOTAL_FILL = PatternFill("solid", fgColor="F7F6F3")
THIN = Side(style="thin", color="E9E9E7")


class OutputLockedError(Exception):
    pass


def _display_width(v) -> int:
    s = f"{v:,}" if isinstance(v, (int, float)) else str(v or "")
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def _style_sheet(ws, money_cols: set[int], total_row: int | None = None):
    ws.freeze_panes = "A2"
    widths = {}
    for row in ws.iter_rows():
        for cell in row:
            cell.font = Font(name=FONT, bold=cell.row == 1 or cell.row == total_row)
            cell.border = Border(bottom=THIN)
            if cell.column in money_cols and cell.row > 1:
                cell.number_format = MONEY_FMT
            widths[cell.column] = max(widths.get(cell.column, 0), _display_width(cell.value))
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
    if total_row:
        for cell in ws[total_row]:
            cell.fill = TOTAL_FILL
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = min(max(w + 3, 8), 60)


def write_report(path: Path, settlement: Settlement, rows: list[SummaryRow]):
    wb = Workbook()
    ws = wb.active
    ws.title = "정산요약"
    ws.append(SUMMARY_COLS)
    for r in rows:
        ws.append([r.name, r.room, r.phone, r.kind, r.count, to_number(r.amount)])
    total_amount = sum((r.amount for r in rows), Decimal(0))
    ws.append(["합계", "", "", "", sum(r.count for r in rows), to_number(total_amount)])
    for cell in ws["C"][1:]:
        cell.number_format = "@"
    _style_sheet(ws, money_cols={5, 6}, total_row=ws.max_row)

    wd = wb.create_sheet("상세내역")
    wd.append(DETAIL_COLS)
    for g in settlement.sorted_groups():
        ships = sorted(g.shipments, key=lambda s: (KIND_ORDER.index(s.kind), s.ship_date, s.waybill))
        for s in ships:
            wd.append([g.name, s.kind, s.waybill, s.ship_date, s.item, s.receiver,
                       *[to_number(s.fees[c]) for c in AMOUNT_COLS], to_number(s.amount)])
    for cell in wd["C"][1:]:
        cell.number_format = "@"
    _style_sheet(wd, money_cols={7, 8, 9, 10, 11})
    wd.auto_filter.ref = wd.dimensions

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        wb.save(path)
    except PermissionError:
        raise OutputLockedError(f"{path.name}이(가) 엑셀에서 열려 있습니다. 엑셀에서 파일을 닫고 다시 시도하세요.")


def default_filename(year: int, month: int) -> str:
    return f"한진택배정산_{year:04d}년{month:02d}월.xlsx"
