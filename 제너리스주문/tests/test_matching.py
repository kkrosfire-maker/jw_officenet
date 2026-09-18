"""app.matching의 순수 로직 테스트 (DB 접근 없이 동작하는 부분만)."""
import unittest

from app.matching import Candidate, classify_match_type


def make_candidate(item_id, score, alias="alias"):
    return Candidate(item={"id": item_id}, matched_alias=alias, score=score)


class ClassifyMatchTypeTest(unittest.TestCase):
    def test_top_candidate_above_threshold_is_auto_confirmed(self):
        candidates = [make_candidate(1, 0.95), make_candidate(2, 0.5)]
        self.assertEqual(classify_match_type(candidates, chosen_item_id=1), "자동확인")

    def test_top_candidate_below_threshold_is_manual(self):
        candidates = [make_candidate(1, 0.8), make_candidate(2, 0.5)]
        self.assertEqual(classify_match_type(candidates, chosen_item_id=1), "수동선택")

    def test_choosing_non_top_candidate_is_manual_even_if_scored_high(self):
        candidates = [make_candidate(1, 0.95), make_candidate(2, 0.93)]
        self.assertEqual(classify_match_type(candidates, chosen_item_id=2), "수동선택")

    def test_empty_candidates_is_manual(self):
        self.assertEqual(classify_match_type([], chosen_item_id=1), "수동선택")


if __name__ == "__main__":
    unittest.main()
