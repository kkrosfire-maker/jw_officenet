"""T10 — 최종 엑셀 출력 (기존 파일 갱신 + 바탕화면 연도 파일)."""
from __future__ import annotations

import datetime
import shutil

import openpyxl
import pytest

from core import writer

from .conftest import FINAL, SETTLEMENT_MONTH

DETAIL = "2026년 거래처별 세부내역"


def _strip_month(path, month: str) -> int:
    """기준 파일에서 해당 정산월 행을 지운다(새로 추가하는 상황을 만든다)."""
    wb = openpyxl.load_workbook(path)
    ws = wb[DETAIL]
    removed = 0
    for row in range(ws.max_row, 7, -1):
        value = ws.cell(row=row, column=3).value
        if getattr(value, "year", None) and f"{value.year:04d}-{value.month:02d}" == month:
            for col in range(1, 20):
                ws.cell(row=row, column=col).value = None
            removed += 1
    last = ws.max_row - removed
    ws.tables["DB"].ref = f"A7:S{last}"
    ws.tables["DB"].autoFilter.ref = f"A7:S{last}"
    wb.save(path)
    wb.close()
    return removed


def _month_counts(path) -> dict[str, int]:
    wb = openpyxl.load_workbook(path)
    try:
        ws = wb[DETAIL]
        counts: dict[str, int] = {}
        for values in ws.iter_rows(min_row=8, max_row=ws.max_row, values_only=True):
            if not values[0]:
                continue
            month = values[2]
            key = f"{month.year:04d}-{month.month:02d}" if hasattr(month, "year") else "?"
            counts[key] = counts.get(key, 0) + 1
        return counts
    finally:
        wb.close()


def test_t10_기존파일에_44행이_추가된다(tmp_path, resolved_result):
    base = tmp_path / "최종엑셀.xlsx"
    shutil.copy2(FINAL, base)
    assert _strip_month(base, SETTLEMENT_MONTH) == 44

    report = writer.write_settlement(base, resolved_result, desktop_out_dir=tmp_path)
    assert report.추가행수 == 44
    assert report.교체행수 == 0
    assert report.표범위 == "A7:S353"
    assert report.final_path == base

    wb = openpyxl.load_workbook(base)
    ws = wb[DETAIL]
    assert ws.tables["DB"].ref == "A7:S353"
    assert wb["종합"]["B18"].value == pytest.approx(5_120_288.65, abs=0.01)
    wb.close()


def test_원본을_고치기_전에_백업한다(tmp_path, resolved_result):
    base = tmp_path / "최종엑셀.xlsx"
    shutil.copy2(FINAL, base)
    before = base.read_bytes()

    report = writer.write_settlement(
        base, resolved_result, replace_month=True, desktop_out_dir=tmp_path
    )
    assert report.backup_path is not None
    assert report.backup_path.exists()
    assert report.backup_path.read_bytes() == before
    assert base.read_bytes() != before        # 원본은 갱신된다


def test_바탕화면_파일이름(tmp_path, resolved_result):
    base = tmp_path / "최종엑셀.xlsx"
    shutil.copy2(FINAL, base)
    report = writer.write_settlement(
        base, resolved_result, replace_month=True, desktop_out_dir=tmp_path
    )
    assert report.desktop_path.name == "정원유니어스 판매정산내역 (2609) 네오벤타.xlsx"
    assert report.desktop_path.exists()


def test_파일이름_규칙():
    assert writer.desktop_file_name("2026-09") == "정원유니어스 판매정산내역 (2609) 네오벤타.xlsx"
    assert writer.desktop_file_name("2027-01") == "정원유니어스 판매정산내역 (2701) 네오벤타.xlsx"


def test_바탕화면_파일은_그해_정산분만(tmp_path, resolved_result):
    """다음 해에 돌리면 그 해 값만 들어간다."""
    base = tmp_path / "최종엑셀.xlsx"
    shutil.copy2(FINAL, base)

    # 2026-01 행 10개를 2025-11 정산분으로 바꿔 연도를 섞는다.
    wb = openpyxl.load_workbook(base)
    ws = wb[DETAIL]
    changed = 0
    for row in range(8, ws.max_row + 1):
        value = ws.cell(row=row, column=3).value
        if getattr(value, "year", None) == 2026 and value.month == 1 and changed < 10:
            ws.cell(row=row, column=3).value = datetime.datetime(2025, 11, 1)
            changed += 1
    wb.save(base)
    wb.close()
    assert changed == 10

    report = writer.write_settlement(
        base, resolved_result, replace_month=True, desktop_out_dir=tmp_path
    )

    전체 = _month_counts(base)
    연도파일 = _month_counts(report.desktop_path)
    assert 전체.get("2025-11") == 10          # 기존 파일에는 남아 있고
    assert "2025-11" not in 연도파일           # 바탕화면 파일에는 없다
    assert set(연도파일) == {m for m in 전체 if m.startswith("2026")}
    assert sum(연도파일.values()) == report.연도행수
    assert report.연도 == "2026"


def test_같은정산월_교체(tmp_path, resolved_result):
    base = tmp_path / "최종엑셀.xlsx"
    shutil.copy2(FINAL, base)
    report = writer.write_settlement(
        base, resolved_result, replace_month=True, desktop_out_dir=tmp_path
    )
    assert report.교체행수 == 44
    assert report.추가행수 == 44
    assert report.표범위 == "A7:S353"   # 44행 빼고 44행 넣었으니 그대로


def test_수식과_소액처_표기(tmp_path, resolved_result):
    base = tmp_path / "최종엑셀.xlsx"
    shutil.copy2(FINAL, base)
    report = writer.write_settlement(
        base, resolved_result, replace_month=True, desktop_out_dir=tmp_path
    )
    wb = openpyxl.load_workbook(report.final_path)
    ws = wb[DETAIL]
    last = ws.max_row
    assert ws.cell(row=last, column=11).value == writer.AMOUNT_FORMULA
    assert ws.cell(row=last, column=15).value == f"=N{last}+M{last}+L{last}-1%"

    소액처 = [r for r in range(310, last + 1) if ws.cell(row=r, column=19).value == "소액처"]
    assert len(소액처) == 15
    assert all(ws.cell(row=r, column=16).value == 0 for r in 소액처)
    일반 = [r for r in range(310, last + 1) if ws.cell(row=r, column=19).value is None]
    assert all(
        ws.cell(row=r, column=16).value == f"=DB[[#This Row],[금액]]*O{r}" for r in 일반
    )
    wb.close()


def test_확정금액_합계는_파이썬이_계산한다(tmp_path, resolved_result):
    """openpyxl 은 수식을 계산하지 않으므로 종합 B18 은 숫자로 들어간다."""
    base = tmp_path / "최종엑셀.xlsx"
    shutil.copy2(FINAL, base)
    report = writer.write_settlement(
        base, resolved_result, replace_month=True, desktop_out_dir=tmp_path
    )
    for path in (report.final_path, report.desktop_path):
        wb = openpyxl.load_workbook(path)
        value = wb["종합"]["B18"].value
        assert isinstance(value, (int, float))
        assert value == pytest.approx(resolved_result.확정금액합계, abs=0.01)
        wb.close()


def test_피벗은_열때_새로고침(tmp_path, resolved_result):
    base = tmp_path / "최종엑셀.xlsx"
    shutil.copy2(FINAL, base)
    report = writer.write_settlement(
        base, resolved_result, replace_month=True, desktop_out_dir=tmp_path
    )
    for path in (report.final_path, report.desktop_path):
        wb = openpyxl.load_workbook(path)
        pivots = [p for sheet in wb.worksheets for p in (getattr(sheet, "_pivots", []) or [])]
        assert pivots
        assert all(p.cache.refreshOnLoad for p in pivots)
        wb.close()
