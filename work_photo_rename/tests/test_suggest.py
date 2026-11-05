import os
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ledger
import suggest
from ledger import MasterExcel

HEADER = ["연도", "담당자명", None, "거래처명", "처방월", "입력월", "제약사명", "통합", None, "특이사항"]
ROWS = [  # 연도, 병원, 처방월, 입력월, 제약사
    (2026, "다솜의원", "10월", "11월", "명문제약"),
    (2026, "다솜의원", "10월", "11월", "안국뉴팜(주)"),
    (2026, "다솜의원", "08월", "09월", "대웅바이오"),           # '08월' 표기 — 최근 3개월 안
    (2025, "다솜의원", "10월", None, "작년시월제약"),          # 작년 같은 달 — 10월을 골라도 후보에 나오면 안 된다
    (2025, "다솜의원", "06월", None, "옛날제약"),               # 몇 달 전 한 번 — 후보에서 빠져야 한다
    (2026, "가온의원", "9월", "10월", "코오롱제약"),
    (2026, "가온의원", "10월", "11월", "코오롱제약"),
    (2026, "혼자의원", "10월", "11월", "단독제약"),
    (2026, "경보병원", "10월", "11월", "경보제약"),
    (2026, "경동병원", "10월", "11월", "경동제약"),
]


class SuggestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        path = Path(cls.dir.name) / "base.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = ledger.SHEET
        ws.append(HEADER)
        for y, h, rx, im, ph in ROWS:
            ws.append([y, "담당", None, h, rx, im, ph, None, None, None])
        wb.save(path)
        cls.m = MasterExcel(str(path))

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    # candidates
    def test_primary_is_recent_three_months_only(self):
        primary, secondary = suggest.candidates(self.m, "다솜의원", "10월")
        self.assertEqual(sorted(primary), sorted(["명문제약", "안국뉴팜(주)", "대웅바이오"]))
        self.assertNotIn("옛날제약", primary)

    def test_same_month_of_last_year_is_not_primary(self):
        primary, secondary = suggest.candidates(self.m, "다솜의원", "10월")
        self.assertNotIn("작년시월제약", primary)
        self.assertIn("작년시월제약", secondary)

    def test_other_pharmas_are_secondary_not_primary(self):
        primary, secondary = suggest.candidates(self.m, "다솜의원", "10월")
        self.assertIn("옛날제약", secondary)           # 새 제약사 대비로 찾을 수는 있다
        self.assertIn("코오롱제약", secondary)
        self.assertFalse(set(primary) & set(secondary))

    def test_unknown_hospital_gets_everything_as_primary(self):
        primary, secondary = suggest.candidates(self.m, "새병원", "10월")
        self.assertIn("옛날제약", primary)
        self.assertIn("코오롱제약", primary)
        self.assertEqual(secondary, [])

    def test_prefer_spelling(self):
        primary, _ = suggest.candidates(self.m, "다솜의원", "10월", {"안국뉴팜": "(주)안국뉴팜"})
        self.assertIn("(주)안국뉴팜", primary)

    def test_hidden_pharma_is_not_a_candidate(self):
        self.m.hidden = frozenset({ledger.memo_key("다솜의원", "명문제약")})
        try:
            primary, _ = suggest.candidates(self.m, "다솜의원", "10월")
            self.assertNotIn("명문제약", primary)
        finally:
            self.m.hidden = frozenset()

    # autofill
    def test_autofill_from_photo_text(self):
        self.assertEqual(suggest.autofill(self.m, "다솜의원", "", "명문제얍"), "명문제약")

    def test_autofill_keeps_what_user_typed(self):
        self.assertIsNone(suggest.autofill(self.m, "다솜의원", "직접입력", "명문제약"))

    def test_autofill_needs_text(self):
        self.assertIsNone(suggest.autofill(self.m, "다솜의원", "", None))
        self.assertIsNone(suggest.autofill(self.m, "다솜의원", "", ""))

    def test_autofill_nothing_similar(self):
        self.assertIsNone(suggest.autofill(self.m, "다솜의원", "", "zzzzqqqq"))

    def test_autofill_prefers_this_hospitals_pharma_when_tied(self):
        # 경동제약 / 경보제약은 서로 비슷하다 — 같은 글자라도 그 병원 쪽을 먼저 고른다
        self.assertEqual(suggest.autofill(self.m, "경보병원", "", "경제약"), "경보제약")
        self.assertEqual(suggest.autofill(self.m, "경동병원", "", "경제약"), "경동제약")

    # sole_pharma
    def test_sole_pharma(self):
        self.assertEqual(suggest.sole_pharma(self.m, "혼자의원", "10월", 2026), "단독제약")

    def test_sole_pharma_not_when_several_or_filled(self):
        self.assertIsNone(suggest.sole_pharma(self.m, "다솜의원", "10월", 2026))
        self.assertIsNone(suggest.sole_pharma(self.m, "혼자의원", "10월", 2026, current="이미입력"))

    def test_sole_pharma_matches_month_spelling(self):
        self.assertEqual(suggest.sole_pharma(self.m, "다솜의원", "8월", 2026), "대웅바이오")      # 엑셀엔 '08월'


if __name__ == "__main__":
    unittest.main()
