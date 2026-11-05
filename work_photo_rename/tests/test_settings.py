import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings import MemoStore, Settings


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "sub" / "config.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_or_broken_file_is_empty(self):
        s = Settings(self.path)
        self.assertIsNone(s.out_dir)
        self.assertEqual(s.recent_pharma, {})
        self.assertEqual(s.hidden, set())
        self.path.parent.mkdir()
        self.path.write_text("{깨진", encoding="utf-8")
        self.assertIsNone(Settings(self.path).out_dir)

    def test_out_dir_survives_restart(self):
        Settings(self.path).set_out_dir(r"C:\통계\10월")
        self.assertEqual(Settings(self.path).out_dir, Path(r"C:\통계\10월"))

    def test_remember_pharma_by_normalized_name(self):
        s = Settings(self.path)
        s.remember_pharma("(주)이든파마")
        s.remember_pharma("   ")
        again = Settings(self.path)
        self.assertEqual(again.recent_pharma, {"이든파마": "(주)이든파마"})

    def test_hide_and_unhide(self):
        s = Settings(self.path)
        s.hide_pharma("다솜의원", "(주)이든파마")
        self.assertTrue(Settings(self.path).hidden)                        # 파일에 남는다
        self.assertTrue(s.unhide_pharma("다솜의원", "이든파마"))             # 표기가 달라도 같은 제약사
        self.assertFalse(s.unhide_pharma("다솜의원", "이든파마"))            # 이미 복귀 — 할 일 없음
        self.assertEqual(Settings(self.path).hidden, set())

    def test_hidden_set_is_shared_object(self):
        """Ledger.hidden 과 같은 집합을 쓰므로, 한쪽에서 바꾸면 다른 쪽에도 보인다."""
        s = Settings(self.path)
        other = s.hidden
        s.hide_pharma("가온의원", "코오롱제약")
        self.assertEqual(len(other), 1)

    def test_unknown_keys_are_kept(self):
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({"기타": 1}), encoding="utf-8")
        s = Settings(self.path)
        s.set_out_dir("X")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["기타"], 1)


class MemoStoreTest(unittest.TestCase):
    def test_memo_roundtrip_same_pharma_different_spelling(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "x" / "메모.json"
            MemoStore(path).set("다솜의원", "(주)이든파마", "정산불가 품목")
            data = MemoStore(path).data
            self.assertEqual(list(data.values()), ["정산불가 품목"])
            from names import memo_key
            self.assertEqual(data[memo_key("다솜의원", "이든파마")], "정산불가 품목")

    def test_write_failure_raises(self):
        with tempfile.TemporaryDirectory() as d:
            blocker = Path(d) / "file"
            blocker.write_text("x")
            with self.assertRaises(OSError):
                MemoStore(blocker / "메모.json").set("a", "b", "c")


if __name__ == "__main__":
    unittest.main()
