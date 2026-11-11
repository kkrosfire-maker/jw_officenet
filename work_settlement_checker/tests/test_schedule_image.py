import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deadline_ocr, store, title_render

FONT = r"C:\Windows\Fonts\malgunbd.ttf"


def fake_schedule(path, who="지에스파마"):
    """엑셀 캡처처럼 생긴 가짜 마감표: 제목 칸 + 요일 줄 + 날짜 줄 + 세로 격자(안쪽 6줄) + 바깥 굵은 테두리."""
    W, H = 1000, 520
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([10, 20, W - 10, 80], outline="black", width=2)                       # 제목 칸
    f = ImageFont.truetype(FONT, 30)
    t = f"2026년 11월 {who} 제약사 통계 마감일정"
    d.text(((W - f.getlength(t)) / 2, 30), t, font=f, fill="black")
    fill = (255, 242, 204)
    for y0, y1 in ((100, 126), (132, 158)):                                           # 요일 줄, 날짜 줄(연노랑)
        d.rectangle([10, y0, W - 10, y1], fill=fill)
    for x in (150, 290, 430, 570, 710, 850):
        d.line([x, 96, x, 500], fill="black", width=2)
    d.line([8, 96, 8, 500], fill="black", width=3)                                    # 바깥 테두리(칸 경계로 안 잡혀야 함)
    d.line([W - 8, 96, W - 8, 500], fill="black", width=3)
    im.save(path)
    return W, H


@unittest.skipUnless(Path(FONT).exists(), "맑은 고딕 굵게 글꼴이 없는 PC")
class TitleRenderTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.src = Path(self.d.name) / "원본.png"
        fake_schedule(self.src)

    def tearDown(self):
        self.d.cleanup()

    def test_title_text_replaced_keeping_position_and_everything_else(self):
        import cv2
        before = deadline_ocr.title_box(cv2.imdecode(np.fromfile(str(self.src), dtype=np.uint8), cv2.IMREAD_COLOR))
        self.assertIsNotNone(before)
        out = title_render.render(self.src, 2026, 11)
        out_path = Path(self.d.name) / "out.png"
        out.save(out_path)
        after = deadline_ocr.title_box(cv2.imdecode(np.fromfile(str(out_path), dtype=np.uint8), cv2.IMREAD_COLOR))
        self.assertIsNotNone(after)
        self.assertGreater(after["x1"] - after["x0"], before["x1"] - before["x0"])      # '정원유니어스(주)'가 더 길다
        self.assertLess(abs((after["x0"] + after["x1"]) - (before["x0"] + before["x1"])), 6)   # 가운데 정렬 유지
        self.assertLess(abs(after["y0"] - before["y0"]), 4)                              # 같은 높이
        a, b = np.asarray(Image.open(self.src).convert("RGB")), np.asarray(out)
        self.assertEqual(a.shape, b.shape)
        self.assertTrue((a[90:] == b[90:]).all())                                         # 제목 아래 표는 한 픽셀도 안 바뀜
        self.assertFalse((a[:90] == b[:90]).all())

    def test_title_not_found_raises(self):
        blank = Path(self.d.name) / "빈.png"
        Image.new("RGB", (400, 300), "white").save(blank)
        with self.assertRaises(ValueError):
            title_render.render(blank, 2026, 11)

    def test_outer_border_is_not_read_as_cell_text(self):
        es = deadline_ocr._without_lines(np.zeros((30, 40), dtype=np.uint8))              # 칸 전체가 선이면 모두 지워짐
        self.assertTrue((es == 255).all())
        text = np.full((30, 120), 255, dtype=np.uint8)
        text[8:22, 20:24] = 0                                                              # 짧은 글자 획은 남음
        self.assertTrue(((deadline_ocr._without_lines(text) < 140).sum()) > 0)


class SourceImageStoreTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        os.environ["SETTLEMENT_CHECKER_DIR"] = str(Path(self.d.name) / "data")

    def tearDown(self):
        os.environ.pop("SETTLEMENT_CHECKER_DIR", None)
        self.d.cleanup()

    def test_copy_survives_original_removal_and_new_import_replaces_it(self):
        a = Path(self.d.name) / "a.jpg"
        a.write_bytes(b"jpg-bytes")
        store.save_source_image(2026, 11, a)
        a.unlink()
        self.assertEqual(Path(store.source_image(2026, 11)).read_bytes(), b"jpg-bytes")
        b = Path(self.d.name) / "b.png"
        b.write_bytes(b"png-bytes")
        store.save_source_image(2026, 11, b)
        self.assertTrue(store.source_image(2026, 11).endswith(".png"))
        self.assertEqual(len(list(store.data_dir().glob("schedule_2611.*"))), 1)            # 옛 확장자 복사본은 지워짐
        self.assertIsNone(store.source_image(2026, 12))


class DropClassifyTest(unittest.TestCase):
    def test_excel_vs_image_vs_other(self):
        import app
        self.assertEqual(app.classify_drop(r"C:\x\1.통계입력_2611.XLSX"), "excel")
        for n in ("a.png", "b.JPG", "c.jpeg"):
            self.assertEqual(app.classify_drop(n), "image")
        self.assertIsNone(app.classify_drop("d.pdf"))
        self.assertIsNone(app.classify_drop("e.xls"))


if __name__ == "__main__":
    unittest.main()
