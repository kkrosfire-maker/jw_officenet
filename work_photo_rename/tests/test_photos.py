import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from photos import Photo, PhotoBook

OCT = ((2026, 10, 1), (2026, 10, 31))
SEP = ((2026, 9, 1), (2026, 9, 30))


class RecordTest(unittest.TestCase):
    def test_new_photo_is_blank_and_not_opened(self):
        ph = PhotoBook().get("a.png")
        self.assertEqual((ph.hospital, ph.pharma, ph.rects, ph.opened, ph.period_read), ("", "", [], False, False))

    def test_record_marks_opened_and_copies_rects(self):
        book, rects = PhotoBook(), [{"cx": 1}]
        book.record("a.png", "다솜의원", "명문제약", rects)
        rects.append({"cx": 2})                      # 나중에 원본을 바꿔도 기록은 그대로
        ph = book.get("a.png")
        self.assertEqual((ph.hospital, ph.pharma, ph.opened), ("다솜의원", "명문제약", True))
        self.assertEqual(ph.rects, [{"cx": 1}])

    def test_ocr_results_do_not_mark_opened(self):
        book = PhotoBook()
        book.set_period("a.png", OCT)
        book.set_ocr_pharma("a.png", "명문제약")
        ph = book.get("a.png")
        self.assertFalse(ph.opened)                  # 처음 여는 사진(파일명으로 병원 추측)이 유지된다
        self.assertEqual((ph.period, ph.period_read, ph.ocr_pharma), (OCT, True, "명문제약"))


class ReadyTest(unittest.TestCase):
    def test_ready_needs_both_names_not_blank(self):
        book = PhotoBook()
        for hospital, pharma, expected in (("다솜의원", "명문제약", True), ("다솜의원", "", False),
                                           ("", "명문제약", False), ("  ", "명문제약", False),
                                           ("다솜의원", "   ", False)):
            book.record("a.png", hospital, pharma, [])
            self.assertEqual(book.is_ready("a.png"), expected, (hospital, pharma))

    def test_unknown_path_not_ready_and_not_created(self):
        book = PhotoBook()
        self.assertFalse(book.is_ready("none.png"))
        self.assertFalse(Photo("x").ready)

    def test_boxes_not_required(self):
        book = PhotoBook()
        book.record("a.png", "다솜의원", "명문제약", [])
        self.assertTrue(book.is_ready("a.png"))


class PlanSaveTest(unittest.TestCase):
    def test_split_into_todo_and_skipped_keeping_order(self):
        book = PhotoBook()
        book.record("C:/x/b.png", "병원B", "제약B", [])
        book.record("C:/x/a.png", "병원A", "", [])
        book.record("C:/x/c.png", "병원C", "제약C", [])
        todo, skipped = book.plan_save(["C:/x/b.png", "C:/x/a.png", "C:/x/c.png", "C:/x/never.png"])
        self.assertEqual([p.path for p in todo], ["C:/x/b.png", "C:/x/c.png"])
        self.assertEqual(skipped, ["a.png", "never.png"])


class PeriodTest(unittest.TestCase):
    def test_status_none_until_ocr_done(self):
        book = PhotoBook()
        book.record("a.png", "병원", "제약", [])
        self.assertIsNone(book.period_status("a.png", 2026, 10))
        self.assertIsNone(book.period_status("zzz.png", 2026, 10))

    def test_status_ok_and_bad(self):
        book = PhotoBook()
        book.set_period("a.png", OCT)
        book.set_period("b.png", SEP)
        self.assertTrue(book.period_status("a.png", 2026, 10)[0])
        self.assertFalse(book.period_status("b.png", 2026, 10)[0])

    def test_unreadable_period_is_a_problem(self):
        book = PhotoBook()
        book.set_period("a.png", None)               # OCR이 끝났지만 날짜를 못 읽음
        self.assertFalse(book.period_status("a.png", 2026, 10)[0])

    def test_period_problems_lists_only_read_and_mismatching(self):
        book = PhotoBook()
        for name, period in (("C:/x/ok.png", OCT), ("C:/x/sep.png", SEP), ("C:/x/blur.png", None)):
            book.record(name, "병원", "제약", [])
            book.set_period(name, period)
        book.record("C:/x/pending.png", "병원", "제약", [])      # OCR 아직 -> 문제로 치지 않음
        photos, _ = book.plan_save(["C:/x/ok.png", "C:/x/sep.png", "C:/x/blur.png", "C:/x/pending.png"])
        self.assertEqual(book.period_problems(photos, 2026, 10), ["sep.png", "blur.png"])
        self.assertEqual(book.period_problems(photos, 2026, 9), ["ok.png", "blur.png"])


class DonePharmasTest(unittest.TestCase):
    def setUp(self):
        self.book = PhotoBook()
        self.book.record("1.png", "다솜의원", "명문제약(주)", [])
        self.book.record("2.png", "다솜의원", "안국뉴팜", [])
        self.book.record("3.png", "가온의원", "코오롱제약", [])
        self.book.record("4.png", "다솜의원", "", [])

    def test_only_checked_photos_of_same_hospital(self):
        self.assertEqual(self.book.pharma_norms_done("다솜의원", {"1.png", "3.png", "4.png"}), {"명문제약"})

    def test_spelling_variants_of_hospital_and_pharma_match(self):
        self.assertEqual(self.book.pharma_norms_done(" 다솜의원 ", {"1.png", "2.png"}), {"명문제약", "안국뉴팜"})

    def test_empty_hospital_or_nothing_checked(self):
        self.assertEqual(self.book.pharma_norms_done("", {"1.png"}), set())
        self.assertEqual(self.book.pharma_norms_done("다솜의원", set()), set())


if __name__ == "__main__":
    unittest.main()


class CopyOriginalTest(unittest.TestCase):
    def test_make_copy_numbers_and_keeps_extension(self):
        import tempfile
        from pathlib import Path
        from imageio_utils import make_copy
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "원본 10월.png"
            src.write_bytes(b"x")
            dest = Path(d) / "복사"
            a = make_copy(src, dest)
            b = make_copy(src, dest)
            c = make_copy(a, dest, taken=[a, b])                  # 복사본의 복사본도 번호만 올라간다
            self.assertEqual([Path(p).name for p in (a, b, c)],
                             ["원본 10월 (복사1).png", "원본 10월 (복사2).png", "원본 10월 (복사3).png"])
            self.assertEqual(Path(c).read_bytes(), b"x")
            self.assertTrue(src.exists())                        # 원본은 그대로

    def test_copy_record_keeps_hospital_and_period_only(self):
        book = PhotoBook()
        book.record("a.png", "다솜의원", "명문제약", [{"cx": 1}])
        book.set_period("a.png", ((2026, 10, 1), (2026, 10, 31)))
        book.set_ocr_pharma("a.png", "명문제약")
        d = book.copy_of("a.png", "a (복사1).png")
        self.assertEqual((d.hospital, d.pharma, d.rects, d.ocr_pharma), ("다솜의원", "", [], None))
        self.assertTrue(d.period_read and d.opened)


class MonthPerPhotoTest(unittest.TestCase):
    def test_month_is_kept_per_photo(self):
        book = PhotoBook()
        book.record("a.png", "다솜의원", "명문제약", [], "9월")
        book.record("b.png", "다솜의원", "안국뉴팜", [], "10월")
        self.assertEqual((book.get("a.png").month, book.get("b.png").month), ("9월", "10월"))
        book.record("a.png", "다솜의원", "명문제약", [])           # 월을 안 주면 기존 값 유지
        self.assertEqual(book.get("a.png").month, "9월")
        self.assertEqual(book.copy_of("a.png", "a2.png").month, "9월")

    def test_period_problems_uses_each_photos_own_month(self):
        book = PhotoBook()
        for p, m in (("a.png", "9월"), ("b.png", "10월")):
            book.record(p, "다솜의원", "명문제약", [], m)
            book.set_period(p, ((2026, 10, 1), (2026, 10, 31)))     # 둘 다 10월 통계
        photos, _ = book.plan_save(["a.png", "b.png"])
        self.assertEqual(book.period_problems(photos, lambda ph: (2026, int(ph.month[:-1]))), ["a.png"])
