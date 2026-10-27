"""주문 기록(언제 얼마나 나갔는지)과 니들·시린지 월 주문 한도 계산.

tkinter/DB에 의존하지 않는 순수 로직만 둔다.
"""
import datetime as dt
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.config import MONTHLY_QUOTA, PIECES_PER_BOX


# 마스터 제품명·규격에 적힌 박스당 수량 표기: 25/B, 100개, 100ea, 100(1박스), 100/개
# '대박스 12개'는 큰 박스 안의 박스 수라서 제외한다.
_BOX_QTY_RE = re.compile(r"(?<!대박스 )(?<!대박스)(?<![\d.])(\d+)\s*(?:개|ea\b|/\s*B\b|\(1박스\)|/\s*개)",
                         re.IGNORECASE)


def pieces_per_box(item: dict | None) -> int:
    """마스터 품목의 박스당 낱개 수. 제품명·규격에 표기가 없으면 PIECES_PER_BOX(100)."""
    item = item or {}
    text = f'{item.get("product_name") or ""} {item.get("spec") or ""}'
    for m in _BOX_QTY_RE.finditer(text):
        n = int(m.group(1))
        if n > 1:
            return n
    return PIECES_PER_BOX


def to_pieces(boxes, item: dict | None = None) -> float:
    """주문 수량(박스)을 그 품목의 박스당 수량으로 곱해 낱개 수로 바꾼다."""
    return (boxes or 0) * pieces_per_box(item)


def _row_item(row: dict) -> dict:
    return {"product_name": row.get("item_product"), "spec": row.get("item_spec")}


def parse_order_date(text: str | None) -> dt.date | None:
    """주문일자 입력값(261026 / 20261026 / 2026-10-26 등)을 날짜로 바꾼다. 못 읽으면 None."""
    digits = re.sub(r"\D", "", text or "")
    try:
        if len(digits) == 6:
            return dt.date(2000 + int(digits[:2]), int(digits[2:4]), int(digits[4:6]))
        if len(digits) == 8:
            return dt.date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None
    return None


def month_usage(rows, year: int, month: int) -> dict[str, float]:
    """rows: [{order_date, category, quantity(박스), item_product, item_spec}, ...]
    → 해당 월 한도 품목별 낱개 합계."""
    usage = {cat: 0.0 for cat in MONTHLY_QUOTA}
    for row in rows:
        cat = row.get("category")
        if cat not in usage:
            continue
        d = parse_order_date(row.get("order_date"))
        if d and d.year == year and d.month == month:
            usage[cat] += to_pieces(row.get("quantity"), _row_item(row))
    return usage


def order_summaries(rows) -> dict[int, dict]:
    """기록 불러오기 목록용: 주문 번호별 {"names": [품목...], 한도 품목: 낱개 합계}."""
    result: dict[int, dict] = {}
    for row in rows:
        s = result.setdefault(row.get("order_id"), {"names": [], **{c: 0.0 for c in MONTHLY_QUOTA}})
        s["names"].append(row.get("raw_text") or "")
        cat = row.get("category")
        if cat in MONTHLY_QUOTA:
            s[cat] += to_pieces(row.get("quantity"), _row_item(row))
    return result


def quota_status(saved: dict[str, float], current: dict[str, float]) -> list[dict]:
    """한도 품목별 [{category, ordered, limit, remaining}] — ordered는 저장된 주문 + 지금 입력 중인 주문."""
    result = []
    for cat, limit in MONTHLY_QUOTA.items():
        ordered = saved.get(cat, 0) + current.get(cat, 0)
        result.append({"category": cat, "ordered": ordered, "limit": limit,
                       "remaining": limit - ordered})
    return result


# ---- 엑셀 기록 파일 ----
FONT_NAME = "맑은 고딕"
LOG_HEADER = ["주문일자", "항목", "품목", "수량(박스)", "낱개(니들·시린지)", "제품명", "규격",
              "매입가", "매출가", "특이사항"]
LOG_WIDTHS = [12, 14, 26, 11, 17, 50, 18, 11, 11, 24]
PRICE_FORMAT = "#,##0"
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADER_FILL = PatternFill("solid", fgColor="DDEBF7")
HEADER_FONT = Font(name=FONT_NAME, bold=True)
BODY_FONT = Font(name=FONT_NAME)
CENTER = Alignment(horizontal="center", vertical="center")


def _date_label(order_date: str) -> str:
    d = parse_order_date(order_date)
    return d.isoformat() if d else (order_date or "")


def _write_table(ws, header, widths, rows, centered=(), price_cols=()):
    for c, (title, width) in enumerate(zip(header, widths), start=1):
        cell = ws.cell(row=1, column=c, value=title)
        cell.font, cell.fill, cell.border, cell.alignment = HEADER_FONT, HEADER_FILL, BORDER, CENTER
        ws.column_dimensions[cell.column_letter].width = width
    for r, values in enumerate(rows, start=2):
        for c, value in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.font, cell.border = BODY_FONT, BORDER
            if c in centered:
                cell.alignment = CENTER
            if c in price_cols:
                cell.number_format = PRICE_FORMAT
    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = ws.dimensions


def write_order_log(rows, output_path: Path) -> Path:
    """저장된 전체 주문 라인으로 기록 엑셀을 새로 만든다(최근 주문이 위).

    rows: [{order_id, order_date, category, raw_text, quantity, requirement_text,
            spec_text, applied_buy, applied_sell, remark}, ...]
    """
    rows = sorted(rows, key=lambda r: (parse_order_date(r.get("order_date")) or dt.date.min,
                                       r.get("order_id") or 0), reverse=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "주문기록"
    _write_table(
        ws, LOG_HEADER, LOG_WIDTHS,
        [(_date_label(r.get("order_date")), r.get("category") or "", r.get("raw_text") or "",
          r.get("quantity"),
          to_pieces(r.get("quantity"), _row_item(r)) if r.get("category") in MONTHLY_QUOTA else None,
          r.get("requirement_text") or "", r.get("spec_text") or "",
          r.get("applied_buy"), r.get("applied_sell"), r.get("remark") or "") for r in rows],
        centered={1, 2, 4, 5, 7}, price_cols={8, 9},
    )

    # 월별 니들·시린지 합계(한도 대비)
    months: dict[tuple[int, int], dict[str, float]] = {}
    for r in rows:
        d = parse_order_date(r.get("order_date"))
        if d and r.get("category") in MONTHLY_QUOTA:
            bucket = months.setdefault((d.year, d.month), {c: 0.0 for c in MONTHLY_QUOTA})
            bucket[r["category"]] += to_pieces(r.get("quantity"), _row_item(r))
    summary = wb.create_sheet("월별 한도")
    header = ["월"] + [f"{c} 주문(개, 한도 {limit:,})" for c, limit in MONTHLY_QUOTA.items()] \
        + [f"{c} 남은 개수" for c in MONTHLY_QUOTA]
    summary_rows = []
    for (y, m) in sorted(months, reverse=True):
        used = months[(y, m)]
        summary_rows.append([f"{y}-{m:02d}"] + [used[c] for c in MONTHLY_QUOTA]
                            + [MONTHLY_QUOTA[c] - used[c] for c in MONTHLY_QUOTA])
    _write_table(summary, header, [10] + [22] * (len(header) - 1), summary_rows,
                 centered=set(range(1, len(header) + 1)))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
