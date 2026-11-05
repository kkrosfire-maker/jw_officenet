import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rxmonth


class ParseTest(unittest.TestCase):
    def test_variants_are_the_same_month(self):
        for t in ("8월", "08월", "8", " 08월 ", 8):
            self.assertEqual(rxmonth.parse(t), 8)
        self.assertTrue(rxmonth.same("8월", "08월"))

    def test_unreadable(self):
        for t in (None, "", "월", "13월", "0월", "abc"):
            self.assertIsNone(rxmonth.parse(t))
        self.assertFalse(rxmonth.same("", ""))
        self.assertFalse(rxmonth.same("8월", "9월"))

    def test_label(self):
        self.assertEqual(rxmonth.label(8), "8월")


class DefaultsTest(unittest.TestCase):
    def test_default_month_is_last_month(self):
        self.assertEqual(rxmonth.default_month(datetime.date(2026, 11, 5)), 10)
        self.assertEqual(rxmonth.default_month(datetime.date(2026, 1, 5)), 12)      # 1월이면 작년 12월

    def test_year_for(self):
        today = datetime.date(2026, 2, 10)
        self.assertEqual(rxmonth.year_for(1, today), 2026)
        self.assertEqual(rxmonth.year_for(2, today), 2026)
        self.assertEqual(rxmonth.year_for(12, today), 2025)      # 12월분을 2월에 입력 → 작년


class PeriodTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(rxmonth.period_of(2026, "10월", "11월"), (2026, 10))
        self.assertEqual(rxmonth.period_of(2025, "08월", None), (2025, 8))

    def test_year_column_is_input_year(self):
        """12월분을 2월에 입력 — 연도 열이 입력 연도(2026)로 적혀 있어도 처방은 2025년 12월."""
        self.assertEqual(rxmonth.period_of(2026, "12월", "2월"), (2025, 12))

    def test_unreadable(self):
        self.assertIsNone(rxmonth.period_of("2026", "10월", "11월"))
        self.assertIsNone(rxmonth.period_of(2026, "", "11월"))

    def test_recent_periods_cross_year(self):
        self.assertEqual(rxmonth.recent_periods((2026, 1), 3), {(2026, 1), (2025, 12), (2025, 11)})
        self.assertEqual(rxmonth.recent_periods(None), set())


if __name__ == "__main__":
    unittest.main()
