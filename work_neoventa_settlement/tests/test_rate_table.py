"""T15 — 요율표 로딩과 버전 비교."""
from __future__ import annotations

import shutil

import openpyxl
import pytest

from core import rate_table as rt

from .conftest import LAWDATA


def test_요율표_로딩(rate_table):
    assert rate_table.row_count > 10_000
    entry = rate_table.first("SB0520002")
    assert entry is not None
    assert entry.제약사명 == "보령제약"
    assert entry.약가 == 2500
    assert entry.요율 == 0.5


def test_보험코드는_문자열(rate_table):
    """앞자리 0 과 SB/SC 코드가 유지된다."""
    assert rate_table.first("053600350") is not None
    assert rate_table.first("SB0361186") is not None
    assert all(isinstance(code, str) for code in rate_table.entries)


def test_중복코드_감지(rate_table):
    """요율표 안에 같은 보험코드가 여러 행인 경우가 있다."""
    dups = rate_table.duplicated_codes()
    assert dups
    # 우리 제품에는 중복이 없다.
    from core import lawdata

    ours = set(lawdata.product_code_pairs(LAWDATA))
    assert ours.isdisjoint(set(dups))


def test_프로모션_시트(rate_table):
    if not rate_table.promotions:
        pytest.skip("이 요율표에는 '제약사별 프로모션' 시트가 없습니다.")
    code, notes = next(iter(rate_table.promotions.items()))
    assert notes and all(isinstance(n, str) for n in notes)


def _modify(src, dst, changes):
    """요율표 사본의 약가·요율·비고를 1건씩 바꾼다."""
    shutil.copy2(src, dst)
    wb = openpyxl.load_workbook(dst)
    ws = wb[rt.RATE_SHEET_NAME]
    header = [c.value for c in ws[rt.RATE_HEADER_ROW]]
    col = {name: i + 1 for i, name in enumerate(header) if name}
    hit = 0
    for row in range(rt.RATE_HEADER_ROW + 1, ws.max_row + 1):
        code = ws.cell(row=row, column=col["보험코드"]).value
        if str(code).strip() in changes:
            field, value = changes[str(code).strip()]
            ws.cell(row=row, column=col[field]).value = value
            hit += 1
    wb.save(dst)
    wb.close()
    assert hit == len(changes)


def test_t15_버전비교_3건(tmp_path, rate_table_path, rate_table):
    changes = {
        "SB0520002": ("약가", 2600),                       # 오바램정 약가
        "670303330": ("요율", 0.45),                       # 코부테롤 요율
        "649803490": ("비고", "26년 9월 EDI까지 정산가능"),   # 푸라칸 비고 추가
    }
    modified = tmp_path / "요율표_수정.xlsx"
    _modify(rate_table_path, modified, changes)

    new_table = rt.load_rate_table(modified)
    diffs = rt.compare(rate_table, new_table, changes)
    assert len(diffs) == 3
    found = {(d.보험코드, d.항목, d.이전값, d.새값) for d in diffs}
    assert ("SB0520002", "약가", 2500, 2600) in found
    assert ("670303330", "요율", 0.4, 0.45) in found
    assert ("649803490", "비고", "", "26년 9월 EDI까지 정산가능") in found


def test_비교는_우리제품만(tmp_path, rate_table_path, rate_table):
    modified = tmp_path / "요율표_수정2.xlsx"
    _modify(rate_table_path, modified, {"SB0520002": ("약가", 2600)})
    new_table = rt.load_rate_table(modified)
    assert rt.compare(rate_table, new_table, ["670303330"]) == []
    assert len(rt.compare(rate_table, new_table, ["SB0520002"])) == 1


def test_사라진_코드는_삭제로(rate_table):
    empty = rt.RateTable(path=rate_table.path)
    diffs = rt.compare(rate_table, empty, ["SB0520002"])
    assert [d.항목 for d in diffs] == ["삭제"]


def test_버전_등록과_승인(tmp_path, monkeypatch, rate_table_path):
    monkeypatch.setattr(rt, "RATE_TABLE_DIR", tmp_path)
    monkeypatch.setattr(rt, "RATE_TABLE_INDEX_PATH", tmp_path / "index.json")
    monkeypatch.setattr(rt.RateVersion, "path", property(lambda self: tmp_path / self.file))

    assert rt.current_version() is None
    version = rt.add_version(rate_table_path, label="테스트")
    assert version.path.exists()
    assert rt.current_version() is None          # 승인 전에는 현재 버전이 아니다
    assert rt.pending_version().file == version.file

    rt.approve_version(version.file)
    assert rt.current_version().file == version.file
    assert rt.pending_version() is None
    assert rt.load_current().row_count > 10_000
