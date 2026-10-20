"""발주처 제출용 엑셀(260914 제너리스 주문.xlsx 테마) 생성."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Color, Font, PatternFill, Side

FONT_NAME = "맑은 고딕"
PRICE_FORMAT = "#,##0_);[Red](#,##0)"
HEADER = ["품목", "수량", "요청사항", "품목", "매입가", "매출가"]
FIXED_WIDTHS = {"C": 4.75, "F": 8.625, "G": 9.5}
AUTOFIT_PADDING = {"B": 1.375, "D": 2.125, "E": 1.0}
AUTOFIT_MIN = {"B": 8, "D": 12, "E": 8}

BODY_FONT = Font(name=FONT_NAME, size=11)
HEADER_FONT = Font(name=FONT_NAME, size=11, bold=True)
HEADER_FILL = PatternFill(patternType="solid", fgColor=Color(theme=6, tint=0.5999938962981048))
THIN = Side(style="thin")
CELL_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER_MIDDLE = Alignment(horizontal="center", vertical="center")
LEFT_MIDDLE = Alignment(vertical="center")


def _display_width(text: str) -> float:
    """한글 등 전각 문자는 2칸, 나머지는 1칸으로 어림잡아 열 너비를 추정."""
    width = 0.0
    for ch in str(text):
        width += 2 if ord(ch) > 0x1100 else 1
    return width


def export_order(order_date_label: str, lines: list[dict], output_path: Path) -> Path:
    """lines: [{raw_text, quantity, requirement_text, spec_text, buy_price, sell_price}, ...]"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.sheet_format.defaultRowHeight = 16.5

    title_cell = ws.cell(row=2, column=2, value=f"{order_date_label} 주문")
    title_cell.font = BODY_FONT
    title_cell.alignment = LEFT_MIDDLE

    for col_offset, title in enumerate(HEADER):
        cell = ws.cell(row=3, column=2 + col_offset, value=title)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = CELL_BORDER
        cell.alignment = LEFT_MIDDLE

    centered_cols = {2, 3, 5}  # B(품목), C(수량), E(품목/규격)
    max_len = {"B": _display_width("품목"), "D": _display_width("요청사항"), "E": _display_width("품목")}

    for row_offset, line in enumerate(lines):
        r = 4 + row_offset
        raw_cell = ws.cell(row=r, column=2, value=line.get("raw_text", ""))
        qty_cell = ws.cell(row=r, column=3, value=line.get("quantity"))
        req_cell = ws.cell(row=r, column=4, value=line.get("requirement_text", ""))
        spec_cell = ws.cell(row=r, column=5, value=line.get("spec_text", ""))
        buy_cell = ws.cell(row=r, column=6, value=line.get("buy_price"))
        sell_cell = ws.cell(row=r, column=7, value=line.get("sell_price"))

        for col_index, cell in enumerate((raw_cell, qty_cell, req_cell, spec_cell, buy_cell, sell_cell), start=2):
            cell.font = BODY_FONT
            cell.border = CELL_BORDER
            cell.alignment = CENTER_MIDDLE if col_index in centered_cols else LEFT_MIDDLE

        buy_cell.number_format = PRICE_FORMAT
        sell_cell.number_format = PRICE_FORMAT

        max_len["B"] = max(max_len["B"], _display_width(raw_cell.value))
        max_len["D"] = max(max_len["D"], _display_width(req_cell.value))
        max_len["E"] = max(max_len["E"], _display_width(spec_cell.value))

    for col in ("B", "D", "E"):
        ws.column_dimensions[col].width = max(AUTOFIT_MIN[col], max_len[col] + AUTOFIT_PADDING[col])
    for col, width in FIXED_WIDTHS.items():
        ws.column_dimensions[col].width = width

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
