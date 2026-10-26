"""app.order_log 순수 로직 테스트(월 한도 계산, 기록 엑셀)."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from app.order_log import month_usage, parse_order_date, quota_status, write_order_log


class ParseOrderDateTest(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(parse_order_date("261026"), dt.date(2026, 10, 26))
        self.assertEqual(parse_order_date("20261026"), dt.date(2026, 10, 26))
        self.assertEqual(parse_order_date("2026-10-26"), dt.date(2026, 10, 26))
        self.assertIsNone(parse_order_date("261399"))
        self.assertIsNone(parse_order_date(""))


class QuotaTest(unittest.TestCase):
    ROWS = [  # quantity는 박스(1박스=100개)
        {"order_date": "261001", "category": "니들", "quantity": 1},
        {"order_date": "261015", "category": "니들", "quantity": 0.5},
        {"order_date": "260930", "category": "니들", "quantity": 9},  # 지난달
        {"order_date": "261002", "category": "시린지", "quantity": 3},
        {"order_date": "261002", "category": "수액", "quantity": 7},  # 한도 대상 아님
        {"order_date": "261002", "category": None, "quantity": 7},
    ]

    def test_month_usage_counts_pieces_only_that_month_and_categories(self):
        self.assertEqual(month_usage(self.ROWS, 2026, 10), {"니들": 150, "시린지": 300})

    def test_quota_status_includes_current_order(self):
        status = {s["category"]: s for s in quota_status({"니들": 150, "시린지": 300}, {"니들": 300})}
        self.assertEqual(status["니들"]["ordered"], 450)
        self.assertEqual(status["니들"]["remaining"], -50)
        self.assertEqual(status["시린지"]["remaining"], 1100)


class WriteOrderLogTest(unittest.TestCase):
    def test_date_in_front_of_each_line_newest_first(self):
        rows = [
            {"order_id": 1, "order_date": "260914", "category": "니들", "raw_text": "23G needle",
             "quantity": 5, "requirement_text": "일회용니들", "spec_text": "23G", "applied_buy": 100,
             "applied_sell": 200, "remark": ""},
            {"order_id": 2, "order_date": "261026", "category": "시린지", "raw_text": "3cc",
             "quantity": 2, "requirement_text": "주사기", "spec_text": "3cc", "applied_buy": 1,
             "applied_sell": 2, "remark": "급함"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_order_log(rows, Path(tmp) / "log.xlsx")
            wb = load_workbook(path)
            ws = wb["주문기록"]
            self.assertEqual(ws["A1"].value, "주문일자")
            self.assertEqual([c.value for c in ws[2]][:4], ["2026-10-26", "시린지", "3cc", 2])
            self.assertEqual(ws["A3"].value, "2026-09-14")
            summary = wb["월별 한도"]
            # 시린지 2박스 = 200개 → 남은 1200개
            self.assertEqual([c.value for c in summary[2]], ["2026-10", 0, 200, 400, 1200])


if __name__ == "__main__":
    unittest.main()
