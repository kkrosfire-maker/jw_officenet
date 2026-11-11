import os
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import store


def make(path, input_month="12월"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "통계입력확인"
    ws.append(["연도", "담당자명", None, "거래처명", "처방월", "입력월", "제약사명", "통합", None, "특이사항"])
    ws.append([2026, "건스", None, "A의원", "11월", input_month, "삼익제약", None, None, None])
    wb.save(path)


class SetWorkFileTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        os.environ["SETTLEMENT_CHECKER_DIR"] = str(Path(self.d.name) / "data")     # 실제 설정 파일을 건드리지 않는다
        import app
        self.api = app.Api()
        self.dir = Path(self.d.name)

    def tearDown(self):
        os.environ.pop("SETTLEMENT_CHECKER_DIR", None)
        self.d.cleanup()

    def test_month_comes_from_file_name_and_is_remembered(self):
        p = self.dir / "1.통계입력_2612.xlsx"
        make(p)
        r = self.api.set_work_file(str(p), 2026, 11)          # 화면은 11월이지만 파일명이 12월
        self.assertEqual((r["ok"], r["year"], r["month"], r["count"]), (True, 2026, 12, 1))
        self.assertEqual(store.load_config()["work_2612"], str(p))
        self.assertEqual(str(self.api._work_file(2026, 12)), str(p))

    def test_name_without_month_uses_open_month(self):
        p = self.dir / "다른이름.xlsx"
        make(p)
        self.api._cur = (2026, 12)
        r = self.api.set_work_file(str(p))
        self.assertEqual((r["ok"], r["month"]), (True, 12))

    def test_rejects_non_excel_and_wrong_month_and_unreadable(self):
        t = self.dir / "a.txt"
        t.write_text("x")
        self.assertFalse(self.api.set_work_file(str(t), 2026, 11)["ok"])
        p = self.dir / "1.통계입력_2611.xlsx"
        make(p, "12월")                                         # 11월 줄이 없는 파일
        self.assertFalse(self.api.set_work_file(str(p))["ok"])
        bad = self.dir / "1.통계입력_2610.xlsx"
        bad.write_bytes(b"not excel")
        self.assertFalse(self.api.set_work_file(str(bad))["ok"])
        self.assertEqual(store.load_config(), {})               # 실패하면 아무것도 저장하지 않는다


if __name__ == "__main__":
    unittest.main()
