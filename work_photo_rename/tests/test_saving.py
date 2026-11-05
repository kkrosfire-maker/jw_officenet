import datetime
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import labeling
import ledger
import saving
from ledger import Ledger
from settings import Settings
from tests.test_ledger import make_book, sheet

TODAY = datetime.date(2026, 11, 5)
IMG = np.full((600, 1000, 3), 200, np.uint8)
RECT = [{"cx": 500, "cy": 300, "hw": 200, "hh": 60, "angle": 0.0, "thickness": 4}]


def read_jpg(path):
    return cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)


class NumberedPathTest(unittest.TestCase):
    def test_numbers_follow_the_name_without_a_space(self):
        with tempfile.TemporaryDirectory() as d:
            first = labeling.numbered_path(d, "다솜의원 10월 이든파마")
            self.assertEqual(first.name, "다솜의원 10월 이든파마.jpg")
            first.write_bytes(b"x")
            second = labeling.numbered_path(d, "다솜의원 10월 이든파마")
            self.assertEqual(second.name, "다솜의원 10월 이든파마2.jpg")
            second.write_bytes(b"x")
            self.assertEqual(labeling.numbered_path(d, "다솜의원 10월 이든파마").name, "다솜의원 10월 이든파마3.jpg")
            for i in range(3, 10):
                labeling.numbered_path(d, "다솜의원 10월 이든파마").write_bytes(b"x")
            self.assertEqual(labeling.numbered_path(d, "다솜의원 10월 이든파마").name, "다솜의원 10월 이든파마10.jpg")


class SavePhotoTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.base = self.dir / "기본파일.xlsx"
        make_book(self.base)
        self.out = self.dir / "out"
        self.settings = Settings(self.dir / "cfg" / "config.json")
        self.ledger = Ledger(self.base)
        self.ledger.hidden = self.settings.hidden
        self.ledger.load()

    def tearDown(self):
        self.ledger.wait()
        self._tmp.cleanup()

    def _wait(self):
        t = time.time()
        while self.ledger.pending and time.time() - t < 30:
            self.ledger.poll()
            time.sleep(0.05)
        self.ledger.poll()

    def _save(self, pharma="신규제약", status=ledger.DONE, source="a.png", month="10월"):
        return saving.save_photo(IMG, source, "다솜의원", pharma, RECT, month, out_dir=self.out,
                                 ledger=self.ledger, settings=self.settings, status=status, today=TODAY)

    def test_saves_jpg_2500_wide_with_label_band(self):
        res = self._save()
        self.assertEqual(res.path.name, "다솜의원 10월 신규제약.jpg")
        img = read_jpg(res.path)
        self.assertEqual(img.shape[1], labeling.TARGET_W)
        self.assertEqual(img.shape[0], round(600 * 2500 / 1000) + labeling.BAND_H)
        self._wait()

    def test_second_save_of_same_label_gets_number_without_space(self):
        self._save(source="a.png")
        res = self._save(source="b.png")
        self.assertEqual(res.path.name, "다솜의원 10월 신규제약2.jpg")
        self._wait()

    def test_remembers_recent_spelling(self):
        self._save(pharma="(주)신규제약")
        self.assertEqual(Settings(self.settings.path).recent_pharma, {"신규제약": "(주)신규제약"})
        self._wait()

    def test_records_in_work_excel_and_history(self):
        res = self._save()
        self.assertEqual(res.excel, "엑셀 반영 중…")
        self._wait()
        work = self.out / "1.통계입력_2611.xlsx"                        # 오늘(2026-11) 기준 이름
        self.assertTrue(work.exists())
        self.assertIn("신규제약", self.ledger.master.all_pharmas())
        ws = sheet(work)
        rows = [[c.value for c in r] for r in ws.iter_rows(min_row=2)]
        new = [r for r in rows if r[6] == "신규제약"][0]
        self.assertEqual((new[0], new[2], new[3], new[4], new[5]), (2026, "입력완료", "다솜의원", "10월", "11월"))

    def test_same_photo_same_name_is_not_recorded_twice(self):
        self._save()
        self._wait()
        self.assertEqual(self._save().excel, "엑셀: 이미 반영됨")
        self._wait()

    def test_no_settlement_stamps_photo_and_marks_status(self):
        plain = read_jpg(self._save(pharma="가제약", source="a.png").path)
        stamped = read_jpg(self._save(pharma="나제약", source="b.png", status=ledger.NOSETTLE).path)
        h, w = plain.shape[0] - labeling.BAND_H, plain.shape[1]
        centre = (slice(h // 2 - 40, h // 2 + 40), slice(w // 2 - 200, w // 2 + 200))
        red = lambda im: int(((im[centre][..., 2] > 200) & (im[centre][..., 1] < 80) & (im[centre][..., 0] < 80)).sum())
        self.assertGreater(red(stamped), red(plain) + 500)           # 가운데에 빨간 도장
        self._wait()
        ws = sheet(self.out / "1.통계입력_2611.xlsx")
        status = {r[6].value: r[2].value for r in ws.iter_rows(min_row=2) if r[6].value in ("가제약", "나제약")}
        self.assertEqual(status, {"가제약": "입력완료", "나제약": "정산불가"})

    def test_hidden_pharma_returns_after_saving_it_again(self):
        self.settings.hide_pharma("다솜의원", "명문제약")
        self.assertNotIn("명문제약", self.ledger.master.hospital_pharmas("다솜의원"))
        self._save(pharma="명문제약")
        self._wait()
        self.assertEqual(Settings(self.settings.path).hidden, set())
        self.assertIn("명문제약", self.ledger.master.hospital_pharmas("다솜의원"))

    def test_december_prescription_in_february_uses_previous_year(self):
        saving.save_photo(IMG, "a.png", "다솜의원", "신규제약", RECT, "12월", out_dir=self.out, ledger=self.ledger,
                          settings=self.settings, today=datetime.date(2027, 2, 3))
        self._wait()
        ws = sheet(self.out / "1.통계입력_2702.xlsx")
        row = [[c.value for c in r] for r in ws.iter_rows(min_row=2) if r[6].value == "신규제약"][0]
        self.assertEqual((row[0], row[4], row[5]), (2026, "12월", "2월"))

    def test_without_master_still_saves_jpg(self):
        lg = Ledger(self.dir / "없는파일.xlsx")                       # 엑셀을 못 읽은 상태
        res = saving.save_photo(IMG, "a.png", "다솜의원", "신규제약", RECT, "10월", out_dir=self.out,
                                ledger=lg, settings=self.settings, today=TODAY)
        self.assertTrue(res.path.exists())
        self.assertEqual(res.excel, "엑셀 미연결")


class WorkExcelPathTest(unittest.TestCase):
    def test_none_without_folder(self):
        self.assertIsNone(ledger.work_excel_path(None))

    def test_new_name_and_old_name_migrated(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.assertEqual(ledger.work_excel_path(d, TODAY), d / "1.통계입력_2611.xlsx")
            (d / "통계입력_2611.xlsx").write_bytes(b"x")
            self.assertEqual(ledger.work_excel_path(d, TODAY), d / "1.통계입력_2611.xlsx")
            self.assertTrue((d / "1.통계입력_2611.xlsx").exists())
            self.assertFalse((d / "통계입력_2611.xlsx").exists())


if __name__ == "__main__":
    unittest.main()
