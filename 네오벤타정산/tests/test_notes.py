"""T7-1 — 비고 제한 조건 해석 (EDI월 = 처방월)."""
from __future__ import annotations

from core.notes import check_restrictions, parse_note


def test_정산종료월():
    rules = parse_note("26년 3월 EDI까지 정산가능")
    assert rules.end_month == "2026-03"
    assert rules.start_month is None


def test_정산시작월():
    assert parse_note("25년 11월 EDI부터 정산가능").start_month == "2025-11"
    assert parse_note("26년 1월 EDI부터 정산재개").start_month == "2026-01"


def test_신규금지():
    rules = parse_note("신규금지 (26.07 EDI부터)")
    assert rules.new_ban_from == "2026-07"
    assert rules.end_month is None


def test_시작과_종료가_함께():
    rules = parse_note(
        "26년 1월 EDI부터 정산재개 /26년 3월 EDI까지 정산가능(추후 재입고시 정산재개 예정)"
    )
    assert (rules.start_month, rules.end_month) == ("2026-01", "2026-03")


def test_해석못한_비고는_참고정보():
    for note in (
        "25.12 일부 제조번호 회수조치",
        "[집중 프로모션 44%→63%]",
        "26년 3월 EDI부터 수수료 변동(36%→40%)",
        "26년 1월 EDI부터 약가변동 (245원→242원)",
    ):
        rules = parse_note(note)
        assert not rules.has_rule
        assert rules.info


def test_t7_1_EDI월_경계():
    """코미정: 처방월 2026-03 / 정산월 2026-04 → 통과. 처방월 2026-04 → 검출."""
    rules = parse_note("26년 3월 EDI까지 정산가능")
    assert check_restrictions(rules, "2026-03") == []
    hits = check_restrictions(rules, "2026-04")
    assert [h.kind for h in hits] == ["END"]


def test_신규금지는_신규처만():
    rules = parse_note("신규금지 (26.07 EDI부터)")
    assert check_restrictions(rules, "2026-08", is_new_client=False) == []
    assert [h.kind for h in check_restrictions(rules, "2026-08", is_new_client=True)] == ["NEW_BAN"]
    # 시작월 전이면 신규처여도 걸리지 않는다.
    assert check_restrictions(rules, "2026-06", is_new_client=True) == []
