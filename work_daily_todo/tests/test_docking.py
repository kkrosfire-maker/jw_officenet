import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from docking import dock_x, usable  # noqa: E402


class DockX(unittest.TestCase):
    def test_right_when_room(self):
        self.assertEqual(dock_x(100, 1000, 360, 1920), 1000)

    def test_left_when_no_room(self):
        self.assertEqual(dock_x(1200, 1700, 360, 1920), 840)

    def test_never_off_screen_left(self):
        self.assertEqual(dock_x(100, 700, 360, 800), 0)


class Usable(unittest.TestCase):
    SCREEN = (-1920, 0, 1920, 1080)  # 왼쪽에 보조 모니터

    def test_normal(self):
        self.assertTrue(usable((1500, 20, 360, 800), self.SCREEN))

    def test_left_monitor(self):
        self.assertTrue(usable((-523, 16, 329, 1008), self.SCREEN))

    def test_minimized_garbage(self):
        self.assertFalse(usable((-32000, -32000, 160, 28), self.SCREEN))

    def test_off_screen(self):
        self.assertFalse(usable((5000, 20, 360, 800), self.SCREEN))


if __name__ == "__main__":
    unittest.main()
