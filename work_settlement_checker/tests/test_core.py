import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core, deadline_ocr, names, schedule, store
from ledger_read import Row


def rows():
    return [Row("건스", "A의원", "(주)이든파마", ""), Row("건스", "A의원", "(주)이든파마", "입력완료"),
            Row("태사랑", "B내과", "맥널티제약(주)", "입력완료"), Row("태사랑", "B내과", "삼익제약", ""),
            Row("태사랑", "C내과", "대한뉴팜(주)", "")]


class CoreTest(unittest.TestCase):
    def view(self, dls, aliases=None):
        return core.build_view(2026, 11, dls, rows(), aliases or {}, dt.date(2026, 11, 10))

    def test_same_hospital_pharma_lines_merge_and_partial_is_pending(self):
        v = self.view([schedule.Deadline(10, "이든파마", 11)])
        (i,) = v["items"]
        self.assertEqual((i["total"], i["done_n"], i["done"]), (2, 1, False))

    def test_alias_links_different_name(self):
        v = self.view([schedule.Deadline(12, "한국맥널티")], {names.norm("한국맥널티"): "맥널티제약(주)"})
        self.assertEqual(v["items"][0]["pharma"], "맥널티제약(주)")
        self.assertTrue(v["items"][0]["done"])

    def test_unlinked_and_missing_and_notice(self):
        v = self.view([schedule.Deadline(5, "동성제약"), schedule.Deadline(11, "코드등록도 마감", None, True)])
        self.assertEqual([u["name"] for u in v["unlinked"]], ["동성제약"])
        self.assertEqual(len(v["notices"]), 1)
        self.assertIn("삼익제약", [m["pharma"] for m in v["missing"]])      # 마감일 못 찾은 제약사

    def test_summary_overdue_and_today(self):
        v = self.view([schedule.Deadline(6, "삼익제약"), schedule.Deadline(10, "대한뉴팜"), schedule.Deadline(13, "이든파마")])
        s = v["summary"]
        self.assertEqual((s["overdue"], s["today"], s["pending"], s["done"]), (1, 1, 3, 0))

    def test_ocr_typo_is_fixed_but_other_names_not_merged(self):
        book = names.NameBook.from_names(["(주)팜젠사이언스", "파마사이언스코리아(주)"])
        self.assertEqual(schedule.resolve("팡젠사이언스", book)[1], "fixed")
        self.assertEqual(schedule.resolve("한국파마", book)[0], None)

    def test_last_day_is_latest_deadline_including_notice(self):
        v = self.view([schedule.Deadline(5, "삼익제약"), schedule.Deadline(13, "코드등록도 마감", None, True)])
        self.assertEqual(v["last_day"], 13)
        self.assertIsNone(self.view([])["last_day"])

    def test_entry_parsing(self):
        e = deadline_ocr.Entry(5, "국제약품(11시)")
        self.assertEqual((e.name, e.hour, e.is_notice), ("국제약품", 11, False))
        e = deadline_ocr.Entry(5, "- 코드등록도 마감")
        self.assertTrue(e.is_notice)
        self.assertEqual(deadline_ocr.Entry(5, "경보제약(오전까지)").hour, 12)

    def test_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["SETTLEMENT_CHECKER_DIR"] = d
            store.save_month(2026, 11, [schedule.Deadline(5, "영진약품", 11)])
            self.assertEqual(store.load_month(2026, 11)[0].hour, 11)
            self.assertEqual(store.saved_months(), [(2026, 11)])


if __name__ == "__main__":
    unittest.main()
