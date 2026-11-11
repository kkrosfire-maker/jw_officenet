import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core, ledger_read, ledger_write

HEAD = ["연도", "담당자명", None, "거래처명", "처방월", "입력월", "제약사명", "통합", None, "특이사항"]


def make(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "통계입력확인"
    ws.append(HEAD)
    for r in rows:
        ws.append(r)
    wb.save(path)


class CarryOverTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.p = Path(self.d.name) / "w.xlsx"
        make(self.p, [
            [2026, "건스", None, "A의원", "10월", "11월", "(주)이든파마", None, None, None],
            [2026, "건스", "입력완료", "A의원", "10월", "11월", "(주)이든파마", None, 1, None],
            [2026, "건스", None, "A의원", "10월", "11월", "삼익제약", None, None, "기존 메모"],
            [2026, "태사랑", None, "B내과", "10월", "11월", "(주)이든파마", None, None, None],
            [2026, "건스", None, "A의원", "09월", "12월", "(주)이든파마", None, None, None],
        ])

    def tearDown(self):
        self.d.cleanup()

    def cells(self):
        ws = openpyxl.load_workbook(self.p)["통계입력확인"]
        return [[c.value for c in row] for row in ws.iter_rows(min_row=2)]

    def test_only_unfinished_rows_of_same_manager_hospital_pharma_and_month(self):
        n = ledger_write.carry_over(self.p, 11, "건스", "A의원", "이든파마")
        self.assertEqual(n, 1)
        r = self.cells()
        self.assertEqual((r[0][2], r[0][8], r[0][9]), ("통계이월", 1, "10월 통계 다음달로 이월"))
        self.assertEqual(r[1][2], "입력완료")                       # 이미 처리된 줄은 그대로
        self.assertIsNone(r[3][2])                                  # 다른 담당자 줄
        self.assertIsNone(r[4][2])                                  # 다른 입력월(12월) 줄

    def test_existing_note_is_kept_and_not_duplicated(self):
        ledger_write.carry_over(self.p, 11, "건스", "A의원", "삼익제약")
        self.assertEqual(self.cells()[2][9], "기존 메모 / 10월 통계 다음달로 이월")
        self.assertEqual(ledger_write.carry_over(self.p, 11, "건스", "A의원", "삼익제약"), 0)   # 두 번째는 이미 처리됨

    def test_carried_rows_count_as_done_in_view(self):
        ledger_write.carry_over(self.p, 11, "건스", "A의원", "이든파마")
        rows = ledger_read.read_rows(self.p, 11)
        self.assertTrue(all(r.done for r in rows if r.hospital == "A의원" and "이든" in r.pharma))
        import schedule
        v = core.build_view(2026, 11, [schedule.Deadline(10, "이든파마")], rows, {}, dt.date(2026, 11, 10))
        a = [i for i in v["items"] if i["hospital"] == "A의원"][0]
        self.assertEqual((a["done"], a["carried_n"], a["total"]), (True, 1, 2))

    def test_no_match_writes_nothing(self):
        before = self.p.read_bytes()
        self.assertEqual(ledger_write.carry_over(self.p, 11, "건스", "없는의원", "이든파마"), 0)
        self.assertEqual(self.p.read_bytes(), before)

    def test_month_label(self):
        self.assertEqual(ledger_write.month_label("08월", "11월"), "8월")
        self.assertEqual(ledger_write.month_label("", "1월"), "12월")


if __name__ == "__main__":
    unittest.main()
