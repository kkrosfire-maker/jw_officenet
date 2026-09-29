"""T3~T9, T13 — 변환 규칙."""
from __future__ import annotations

import pytest

from core import converter as conv
from core import lawdata

from .conftest import LAWDATA, SETTLEMENT_MONTH, SETTLEMENT_SHEET


def test_t3_보험코드_매칭(ctx, law_rows_september):
    result = conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH)
    assert result.issues_of(conv.NEW_PRODUCT) == []
    assert result.issues_of(conv.PRODUCT_RENAMED) == []
    assert result.issues_of(conv.PRODUCT_CODE_CHANGED) == []
    assert result.issues_of(conv.NOT_IN_RATE_TABLE) == []


def test_t4_제품명과_요율이_기존_최종파일과_같다(resolved_result, final_db):
    기존 = final_db.rows_for_month(SETTLEMENT_MONTH)
    assert len(resolved_result.rows) == len(기존) == 44
    for new, ref in zip(resolved_result.rows, 기존):
        assert new.병원명 == ref.병원명
        assert new.제품명 == ref.제품명
        assert new.단가 == ref.단가
        assert (new.수수료 or 0) == (ref.수수료 or 0)
        assert (new.구간인센 or 0) == (ref.구간인센 or 0)
        assert (new.특별인센 or 0) == (ref.특별인센 or 0)


def test_t5_구분과_제약사는_요율표를_따른다(resolved_result):
    by_company = {}
    for row in resolved_result.rows:
        by_company.setdefault(row.제약사, set()).add(row.구분)
    assert by_company["안국뉴팜"] == {3}
    assert by_company["명문제약"] == {2}
    assert by_company["유니메드"] == {"유니"}


def test_t6_단가불일치는_오바램정_한건(ctx, law_rows_september):
    result = conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH)
    issues = result.issues_of(conv.PRICE_MISMATCH)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.제품명 == "오바램정100mg"
    assert issue.detail == {"lawdata단가": 1500, "요율표약가": 2500}
    # 기본값을 미리 정하지 않는다
    affected = [r for r in result.rows if r.order in issue.rows]
    assert affected and all(r.단가 is None for r in affected)


def test_단가는_선택한_값을_쓴다(ctx, law_rows_september):
    result = conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH)
    key = result.issues_of(conv.PRICE_MISMATCH)[0].key
    for choice, expected in (({"choice": "rate"}, 2500), ({"choice": "lawdata"}, 1500),
                             ({"choice": "custom", "value": 1234}, 1234)):
        again = conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH, {key: choice})
        오바램 = [r for r in again.rows if r.제품명 == "오바램정100mg"]
        assert 오바램 and all(r.단가 == expected for r in 오바램)


def test_t7_정산제한은_아이맘_코미정_한건(ctx, law_rows_september):
    result = conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH)
    issues = result.issues_of(conv.NOTE_RESTRICTION)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.제품명 == "코미정"
    assert issue.detail["병원명"] == "아이맘소아청소년과의원"
    assert issue.detail["처방월"] == "2026-08"
    assert "END" in issue.detail["종류"]


def test_t7_황도영_빌다틴은_기존처라서_미검출(ctx, law_rows_september):
    """빌다틴은 '신규금지 (26.07 EDI부터)' 지만 황도영의원은 기존처다."""
    result = conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH)
    hits = [i for i in result.issues_of(conv.NOTE_RESTRICTION) if i.제품명.startswith("빌다틴")]
    assert hits == []


def test_t8_소액처(resolved_result):
    groups = {(g["병원명"], g["제약사"]) for g in resolved_result.small_groups}
    assert groups == {
        ("개나리소아청소년과병원", "명문제약"),
        ("개나리소아청소년과병원", "코오롱제약"),
        ("다솜의원(양산)", "명문제약"),
        ("다솜의원(양산)", "코오롱제약"),
        ("성진내과의원", "명문제약"),
        ("성진내과의원", "코오롱제약"),
        ("아이맘소아청소년과의원", "코오롱제약"),
        ("황도영의원", "안국뉴팜"),
    }
    assert sum(1 for r in resolved_result.rows if r.소액처) == 15
    assert all(r.확정금액 == 0 for r in resolved_result.rows if r.소액처)


def test_최소인정금액_없음이면_판정안한다(resolved_result):
    """보령제약은 '없음' 이라 금액이 작아도 소액처가 아니다."""
    assert all(g["제약사"] != "보령제약" for g in resolved_result.small_groups)


def test_t9_확정금액_합계(resolved_result):
    assert resolved_result.확정금액합계 == pytest.approx(5_120_288.65, abs=0.01)


def test_모든_검토를_끝내야_준비완료(ctx, law_rows_september):
    first = conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH)
    assert not first.ready
    assert {i.code for i in first.open_issues} >= {
        conv.DUPLICATE_MONTH,
        conv.PRICE_MISMATCH,
        conv.NOTE_RESTRICTION,
    }


def test_중복정산월_감지(ctx, law_rows_september):
    result = conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH)
    issue = result.issue(conv.DUPLICATE_MONTH)
    assert issue is not None and issue.detail["existing"] == 44


def test_제한조건_제외하면_행이_빠진다(ctx, law_rows_september):
    result = conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH)
    key = result.issues_of(conv.NOTE_RESTRICTION)[0].key
    again = conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH, {key: {"include": False}})
    assert len(again.rows) == 43
    assert len(again.excluded) == 1
    assert again.excluded[0].제품명 == "코미정"


def test_t13_보험코드_변경_연결_제안(ctx):
    """7월 시트 2026-04 정산분: 코미정[삭제된 제품](SC6228163) → 코미정."""
    rows = lawdata.load_settlement(LAWDATA, "7월", "2026-04")
    result = conv.convert(rows, ctx, "2026-04")
    issues = result.issues_of(conv.PRODUCT_CODE_CHANGED)
    assert len(issues) == 1
    detail = issues[0].detail
    assert detail["lawdata약제명"] == "코미정[삭제된 제품]"
    assert detail["새코드"] == "SC6228163"
    assert detail["추천제품"] == "코미정"
    assert detail["기존코드"] == "SB0361186"


def test_적용값_변경_확인(ctx, law_rows_september):
    """최종 DB 의 마지막 적용값과 다르면 확인을 요구한다."""
    result = conv.convert(
        law_rows_september, ctx, SETTLEMENT_MONTH, {conv.DUPLICATE_MONTH: {"action": "replace"}}
    )
    changed = result.issues_of(conv.VALUE_CHANGED)
    assert changed
    for issue in changed:
        assert issue.detail["이전값"] != issue.detail["새값"]
        assert issue.detail["이전정산월"] < SETTLEMENT_MONTH


def test_참고정보는_막지_않는다(resolved_result):
    """해석 못한 비고와 프로모션은 참고로만 붙는다."""
    진토젯 = [r for r in resolved_result.rows if r.제품명.startswith("진토젯")]
    assert 진토젯
    assert any("집중 프로모션" in note for row in 진토젯 for note in row.참고)
    assert resolved_result.ready
