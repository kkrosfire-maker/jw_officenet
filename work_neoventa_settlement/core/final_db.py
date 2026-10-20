"""최종 엑셀 DB 표 읽기.

정산 전 검사에 쓴다: 마지막 적용값(VALUE_CHANGED), 신규처 판정, 같은 정산월 중복.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import openpyxl

from .config import FINAL_DETAIL_SHEET, FINAL_HEADER_ROW
from .utils import clean_str, parse_month, to_number


@dataclass
class DBRow:
    row: int
    values: tuple                 # A~S 원본 값 (그대로 다시 쓸 때 사용)
    처방월: Optional[str]
    정산월: Optional[str]
    병원명: str
    제약사: str
    제품명: str
    단가: Optional[float]
    수수료: Optional[float]
    구간인센: Optional[float]
    특별인센: Optional[float]
    정산내역확인: str


class FinalDB:
    """DB 표의 기존 행 모음."""

    def __init__(self, rows: list[DBRow], sheet_max_row: int, table_ref: str = ""):
        self.rows = rows
        self.sheet_max_row = sheet_max_row
        self.table_ref = table_ref

    # ---- 조회

    def months(self) -> list[str]:
        return sorted({r.정산월 for r in self.rows if r.정산월})

    def rows_for_month(self, settlement_month: str) -> list[DBRow]:
        return [r for r in self.rows if r.정산월 == settlement_month]

    def last_applied(self, 제품명: str, *, exclude_month: Optional[str] = None) -> Optional[DBRow]:
        """같은 제품에 마지막으로 적용한 값 (처방월이 가장 늦은 행)."""
        name = clean_str(제품명)
        hits = [
            r
            for r in self.rows
            if clean_str(r.제품명) == name and (exclude_month is None or r.정산월 != exclude_month)
        ]
        if not hits:
            return None
        return max(hits, key=lambda r: (r.처방월 or "", r.정산월 or "", r.row))

    def is_new_client(
        self,
        병원명: str,
        제품명: str,
        before_month: str,
        *,
        exclude_month: Optional[str] = None,
    ) -> bool:
        """신규처 판정: 처방월이 before_month 보다 앞선 같은 병원 × 같은 제품 행이 없으면 신규처."""
        hospital, product = clean_str(병원명), clean_str(제품명)
        for r in self.rows:
            if exclude_month is not None and r.정산월 == exclude_month:
                continue
            if clean_str(r.병원명) != hospital or clean_str(r.제품명) != product:
                continue
            if r.처방월 and r.처방월 < before_month:
                return False
        return True


def load_final_db(path: str | Path) -> FinalDB:
    wb = openpyxl.load_workbook(path, data_only=False)
    try:
        if FINAL_DETAIL_SHEET not in wb.sheetnames:
            raise RuntimeError(
                f"[{FINAL_DETAIL_SHEET}] 시트가 없습니다. 있는 시트: {wb.sheetnames}"
            )
        ws = wb[FINAL_DETAIL_SHEET]
        table = (ws.tables or {}).get("DB")
        table_ref = getattr(table, "ref", "") if table is not None else ""
        rows: list[DBRow] = []
        for idx, values in enumerate(
            ws.iter_rows(min_row=FINAL_HEADER_ROW + 1, max_col=19, values_only=True),
            start=FINAL_HEADER_ROW + 1,
        ):
            if not any(values):
                continue
            rows.append(
                DBRow(
                    row=idx,
                    values=tuple(values) + (None,) * (19 - len(values)),
                    처방월=parse_month(values[1]),
                    정산월=parse_month(values[2]),
                    병원명=clean_str(values[4]),
                    제약사=clean_str(values[5]),
                    제품명=clean_str(values[7]),
                    단가=to_number(values[8]),
                    수수료=to_number(values[11]),
                    구간인센=to_number(values[12]),
                    특별인센=to_number(values[13]),
                    정산내역확인=clean_str(values[18]),
                )
            )
        return FinalDB(rows, ws.max_row, table_ref)
    finally:
        wb.close()
