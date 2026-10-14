"""PRD 3.9 수용 테스트: 2026년 9월 샘플."""
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from hanjin import engine
from hanjin.engine import DataError, settle
from hanjin.master import Master
from hanjin.report import write_report

SAMPLE = Path(__file__).parent / "data" / "sample_2026-09.xlsx"

EXPECTED_ALL_DIFFERENT = [
    ("★뉴트리에스*", "0107699****", "발송", 1, 1900),
    ("김판*", "0108434****", "발송", 1, 1900),
    ("뉴트리에*", "0108434****", "발송", 10, 22000),
    ("데이스터*", "0708064****", "발송", 9, 17100),
    ("성도커머*", "0109833****", "발송", 70, 133000),
    ("", "", "착신(반품)", 1, 2000),
    ("정영*", "0108434****", "발송", 1, 1900),
]


@pytest.fixture(scope="module")
def df():
    if not SAMPLE.exists():  # 개인정보가 있어 저장소에 올리지 않음 → 이 PC에만 있음
        pytest.skip("샘플 파일 없음: tests/data/sample_2026-09.xlsx")
    data, dup = engine.load_files([SAMPLE])
    assert dup == 0
    return data


def test_candidates(df):
    s = settle(df)
    got = {(c.base, c.other, c.phone) for c in s.candidates}
    assert got == {
        ("뉴트리에*", "정영*", "0108434****"),
        ("뉴트리에*", "김판*", "0108434****"),
        ("뉴트리에*", "★뉴트리에스*", "0107699****"),
    }
    assert "뉴트리에*" in s.multi_phone_names()


def test_all_different_matches_prd(df):
    pairs = {frozenset(("뉴트리에*", n)) for n in ("정영*", "김판*", "★뉴트리에스*")}
    s = settle(df, different_pairs=pairs)
    assert s.candidates == []
    rows = s.summary_rows()
    got = [(r.name, r.phone, r.kind, r.count, int(r.amount)) for r in rows]
    assert got == EXPECTED_ALL_DIFFERENT
    assert sum(r.count for r in rows) == 93
    assert sum(r.amount for r in rows) == Decimal(179800) == s.source_total
    s.verify(rows)


def test_return_charged_to_receiver(df):
    s = settle(df)
    ret = [x for x in s.shipments if x.kind == "착신(반품)"]
    assert len(ret) == 1 and ret[0].name == "성도커머*"


def test_all_same(df):
    aliases = {"정영*": "뉴트리에*", "김판*": "뉴트리에*", "★뉴트리에스*": "뉴트리에*"}
    s = settle(df, aliases=aliases)
    g = s.groups["뉴트리에*"]
    assert g.count["발송"] == 13 and g.amount["발송"] == Decimal(27700)
    assert s.candidates == []


def test_master_roundtrip_and_report(df, tmp_path):
    m = Master(tmp_path / "m.xlsx", tmp_path / "backup")
    m.record_different("정영*", "뉴트리에*", "0108434****")
    m.record_same("김판*", "뉴트리에*", "0108434****")
    m.set_sender_field("성도커머*", "호실", "301")
    m.set_sender_field("성도커머*", "전화번호", "01098331234")
    m.save()
    m.save()  # 두 번째 저장은 백업을 남긴다
    assert list((tmp_path / "backup").glob("*.xlsx"))

    m2 = Master(tmp_path / "m.xlsx", tmp_path / "backup")
    assert m2.alias_map() == {"김판*": "뉴트리에*"}
    s = settle(df, m2.alias_map(), m2.different_pairs())
    assert {c.other for c in s.candidates} == {"★뉴트리에스*"}

    rows = s.summary_rows(m2.senders)
    sd = [r for r in rows if r.name == "성도커머*"][0]
    assert (sd.room, sd.phone) == ("301", "01098331234")
    out = tmp_path / "out.xlsx"
    write_report(out, s, rows)
    wb = load_workbook(out)
    assert wb.sheetnames == ["정산요약", "상세내역"]
    last = list(wb["정산요약"].iter_rows(values_only=True))[-1]
    assert last[0] == "합계" and last[4] == 93 and last[5] == 179800
    assert wb["상세내역"].max_row == 94


def test_merge_chain_choose_other_as_rep():
    m = Master(Path("nonexistent.xlsx"), Path("."))
    m.record_same("정영*", "뉴트리에*", "")
    m.record_same("뉴트리에*", "★뉴트리에스*", "")
    amap = m.alias_map()
    assert engine.resolve("정영*", amap) == "★뉴트리에스*"
    assert engine.resolve("뉴트리에*", amap) == "★뉴트리에스*"


def test_missing_column(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("운송장번호,운임\n1,100\n", encoding="cp949")
    with pytest.raises(DataError, match="필수 열"):
        engine.load_files([p])


def test_csv_cp949_and_dedupe(df, tmp_path):
    p = tmp_path / "s.csv"
    df.drop(columns=["원본파일"]).head(5).to_csv(p, index=False, encoding="cp949")
    data, dup = engine.load_files([SAMPLE, p])
    assert dup == 5 and len(data) == 93


def test_bad_amount(df):
    bad = df.copy()
    bad.loc[0, "운임"] = "abc"
    with pytest.raises(DataError, match=bad.loc[0, "운송장번호"]):
        settle(bad)


def test_symbol_candidate():
    import pandas as pd
    rows = []
    for i, (n, p) in enumerate([("가나*", "010A"), ("★가나*", "010B")]):
        r = dict.fromkeys(engine.REQUIRED_COLS + engine.OPTIONAL_COLS, "")
        r.update({"운송장번호": str(i), "운임": "100", "지불조건": "발신",
                  "송하인명": n, "송하인전화번호": p, "출고일": "2026-09-01"})
        rows.append(r)
    s = settle(pd.DataFrame(rows))
    assert [(c.base, c.other) for c in s.candidates] == [("가나*", "★가나*")]


def _m():
    return Master(Path("nonexistent.xlsx"), Path("."))


def test_assign_member_moves_alone():
    m = _m()
    m.assign("정영*", "뉴트리에*")
    m.assign("김판*", "뉴트리에*")
    m.assign("정영*", "데이스터*")  # 잘못 묶은 것 재지정
    assert m.alias_map() == {"김판*": "뉴트리에*", "정영*": "데이스터*"}


def test_assign_rep_moves_whole_group():
    m = _m()
    m.assign("정영*", "뉴트리에*")
    m.assign("뉴트리에*", "★뉴트리에스*")
    assert m.alias_map() == {"정영*": "★뉴트리에스*", "뉴트리에*": "★뉴트리에스*"}


def test_split_and_make_rep():
    m = _m()
    m.assign("정영*", "뉴트리에*")
    m.assign("김판*", "뉴트리에*")
    m.make_rep("김판*")
    assert m.alias_map() == {"정영*": "김판*", "뉴트리에*": "김판*"}
    m.split("정영*")
    assert m.alias_map() == {"뉴트리에*": "김판*"}


def test_merge_clears_different_and_undo(df):
    m = _m()
    m.record_different("정영*", "뉴트리에*", "")
    assert frozenset(("정영*", "뉴트리에*")) in m.different_pairs()
    m.assign("정영*", "뉴트리에*")
    assert not m.different_pairs()
    m.split("정영*")
    m.record_different("김판*", "뉴트리에*", "")
    m.undo_different("뉴트리에*", "김판*")
    assert len(settle(df, m.alias_map(), m.different_pairs()).candidates) == 3
