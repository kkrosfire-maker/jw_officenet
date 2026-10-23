import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ledger import Ledger, MemoryStore, dday_text  # noqa: E402


class Clock:
    def __init__(self, s):
        self.t = datetime.fromisoformat(s)

    def __call__(self):
        return self.t

    def go(self, s):
        self.t = datetime.fromisoformat(s)


def ledger(day="2026-10-22T09:00:00", tasks=None):
    clock = Clock(day)
    store = MemoryStore(tasks)
    return Ledger(store, clock), clock, store


def sections(lg):
    return {t["text"]: t["section"] for t in lg.view()["tasks"]}


class Sections(unittest.TestCase):
    def test_new_task_is_today_and_due_today(self):
        lg, _, _ = ledger()
        lg.add("블로그")
        t = lg.view()["tasks"][0]
        self.assertEqual((t["section"], t["due"], t["dday"]), ("today", "2026-10-22", {"text": "D-0", "kind": "zero"}))

    def test_yesterdays_open_task_is_late_and_yesterdays_done_is_hidden(self):
        lg, clock, _ = ledger()
        lg.add("밀림")
        lg.add("끝냄")
        lg.toggle(lg.tasks[1]["id"])
        clock.go("2026-10-23T09:00:00")
        self.assertEqual(sections(lg), {"밀림": "late"})
        self.assertEqual(lg.view()["tasks"][0]["late_days"], 1)

    def test_task_with_future_due_is_upcoming_not_late_until_d0(self):
        lg, clock, _ = ledger()
        lg.add("보고서", due="2026-10-24")
        self.assertEqual(sections(lg), {"보고서": "upcoming"})
        clock.go("2026-10-23T09:00:00")
        self.assertEqual(sections(lg), {"보고서": "upcoming"})  # 등록일은 지났어도 D-1 이면 밀린 일이 아니다
        clock.go("2026-10-24T09:00:00")
        self.assertEqual(sections(lg), {"보고서": "today"})  # D-0 이면 오늘
        clock.go("2026-10-25T09:00:00")
        self.assertEqual(sections(lg), {"보고서": "late"})  # 마감이 지나면 밀린 일

    def test_toggle_twice_reopens(self):
        lg, _, _ = ledger()
        lg.add("a")
        lg.toggle(lg.tasks[0]["id"])
        lg.toggle(lg.tasks[0]["id"])
        self.assertIsNone(lg.tasks[0]["done_at"])
        lg.toggle(lg.tasks[0]["id"])
        self.assertEqual(sections(lg), {"a": "today"})

    def test_blank_text_is_ignored(self):
        lg, _, _ = ledger()
        lg.add("   ")
        lg.add(None)
        self.assertEqual(lg.tasks, [])


class Dday(unittest.TestCase):
    def test_text(self):
        self.assertEqual([dday_text(g) for g in (2, 0, -3)], ["D+2", "D-0", "D-3"])

    def test_open_task_counts_up_and_done_task_freezes(self):
        lg, clock, _ = ledger()
        lg.add("a", due="2026-10-24")
        self.assertEqual(lg.view()["tasks"][0]["dday"], {"text": "D-2", "kind": "minus"})
        clock.go("2026-10-26T09:00:00")
        self.assertEqual(lg.view()["tasks"][0]["dday"], {"text": "D+2", "kind": "plus"})
        lg.toggle(lg.tasks[0]["id"])  # 26일에 완료 → 그날 기준으로 굳는다
        clock.go("2026-10-26T20:00:00")
        self.assertEqual(lg.view()["tasks"][0]["dday"]["text"], "D+2")

    def test_clearing_due_resets_to_created_day(self):
        lg, _, _ = ledger()
        lg.add("a", due="2026-11-01")
        lg.set_due(lg.tasks[0]["id"], "")
        self.assertEqual(lg.tasks[0]["due"], "2026-10-22")


class Daily(unittest.TestCase):
    def test_daily_is_pinned_section_and_never_late(self):
        lg, clock, _ = ledger()
        lg.add("매일", daily=True)
        clock.go("2026-10-25T09:00:00")
        t = lg.view()["tasks"][0]
        self.assertEqual((t["section"], t["date"]), ("daily", "2026-10-25"))

    def test_done_yesterday_is_archived_and_reborn_unchecked(self):
        lg, clock, _ = ledger()
        lg.add("매일", daily=True)
        lg.toggle(lg.tasks[0]["id"])
        old_id = lg.tasks[0]["id"]
        clock.go("2026-10-23T09:00:00")
        view = lg.view()["tasks"]
        self.assertEqual(len(view), 1)
        self.assertIsNone(view[0]["done_at"])
        self.assertNotEqual(view[0]["id"], old_id)
        old = next(t for t in lg.tasks if t["id"] == old_id)
        self.assertTrue(old["archived"] and not old["daily"] and old["done_at"])  # 엑셀 기록은 남는다

    def test_done_today_stays_checked(self):
        lg, _, _ = ledger()
        lg.add("매일", daily=True)
        lg.toggle(lg.tasks[0]["id"])
        self.assertTrue(lg.view()["tasks"][0]["done_at"])

    def test_turning_off_open_daily_makes_it_a_normal_task(self):
        lg, clock, _ = ledger()
        lg.add("매일", daily=True)
        lg.set_daily(lg.tasks[0]["id"], False)
        clock.go("2026-10-23T09:00:00")
        self.assertEqual(sections(lg), {"매일": "late"})


class Housekeeping(unittest.TestCase):
    def test_remove_orphans_children(self):
        lg, _, _ = ledger()
        lg.add("부모")
        lg.add("자식", parent=lg.tasks[0]["id"])
        lg.remove_many([lg.tasks[0]["id"]])
        self.assertIsNone(lg.tasks[0]["parent"])

    def test_archive_hides_but_keeps_record(self):
        lg, _, _ = ledger()
        lg.add("a")
        lg.toggle(lg.tasks[0]["id"])
        lg.archive([lg.tasks[0]["id"]])
        self.assertEqual(lg.view()["tasks"], [])
        self.assertEqual(len(lg.tasks), 1)

    def test_every_change_is_saved(self):
        lg, _, store = ledger()
        before = store.saves
        lg.add("a")
        lg.edit(lg.tasks[0]["id"], "b")
        lg.set_note(lg.tasks[0]["id"], "메모")
        self.assertEqual(store.saves, before + 3)


if __name__ == "__main__":
    unittest.main()
