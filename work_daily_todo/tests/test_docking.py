import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from docking import dock_x  # noqa: E402


class DockX(unittest.TestCase):
    def test_right_when_room(self):
        self.assertEqual(dock_x(100, 1000, 360, 1920), 1000)

    def test_left_when_no_room(self):
        self.assertEqual(dock_x(1200, 1700, 360, 1920), 840)

    def test_never_off_screen_left(self):
        self.assertEqual(dock_x(100, 700, 360, 800), 0)


if __name__ == "__main__":
    unittest.main()
