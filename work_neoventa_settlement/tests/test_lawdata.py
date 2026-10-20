"""T1, T2, T11, T12 — lawdata 로딩."""
from __future__ import annotations

from core import lawdata

from .conftest import LAWDATA, SETTLEMENT_MONTH, SETTLEMENT_SHEET


def test_t1_추출_행수와_원본순서():
    rows = lawdata.load_settlement(LAWDATA, SETTLEMENT_SHEET, SETTLEMENT_MONTH)
    assert len(rows) == 44
    assert [r.order for r in rows] == sorted(r.order for r in rows)
    assert [r.source_row for r in rows] == sorted(r.source_row for r in rows)


def test_t2_첫행_처방월():
    rows = lawdata.load_settlement(LAWDATA, SETTLEMENT_SHEET, SETTLEMENT_MONTH)
    assert rows[0].처방월 == "2026-07"
    assert rows[0].정산월 == "2026-09"


def test_t11_지급유형없는_6월시트():
    """6월 시트에는 '지급유형' 컬럼이 없다. 헤더 이름 기반 로딩이면 문제없다."""
    rows = lawdata.load_sheet(LAWDATA, "6월")
    assert len(rows) == 43
    assert all(r.보험코드 for r in rows)
    assert "지급유형" not in rows[0].raw


def test_t12_7월시트_정산월_필터():
    """7월 시트에는 2~7월 정산분이 섞여 있다."""
    전체 = lawdata.load_sheet(LAWDATA, "7월")
    assert len(전체) == 221
    filtered = lawdata.load_settlement(LAWDATA, "7월", "2026-07")
    assert len(filtered) == 43


def test_중복헤더와_빈헤더_무시():
    rows = lawdata.load_sheet(LAWDATA, "9월")
    names = list(rows[0].raw)
    assert len(names) == len(set(names))
    assert all(name for name in names)


def test_시트_추천():
    names = lawdata.sheet_names(LAWDATA)
    assert lawdata.suggest_sheet(names, "2026-09") == "9월"
    assert lawdata.suggest_sheet(names, "2026-06") == "6월"
