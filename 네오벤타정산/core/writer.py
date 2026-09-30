"""최종 엑셀 출력.

두 개를 만든다.
1. **기존 최종 엑셀에 이번 달 행을 추가**한다 (원본을 고치기 전에 data/backup/ 에 백업).
2. **바탕화면에 그 해의 정산분만 담은 파일**을 만든다.
   이름: `정원유니어스 판매정산내역 (YYMM) 네오벤타.xlsx` (YYMM = 정산연월)
"""
from __future__ import annotations

import shutil
from copy import copy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table

from .config import (
    BACKUP_DIR,
    FINAL_DETAIL_SHEET,
    FINAL_HEADER_ROW,
    FINAL_SUMMARY_ISSUE_CELL,
    FINAL_SUMMARY_SHEET,
    FINAL_TABLE_NAME,
    ensure_dirs,
)
from .converter import ConversionResult, OutRow
from .slicers import restore_slicers
from .utils import desktop_dir, month_to_date, yymm

AMOUNT_FORMULA = "=DB[[#This Row],[수량]]*DB[[#This Row],[단가]]"
FIXED_FORMULA = "=DB[[#This Row],[금액]]*O{row}"
RATE_FORMULA = "=N{row}+M{row}+L{row}-1%"

SMALL_ACCOUNT_LABEL = "소액처"
FIRST_DATA_ROW = FINAL_HEADER_ROW + 1
LAST_COLUMN = 19


@dataclass
class WriteReport:
    final_path: Path          # 내용을 추가한 기존 최종 엑셀
    desktop_path: Path        # 바탕화면에 만든 그 해 정산 파일
    backup_path: Optional[Path]
    추가행수: int
    교체행수: int
    금액합계: float
    확정금액합계: float
    소액처그룹: int
    소액처행수: int
    슬라이서: int
    표범위: str
    총행수: int
    연도행수: int
    연도: str

    # 이전 이름과의 호환
    @property
    def path(self) -> Path:
        return self.desktop_path


def desktop_file_name(settlement_month: str) -> str:
    """'2026-09' → '정원유니어스 판매정산내역 (2609) 네오벤타.xlsx'"""
    return f"정원유니어스 판매정산내역 ({yymm(settlement_month)}) 네오벤타.xlsx"


def build_output_path(settlement_month: str, out_dir=None) -> Path:
    base = Path(out_dir) if out_dir else desktop_dir()
    return base / desktop_file_name(settlement_month)


def _row_values(row: OutRow, vendor: str) -> list:
    """OutRow → A~S 값 (K/O/P 수식은 나중에 채운다)."""
    return [
        row.수탁업체명 or vendor,
        month_to_date(row.처방월) if row.처방월 else None,
        month_to_date(row.정산월) if row.정산월 else None,
        row.사업자번호,
        row.병원명,
        row.제약사,
        row.구분,
        row.제품명,
        row.단가,
        row.수량,
        None,                      # K 금액 (수식)
        row.수수료,
        row.구간인센,
        row.특별인센,
        None,                      # O 최종요율 (수식)
        None,                      # P 확정금액 (수식 또는 0)
        None,                      # Q 비고
        None,                      # R 정책1
        SMALL_ACCOUNT_LABEL if row.소액처 else None,
    ]


def _month_text(value) -> str:
    if hasattr(value, "year"):
        return f"{value.year:04d}-{value.month:02d}"
    return str(value or "")


def _read_rows(ws) -> list[list]:
    rows = []
    for row_idx in range(FIRST_DATA_ROW, ws.max_row + 1):
        values = [ws.cell(row=row_idx, column=c).value for c in range(1, LAST_COLUMN + 1)]
        if any(v is not None and v != "" for v in values):
            rows.append(values)
    return rows


def _style_template(ws):
    last = ws.max_row
    if last < FIRST_DATA_ROW:
        return None, None
    styles = [copy(ws.cell(row=last, column=c)._style) for c in range(1, LAST_COLUMN + 1)]
    formats = [ws.cell(row=last, column=c).number_format for c in range(1, LAST_COLUMN + 1)]
    return styles, formats


def _write_rows(ws, rows: list[list], *, new_from: int, small_flags: list[bool], styles, formats) -> int:
    """행들을 DB 표 자리에 쓰고, 마지막 행 번호를 돌려준다."""
    original_last = ws.max_row
    for offset, values in enumerate(rows):
        row_idx = FIRST_DATA_ROW + offset
        is_new = offset >= new_from
        for col in range(1, LAST_COLUMN + 1):
            cell = ws.cell(row=row_idx, column=col)
            if styles is not None and is_new:
                cell._style = copy(styles[col - 1])
                cell.number_format = formats[col - 1]
            cell.value = values[col - 1]
        ws.cell(row=row_idx, column=11).value = AMOUNT_FORMULA
        ws.cell(row=row_idx, column=15).value = RATE_FORMULA.format(row=row_idx)
        if is_new:
            ws.cell(row=row_idx, column=16).value = (
                0 if small_flags[offset] else FIXED_FORMULA.format(row=row_idx)
            )
        else:
            previous = values[15]
            ws.cell(row=row_idx, column=16).value = (
                FIXED_FORMULA.format(row=row_idx)
                if isinstance(previous, str) and previous.startswith("=")
                else previous
            )

    # 남은 행 지우기
    for row_idx in range(FIRST_DATA_ROW + len(rows), original_last + 1):
        for col in range(1, LAST_COLUMN + 1):
            ws.cell(row=row_idx, column=col).value = None

    return FIRST_DATA_ROW + len(rows) - 1


def _retarget_table(ws, new_last: int) -> str:
    """표(ListObject) 범위와 자동필터 범위를 새 범위로 맞춘다."""
    new_ref = f"A{FINAL_HEADER_ROW}:{get_column_letter(LAST_COLUMN)}{new_last}"
    table: Optional[Table] = (ws.tables or {}).get(FINAL_TABLE_NAME)
    if table is None:
        raise RuntimeError(f"'{ws.title}' 시트에 {FINAL_TABLE_NAME} 표가 없습니다.")
    table.ref = new_ref
    if table.autoFilter is not None:
        table.autoFilter.ref = new_ref
        # 남아 있던 필터 조건은 새 행을 숨길 수 있어 지운다.
        table.autoFilter.filterColumn = []
        table.autoFilter.sortState = None
    if getattr(table, "sortState", None) is not None:
        table.sortState = None
    ws.auto_filter.ref = None
    return new_ref


def _set_pivot_refresh(wb) -> None:
    for sheet in wb.worksheets:
        for pivot in getattr(sheet, "_pivots", []) or []:
            pivot.cache.refreshOnLoad = True


def _backup(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, target)
    return target


def write_settlement(
    source_path: str | Path,
    result: ConversionResult,
    *,
    replace_month: bool = False,
    desktop_out_dir=None,
    vendor_name: str = "",
) -> WriteReport:
    """기존 최종 엑셀에 이번 달 행을 넣고, 바탕화면에 그 해 정산 파일을 만든다."""
    source_path = Path(source_path)
    target_month = result.settlement_month
    year = target_month.split("-")[0]

    backup_path = _backup(source_path)

    wb = openpyxl.load_workbook(source_path)
    try:
        ws = wb[FINAL_DETAIL_SHEET]
        styles, formats = _style_template(ws)

        existing = _read_rows(ws)
        kept, replaced = [], 0
        for values in existing:
            if replace_month and _month_text(values[2]).startswith(target_month):
                replaced += 1
                continue
            kept.append(values)

        new_values = [_row_values(r, vendor_name) for r in result.rows]
        all_values = kept + new_values
        small_flags = [False] * len(kept) + [r.소액처 for r in result.rows]

        new_last = _write_rows(
            ws, all_values, new_from=len(kept), small_flags=small_flags,
            styles=styles, formats=formats,
        )
        new_ref = _retarget_table(ws, new_last)

        if FINAL_SUMMARY_SHEET in wb.sheetnames:
            wb[FINAL_SUMMARY_SHEET][FINAL_SUMMARY_ISSUE_CELL] = round(result.확정금액합계, 2)
        _set_pivot_refresh(wb)
        wb.save(source_path)
    finally:
        wb.close()

    # openpyxl 은 슬라이서를 모르고 지운다. 저장 직전 백업에서 되돌린다.
    if backup_path:
        restore_slicers(backup_path, source_path)

    desktop_path = _write_year_file(
        source_path, target_month, year, result, out_dir=desktop_out_dir
    )
    # 바탕화면 파일도 openpyxl 로 저장했으니 방금 고친 원본에서 다시 옮긴다.
    slicers = restore_slicers(source_path, desktop_path)
    year_rows = sum(1 for v in all_values if _month_text(v[2]).startswith(year))

    return WriteReport(
        final_path=source_path,
        desktop_path=desktop_path,
        backup_path=backup_path,
        추가행수=len(result.rows),
        교체행수=replaced,
        금액합계=result.금액합계,
        확정금액합계=result.확정금액합계,
        소액처그룹=len(result.small_groups),
        소액처행수=sum(1 for r in result.rows if r.소액처),
        슬라이서=slicers,
        표범위=new_ref,
        총행수=len(all_values),
        연도행수=year_rows,
        연도=year,
    )


def _write_year_file(
    source_path: Path,
    settlement_month: str,
    year: str,
    result: ConversionResult,
    *,
    out_dir=None,
) -> Path:
    """방금 갱신한 최종 엑셀에서 그 해 정산분만 남겨 바탕화면에 저장한다."""
    target = build_output_path(settlement_month, out_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)

    wb = openpyxl.load_workbook(target)
    try:
        ws = wb[FINAL_DETAIL_SHEET]
        styles, formats = _style_template(ws)
        rows = [v for v in _read_rows(ws) if _month_text(v[2]).startswith(year)]
        # 전부 기존 행이므로(new_from=len) 값과 P 열을 그대로 옮기고 수식 행번호만 맞춘다.
        new_last = _write_rows(
            ws, rows, new_from=len(rows), small_flags=[False] * len(rows),
            styles=styles, formats=formats,
        )
        _retarget_table(ws, new_last)
        if FINAL_SUMMARY_SHEET in wb.sheetnames:
            wb[FINAL_SUMMARY_SHEET][FINAL_SUMMARY_ISSUE_CELL] = round(result.확정금액합계, 2)
        _set_pivot_refresh(wb)
        wb.save(target)
    finally:
        wb.close()
    return target
