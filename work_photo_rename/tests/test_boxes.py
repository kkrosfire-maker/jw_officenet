import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from boxes import BoxSet, MIN_HALF

W, H = 2000, 1000


def boxset_with(*specs):
    b = BoxSet()
    for cx, cy, hw, hh in specs:
        b.add(W, H, thickness=5)
        b.rects[-1].update(cx=cx, cy=cy, hw=hw, hh=hh)
    return b


class AddDeleteTest(unittest.TestCase):
    def test_add_is_centered_and_selected(self):
        b = BoxSet()
        idx = b.add(W, H, 0.3, 0.04, 6)
        self.assertEqual(idx, 0)
        r = b.rects[0]
        self.assertEqual((r["cx"], r["cy"], r["hw"], r["hh"], r["thickness"]), (1000, 500, 600, 40, 6))
        self.assertEqual((b.primary, b.sel), (0, {0}))

    def test_delete_selected_removes_all_selected(self):
        b = boxset_with((10, 10, 50, 20), (20, 20, 50, 20), (30, 30, 50, 20))
        b.select_many([0, 2], 2)
        self.assertEqual(b.delete_selected(), 2)
        self.assertEqual([r["cx"] for r in b.rects], [20])
        self.assertEqual((b.primary, b.sel), (None, set()))

    def test_delete_without_selection_does_nothing(self):
        b = boxset_with((10, 10, 50, 20))
        b.deselect()
        self.assertIsNone(b.delete_selected())
        self.assertEqual(len(b.rects), 1)

    def test_clear(self):
        b = boxset_with((10, 10, 50, 20))
        self.assertTrue(b.clear())
        self.assertFalse(b.clear())


class SnapshotTest(unittest.TestCase):
    def test_snapshot_is_deep_copy(self):
        b = boxset_with((10, 10, 50, 20))
        snap = b.snapshot()
        b.rects[0]["cx"] = 999
        self.assertEqual(snap[0]["cx"], 10)

    def test_replace_drops_selection(self):
        b = boxset_with((10, 10, 50, 20))
        b.replace([{"cx": 1, "cy": 2, "hw": 3, "hh": 4, "angle": 0, "thickness": 4}])
        self.assertEqual((b.primary, b.sel), (None, set()))
        self.assertEqual(len(b.rects), 1)


class KeyboardEditTest(unittest.TestCase):
    def test_move_clamps_center_inside_photo(self):
        b = boxset_with((5, 5, 50, 20))
        b.move_selected(-50, -50, W, H)
        self.assertEqual((b.rects[0]["cx"], b.rects[0]["cy"]), (0.0, 0.0))
        b.move_selected(99999, 99999, W, H)
        self.assertEqual((b.rects[0]["cx"], b.rects[0]["cy"]), (float(W), float(H)))

    def test_move_applies_to_every_selected_box(self):
        b = boxset_with((100, 100, 50, 20), (200, 200, 50, 20), (300, 300, 50, 20))
        b.select_many([0, 1], 1)
        b.move_selected(10, 5, W, H)
        self.assertEqual([(r["cx"], r["cy"]) for r in b.rects], [(110, 105), (210, 205), (300, 300)])

    def test_resize_changes_width_and_height_by_full_amount(self):
        b = boxset_with((100, 100, 50, 20))
        b.resize_selected(10, -6)
        self.assertEqual((b.rects[0]["hw"], b.rects[0]["hh"]), (55, 17))

    def test_resize_never_below_minimum(self):
        b = boxset_with((100, 100, 50, 20))
        b.resize_selected(-9999, -9999)
        self.assertEqual((b.rects[0]["hw"], b.rects[0]["hh"]), (MIN_HALF, MIN_HALF))

    def test_rotate_wraps_around(self):
        b = boxset_with((100, 100, 50, 20))
        b.rotate_selected(-15)
        self.assertEqual(b.rects[0]["angle"], 345)
        b.deselect()
        self.assertFalse(b.rotate_selected(15))

    def test_thickness_follows_primary(self):
        b = boxset_with((1, 1, 5, 5), (2, 2, 5, 5))
        b.select(0)
        b.set_thickness(9)
        self.assertEqual(b.thickness(), 9)
        self.assertEqual(b.rects[1]["thickness"], 5)
        b.deselect()
        self.assertIsNone(b.thickness())


class CopyPasteTest(unittest.TestCase):
    def test_paste_goes_to_center_keeping_size_angle_thickness(self):
        b = boxset_with((100, 900, 321, 45))
        b.rects[0].update(angle=10, thickness=7)
        b.select(0)
        self.assertEqual(b.copy_selected(), 1)
        self.assertEqual(b.paste(W, H), 1)
        pasted = b.rects[1]
        self.assertEqual((pasted["cx"], pasted["cy"]), (1000, 500))
        self.assertEqual((pasted["hw"], pasted["hh"], pasted["angle"], pasted["thickness"]), (321, 45, 10, 7))
        self.assertEqual((b.primary, b.sel), (1, {1}))

    def test_paste_does_not_alias_the_original(self):
        b = boxset_with((100, 900, 321, 45))
        b.select(0)
        b.copy_selected()
        b.paste(W, H)
        b.rects[1]["hw"] = 1
        b.paste(W, H)
        self.assertEqual(b.rects[2]["hw"], 321)      # 클립보드는 붙인 박스를 고쳐도 그대로

    def test_paste_many_keeps_relative_layout_centered(self):
        b = boxset_with((100, 100, 50, 20), (300, 100, 50, 20))
        b.select_many([0, 1], 1)
        self.assertEqual(b.copy_selected(), 2)
        self.assertEqual(b.paste(W, H), 2)
        self.assertEqual([(r["cx"], r["cy"]) for r in b.rects[2:]], [(900, 500), (1100, 500)])
        self.assertEqual(b.sel, {2, 3})

    def test_clipboard_survives_switching_photo(self):
        b = boxset_with((100, 100, 77, 33))
        b.select(0)
        b.copy_selected()
        b.reset()                                    # 다른 사진으로
        self.assertEqual(b.rects, [])
        self.assertEqual(b.paste(800, 500), 1)
        self.assertEqual((b.rects[0]["cx"], b.rects[0]["cy"], b.rects[0]["hw"]), (400, 250, 77))

    def test_copy_with_nothing_selected_keeps_old_clipboard(self):
        b = boxset_with((100, 100, 77, 33))
        b.select(0)
        b.copy_selected()
        b.deselect()
        self.assertEqual(b.copy_selected(), 0)
        self.assertEqual(b.paste(W, H), 1)

    def test_paste_empty_clipboard(self):
        self.assertEqual(BoxSet().paste(W, H), 0)


if __name__ == "__main__":
    unittest.main()
