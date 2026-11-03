import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from names import NameBook, clean_pharma, memo_key, norm, same


class NormTest(unittest.TestCase):
    def test_ignores_company_marks_spaces_symbols(self):
        for a in ("(주)이든파마", "이든파마(주)", "이든파마㈜", "주식회사 이든파마", " 이든 파마 ", "이든-파마"):
            self.assertEqual(norm(a), "이든파마", a)

    def test_lowercase_and_digits_kept(self):
        self.assertEqual(norm("SD파마 2"), "sd파마2")

    def test_same(self):
        self.assertTrue(same("명문제약(주)", "명문제약"))
        self.assertFalse(same("명문제약", "명문약품"))
        self.assertFalse(same("", ""))

    def test_clean_pharma_strips_trailing_count_only(self):
        self.assertEqual(clean_pharma("명문제약 (2)"), "명문제약")
        self.assertEqual(clean_pharma("명문제약2"), "명문제약")
        self.assertEqual(clean_pharma("(주)이든파마"), "(주)이든파마")

    def test_memo_key_same_for_spelling_variants(self):
        self.assertEqual(memo_key("다솜의원", "안국뉴팜(주)"), memo_key(" 다솜의원 ", "안국뉴팜"))


class NameBookTest(unittest.TestCase):
    def setUp(self):
        # 오래된 것 -> 최근 순: 최근 표기는 '(주)이든파마', '명문제약(주)'
        self.book = NameBook.from_names(["이든파마", "명문제약", "(주)이든파마", "코오롱제약", "명문제약(주)"])

    def test_display_uses_latest_spelling(self):
        self.assertEqual(self.book.display("이든파마"), "(주)이든파마")
        self.assertEqual(self.book.display("명문제약"), "명문제약(주)")

    def test_display_prefers_users_recent_choice(self):
        self.assertEqual(self.book.display("이든파마", prefer={norm("이든파마"): "이든파마(주)"}), "이든파마(주)")

    def test_display_unknown_name_unchanged(self):
        self.assertEqual(self.book.display("새제약"), "새제약")

    def test_dedupe_keeps_one_per_group_in_order(self):
        names = ["이든파마", "코오롱제약", "(주)이든파마", "명문제약", "명문제약(주)"]
        self.assertEqual(self.book.dedupe(names), ["(주)이든파마", "코오롱제약", "명문제약(주)"])

    def test_dedupe_sort_gananda_order(self):
        book = NameBook()
        out = book.dedupe(["(주)다산제약", "나래제약", "가나제약(주)", "㈜라이트팜텍"], sort=True)
        self.assertEqual(out, ["가나제약(주)", "나래제약", "(주)다산제약", "㈜라이트팜텍"])

    def test_dedupe_drop_norms(self):
        out = self.book.dedupe(["이든파마", "코오롱제약"], drop_norms={norm("이든파마")})
        self.assertEqual(out, ["코오롱제약"])

    def test_closest_finds_similar_name(self):
        name, score = self.book.closest("코오롱제얀")
        self.assertEqual(name, "코오롱제약")
        self.assertGreaterEqual(score, 0.6)

    def test_closest_none_when_nothing_similar(self):
        self.assertEqual(self.book.closest("인성배"), (None, 0.0))

    def test_closest_too_short_input(self):
        self.assertEqual(self.book.closest("이"), (None, 0.0))

    def test_closest_favored_breaks_tie(self):
        book = NameBook.from_names(["대한가약", "대한나약"])      # '대한다약'과 똑같이 닮은 두 이름
        name, _ = book.closest("대한다약", favored_norms={norm("대한나약")})
        self.assertEqual(name, "대한나약")


if __name__ == "__main__":
    unittest.main()
