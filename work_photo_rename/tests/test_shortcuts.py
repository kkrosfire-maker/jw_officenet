import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shortcuts import Shortcuts
from undo_stack import HistoryController


class FakeInput:
    pass


class FakeCanvas:
    pass


class FakeRoot:
    """tk 창 대신: bind_all 로 등록된 핸들러를 모아 두고, focus_get 이 돌려줄 위젯을 정한다."""

    def __init__(self):
        self.focus = FakeCanvas()
        self.bound = {}

    def focus_get(self):
        return self.focus

    def bind_all(self, seq, fn, add=None):
        assert add == "+", "여러 핸들러가 서로 덮어쓰지 않아야 한다"
        self.bound.setdefault(seq, []).append(fn)

    def press(self, seq, event=None):
        return [fn(event) for fn in self.bound[seq]]


class ShortcutsTest(unittest.TestCase):
    def setUp(self):
        self.root = FakeRoot()
        self.keys = Shortcuts(self.root, (FakeInput,))

    def test_handler_runs_when_focus_is_elsewhere(self):
        self.keys.bind("<Delete>", lambda e: "break")
        self.assertEqual(self.root.press("<Delete>"), ["break"])

    def test_handler_skipped_while_typing(self):
        self.keys.bind("<Delete>", lambda e: "break")
        self.root.focus = FakeInput()
        self.assertEqual(self.root.press("<Delete>"), [None])      # None = 입력칸의 기본 동작에 맡김

    def test_in_inputs_handlers_still_run_while_typing(self):
        seen = []
        self.keys.bind("<KeyPress-Alt_L>", lambda e: seen.append("alt"), in_inputs=True)
        self.root.focus = FakeInput()
        self.root.press("<KeyPress-Alt_L>")
        self.assertEqual(seen, ["alt"])

    def test_same_key_can_have_several_handlers(self):
        self.keys.bind("<Left>", lambda e: "a")
        self.keys.bind("<Left>", lambda e: "b")
        self.assertEqual(self.root.press("<Left>"), ["a", "b"])

    def test_no_skip_types_never_skips(self):
        keys = Shortcuts(self.root)
        keys.bind("<Up>", lambda e: "x")
        self.root.focus = FakeInput()
        self.assertEqual(self.root.press("<Up>"), ["x"])


class HistoryKeysTest(unittest.TestCase):
    def test_ctrl_z_undoes_and_reports_status_but_not_while_typing(self):
        root = FakeRoot()
        state = {"v": 1}
        h = HistoryController(snapshot_fn=lambda: state["v"], restore_fn=lambda v: state.update(v=v))
        status = []
        h.bind_keys(Shortcuts(root, (FakeInput,)), status_fn=lambda action, ok: status.append((action, ok)))
        h.push(0)
        state["v"] = 1
        root.focus = FakeInput()
        self.assertEqual(root.press("<Control-z>"), [None])
        self.assertEqual(state["v"], 1)                              # 입력 중에는 되돌리지 않는다
        root.focus = FakeCanvas()
        self.assertEqual(root.press("<Control-z>"), ["break"])
        self.assertEqual((state["v"], status), (0, [("undo", True)]))
        root.press("<Control-y>")
        self.assertEqual((state["v"], status[-1]), (1, ("redo", True)))


if __name__ == "__main__":
    unittest.main()
