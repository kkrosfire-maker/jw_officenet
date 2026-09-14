"""발주처 제출용 엑셀(260907 제너리스 주문.xlsx 양식) 생성."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

PRICE_FORMAT = "#,##0.00_);[Red](#,##0.00)"
HEADER = ["품목", "수량", "요청사항", "품목", "매입가", "매출가"]
COL_WIDTHS = {"B": 15.75, "C": 4.75, "D": 41.5, "E": 43.875, "F": 8.625, "G": 9.5}


def export_order(order_date_label: str, lines: list[dict], output_path: Path) -> Path:
    """lines: [{raw_text, quantity, requirement_text, spec_text, buy_price, sell_price}, ...]"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    ws.cell(row=2, column=2, value=f"{order_date_label} 주문")

    for col_offset, title in enumerate(HEADER):
        cell = ws.cell(row=3, column=2 + col_offset, value=title)
        cell.font = Font(bold=True)

    for row_offset, line in enumerate(lines):
        r = 4 + row_offset
        ws.cell(row=r, column=2, value=line.get("raw_text", ""))
        ws.cell(row=r, column=3, value=line.get("quantity"))
        ws.cell(row=r, column=4, value=line.get("requirement_text", ""))
        ws.cell(row=r, column=5, value=line.get("spec_text", ""))
        buy_cell = ws.cell(row=r, column=6, value=line.get("buy_price"))
        sell_cell = ws.cell(row=r, column=7, value=line.get("sell_price"))
        buy_cell.number_format = PRICE_FORMAT
        sell_cell.number_format = PRICE_FORMAT

    for col, width in COL_WIDTHS.items():
        ws.column_dimensions[col].width = width

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
