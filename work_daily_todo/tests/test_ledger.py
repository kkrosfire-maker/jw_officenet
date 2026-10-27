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
        lg.add("매일", repeat="day")
        clock.go("2026-10-26T09:00:00")
        t = lg.view()["tasks"][0]
        self.assertEqual((t["section"], t["date"]), ("routine", "2026-10-26"))

    def test_daily_means_weekdays(self):
        lg, clock, _ = ledger("2026-10-24T09:00:00")  # 토요일에 만들면 첫 회차는 월요일
        lg.add("매일", repeat="day")
        self.assertEqual(lg.tasks[0]["due"], "2026-10-26")

    def test_done_friday_comes_back_monday_not_weekend(self):
        lg, clock, _ = ledger("2026-10-23T09:00:00")  # 금
        lg.add("매일", repeat="day")
        lg.toggle(lg.tasks[0]["id"])
        clock.go("2026-10-24T09:00:00")  # 토: 다음 회차는 월요일(D-2), 진행률에 안 잡힌다
        t = lg.view()["tasks"][0]
        self.assertEqual((t["due"], t["done_at"]), ("2026-10-26", None))
        self.assertEqual(t["dday"]["text"], "D-2")

    def test_open_friday_task_waits_over_weekend_then_moves_to_monday(self):
        lg, clock, _ = ledger("2026-10-23T09:00:00")
        lg.add("매일", repeat="day")
        clock.go("2026-10-25T09:00:00")  # 일
        self.assertEqual(lg.view()["tasks"][0]["due"], "2026-10-23")
        clock.go("2026-10-26T09:00:00")  # 월
        self.assertEqual(lg.view()["tasks"][0]["due"], "2026-10-26")

    def test_done_yesterday_is_archived_and_reborn_unchecked(self):
        lg, clock, _ = ledger()
        lg.add("매일", repeat="day")
        lg.toggle(lg.tasks[0]["id"])
        old_id = lg.tasks[0]["id"]
        clock.go("2026-10-23T09:00:00")
        view = lg.view()["tasks"]
        self.assertEqual(len(view), 1)
        self.assertIsNone(view[0]["done_at"])
        self.assertNotEqual(view[0]["id"], old_id)
        old = next(t for t in lg.tasks if t["id"] == old_id)
        self.assertTrue(old["archived"] and not old["repeat"] and old["done_at"])  # 엑셀 기록은 남는다

    def test_done_today_stays_checked(self):
        lg, _, _ = ledger()
        lg.add("매일", repeat="day")
        lg.toggle(lg.tasks[0]["id"])
        self.assertTrue(lg.view()["tasks"][0]["done_at"])

    def test_turning_off_open_daily_makes_it_a_normal_task(self):
        lg, clock, _ = ledger()
        lg.add("매일", repeat="day")
        lg.set_repeat(lg.tasks[0]["id"], None)
        clock.go("2026-10-23T09:00:00")
        self.assertEqual(sections(lg), {"매일": "late"})


class Routine(unittest.TestCase):
    # 2026-10-22 은 목요일(week:3), 2026-10-26 은 월요일(week:0)
    def test_weekly_shows_in_routine_before_its_day(self):
        lg, clock, _ = ledger()
        lg.add("주간보고", repeat="week:0")
        t = lg.view()["tasks"][0]
        self.assertEqual((t["section"], t["due"], t["dday"]["text"]), ("routine", "2026-10-26", "D-4"))
        clock.go("2026-10-26T09:00:00")
        self.assertEqual(sections(lg), {"주간보고": "routine"})

    def test_weekly_added_on_its_day_is_due_today(self):
        lg, _, _ = ledger()
        lg.add("목요회의", repeat="week:3")
        self.assertEqual(sections(lg), {"목요회의": "routine"})

    def test_missed_weekly_stays_until_next_occurrence_then_moves_without_record(self):
        lg, clock, _ = ledger("2026-10-26T09:00:00")
        lg.add("주간보고", repeat="week:0")
        clock.go("2026-10-28T09:00:00")
        t = lg.view()["tasks"][0]
        self.assertEqual((t["section"], t["due"], t["dday"]["text"]), ("routine", "2026-10-26", "D+2"))
        clock.go("2026-11-03T09:00:00")
        t = lg.view()["tasks"][0]
        self.assertEqual((t["section"], t["due"]), ("routine", "2026-11-02"))
        self.assertEqual(len(lg.tasks), 1)

    def test_done_weekly_is_archived_and_reborn_for_next_week(self):
        lg, clock, _ = ledger("2026-10-26T09:00:00")
        lg.add("주간보고", repeat="week:0")
        clock.go("2026-10-27T09:00:00")  # 하루 늦게 완료
        lg.toggle(lg.tasks[0]["id"])
        self.assertEqual(sections(lg), {"주간보고": "routine"})
        clock.go("2026-10-28T09:00:00")
        view = lg.view()["tasks"]
        self.assertEqual([(t["section"], t["due"], t["done_at"]) for t in view], [("routine", "2026-11-02", None)])
        self.assertTrue(lg.tasks[0]["archived"] and lg.tasks[0]["done_at"])

    def test_done_early_counts_for_that_occurrence(self):
        lg, clock, _ = ledger()  # 목요일에 다음 월요일 몫을 미리 함
        lg.add("주간보고", repeat="week:0")
        lg.toggle(lg.tasks[0]["id"])
        clock.go("2026-10-23T09:00:00")
        self.assertEqual(lg.view()["tasks"][0]["due"], "2026-11-02")

    def test_long_absence_skips_to_latest_occurrence(self):
        lg, clock, _ = ledger("2026-10-26T09:00:00")
        lg.add("주간보고", repeat="week:0")
        lg.toggle(lg.tasks[0]["id"])
        clock.go("2026-11-20T09:00:00")
        self.assertEqual(lg.view()["tasks"][0]["due"], "2026-11-16")

    def test_monthly_last_day_clamps_to_short_months(self):
        lg, clock, _ = ledger("2026-10-31T09:00:00")
        lg.add("월말정산", repeat="month:31")
        lg.toggle(lg.tasks[0]["id"])
        clock.go("2026-11-01T09:00:00")
        self.assertEqual(lg.view()["tasks"][0]["due"], "2026-11-30")
        clock.go("2027-02-28T09:00:00")
        lg.toggle(lg.view()["tasks"][0]["id"])
        clock.go("2027-03-01T09:00:00")
        self.assertEqual(lg.view()["tasks"][0]["due"], "2027-03-31")

    def test_monthly_waits_for_its_date(self):
        lg, clock, _ = ledger()
        lg.add("임대료 확인", repeat="month:5")
        self.assertEqual(lg.view()["tasks"][0]["due"], "2026-11-05")
        clock.go("2026-11-05T09:00:00")
        self.assertEqual(sections(lg), {"임대료 확인": "routine"})

    def test_set_repeat_moves_open_task_to_first_occurrence(self):
        lg, _, _ = ledger()
        lg.add("a")
        lg.set_repeat(lg.tasks[0]["id"], "week:0")
        self.assertEqual(lg.tasks[0]["due"], "2026-10-26")

    def test_invalid_rule_is_ignored(self):
        lg, _, _ = ledger()
        lg.add("a", repeat="week:9")
        self.assertIsNone(lg.tasks[0]["repeat"])

    def test_old_daily_flag_is_migrated(self):
        lg, _, _ = ledger(tasks=[{"id": "x", "text": "매일", "date": "2026-10-20", "created_at": "2026-10-20T09:00:00",
                                  "done_at": None, "note": "", "parent": None, "due": "2026-10-20", "daily": True}])
        self.assertEqual(lg.tasks[0]["repeat"], "day")
        self.assertNotIn("daily", lg.tasks[0])
        self.assertEqual(sections(lg), {"매일": "routine"})


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
