"""lawdata(EDI 처방 원본) 로딩.

컬럼 위치가 월마다 다르므로 **헤더 이름으로만** 컬럼을 찾는다.
이름이 중복된 컬럼(`수정자`)은 첫 번째만 쓰고, 헤더가 없는 컬럼은 무시한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import openpyxl

from .config import LAWDATA_HEADER_ROW
from .utils import clean_str, code_key, parse_month, to_number

REQUIRED_HEADERS = ["처방월", "정산월", "거래처", "사업자등록번호", "보험코드", "제품", "단가", "수량(원외)"]
OPTIONAL_HEADERS = ["제조사"]


@dataclass
class LawRow:
    """lawdata 한 행에서 쓰는 값만 담는다."""

    source_row: int          # 엑셀 행 번호 (추적용)
    order: int               # 시트 안에서의 원본 순서 (0부터)
    처방월: Optional[str]     # 'YYYY-MM'
    정산월: Optional[str]
    거래처: str
    사업자등록번호: str
    보험코드: str
    제품: str
    제조사: str
    단가: Optional[float]
    수량: Optional[float]
    raw: dict = field(default_factory=dict, repr=False)


class LawdataError(RuntimeError):
    pass


def sheet_names(path: str | Path) -> list[str]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def suggest_sheet(names: list[str], settlement_month: str) -> Optional[str]:
    """정산월(YYYY-MM)에 맞는 시트 이름을 추천한다. 예: '2026-09' → '9월'."""
    month = int(settlement_month.split("-")[1])
    for candidate in (f"{month}월", f"{month:02d}월", str(month)):
        if candidate in names:
            return candidate
    return names[-1] if names else None


def _header_index(header_row: tuple) -> dict[str, int]:
    """헤더 이름 → 컬럼 인덱스. 중복 이름은 첫 번째만, None 헤더는 버린다."""
    index: dict[str, int] = {}
    for i, value in enumerate(header_row):
        name = clean_str(value)
        if not name or name in index:
            continue
        index[name] = i
    return index


def load_sheet(path: str | Path, sheet: str) -> list[LawRow]:
    """시트 전체를 읽는다(정산월 필터 없음). 원본 행 순서를 유지한다."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if sheet not in wb.sheetnames:
            raise LawdataError(f"시트 '{sheet}' 가 없습니다. 있는 시트: {wb.sheetnames}")
        ws = wb[sheet]
        rows = ws.iter_rows(min_row=LAWDATA_HEADER_ROW, values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            raise LawdataError(f"시트 '{sheet}' 가 비어 있습니다.")
        index = _header_index(header)
        missing = [h for h in REQUIRED_HEADERS if h not in index]
        if missing:
            raise LawdataError(f"시트 '{sheet}' 에 필요한 헤더가 없습니다: {missing}")

        def get(row: tuple, name: str):
            i = index.get(name)
            return row[i] if i is not None and i < len(row) else None

        result: list[LawRow] = []
        order = 0
        for offset, row in enumerate(rows, start=LAWDATA_HEADER_ROW + 1):
            code = code_key(get(row, "보험코드"))
            product = clean_str(get(row, "제품"))
            if not code and not product:
                continue  # 빈 행
            result.append(
                LawRow(
                    source_row=offset,
                    order=order,
                    처방월=parse_month(get(row, "처방월")),
                    정산월=parse_month(get(row, "정산월")),
                    거래처=clean_str(get(row, "거래처")),
                    사업자등록번호=clean_str(get(row, "사업자등록번호")),
                    보험코드=code,
                    제품=product,
                    제조사=clean_str(get(row, "제조사")),
                    단가=to_number(get(row, "단가")),
                    수량=to_number(get(row, "수량(원외)")),
                    raw={name: get(row, name) for name in index},
                )
            )
            order += 1
        return result
    finally:
        wb.close()


def load_settlement(path: str | Path, sheet: str, settlement_month: str) -> list[LawRow]:
    """정산월이 일치하는 행만, 원본 순서 그대로 돌려준다."""
    return [r for r in load_sheet(path, sheet) if r.정산월 == settlement_month]


def available_months(path: str | Path, sheet: str) -> list[str]:
    months = {r.정산월 for r in load_sheet(path, sheet) if r.정산월}
    return sorted(months)


def scan(path: str | Path) -> dict[str, list[str]]:
    """시트마다 들어 있는 정산월 목록. 시트가 하나뿐인 lawdata 도 그대로 다룬다."""
    result: dict[str, list[str]] = {}
    for sheet in sheet_names(path):
        try:
            result[sheet] = available_months(path, sheet)
        except LawdataError:
            result[sheet] = []
    return result


def prescription_range(rows: list[LawRow]) -> tuple[Optional[str], Optional[str]]:
    """이 행들의 처방월 범위 (가장 이른 달, 가장 늦은 달)."""
    months = sorted({r.처방월 for r in rows if r.처방월})
    if not months:
        return None, None
    return months[0], months[-1]


def product_code_pairs(path: str | Path) -> dict[str, set[str]]:
    """전체 시트에서 보험코드 → 약제명 집합을 모은다(마스터 초기화용)."""
    pairs: dict[str, set[str]] = {}
    for sheet in sheet_names(path):
        try:
            rows = load_sheet(path, sheet)
        except LawdataError:
            continue
        for row in rows:
            if not row.보험코드:
                continue
            pairs.setdefault(row.보험코드, set()).add(row.제품)
    return pairs
