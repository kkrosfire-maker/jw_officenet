"""할 일 장부 - 할 일의 규칙(구역 분류·반복 루틴 갱신·완료·보관·D-day)을 한 곳에 모은 모듈.
화면(pywebview)과 파일 저장을 모르기 때문에 날짜(clock)와 저장소(store)를 바꿔 끼워 테스트할 수 있다."""
import json
import os
import calendar
import uuid
from datetime import date, datetime, timedelta

WEEKDAY = "월화수목금토일"


def parse_day(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def dday_text(gap):
    """gap = 기준일 - 마감일. +지연 / 0 당일 / -여유."""
    return f"D+{gap}" if gap > 0 else "D-0" if gap == 0 else f"D{gap}"


def due_gap(task, ref_day):
    """마감일 대비 며칠 지났는가(ref_day 는 date). 마감일이 없으면 None."""
    return (ref_day - parse_day(task["due"])).days if task.get("due") else None


# ---- 반복 규칙 ----
# "day" = 매일, "week:0"~"week:6" = 매주 월~일, "month:1"~"month:31" = 매월 N일(31 = 말일, 짧은 달은 마지막 날)
def _month_day(y, m, n):
    return date(y, m, min(n, calendar.monthrange(y, m)[1]))


def _rule(rule):
    kind, _, n = rule.partition(":")
    return kind, int(n or 0)


def valid_rule(rule):
    try:
        kind, n = _rule(rule)
    except (AttributeError, ValueError):
        return False
    return kind == "day" or (kind == "week" and 0 <= n <= 6) or (kind == "month" and 1 <= n <= 31)


def occ_on_or_before(rule, day):
    """day 이전(당일 포함) 가장 최근 회차."""
    kind, n = _rule(rule)
    if kind == "week":
        return day - timedelta(days=(day.weekday() - n) % 7)
    if kind == "month":
        c = _month_day(day.year, day.month, n)
        if c <= day:
            return c
        y, m = (day.year, day.month - 1) if day.month > 1 else (day.year - 1, 12)
        return _month_day(y, m, n)
    return day


def occ_after(rule, day):
    """day 다음(당일 제외) 첫 회차."""
    kind, n = _rule(rule)
    if kind == "week":
        return day + timedelta(days=(n - day.weekday()) % 7 or 7)
    if kind == "month":
        c = _month_day(day.year, day.month, n)
        if c > day:
            return c
        y, m = (day.year, day.month + 1) if day.month < 12 else (day.year + 1, 1)
        return _month_day(y, m, n)
    return day + timedelta(days=1)


class JsonStore:
    """todos.json 한 파일에 통째로 저장한다. 쓰는 도중 꺼져도 깨지지 않게 임시 파일에 쓴 뒤 바꿔치기한다."""

    def __init__(self, path):
        self.path = path

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)["tasks"]
        except (OSError, ValueError, KeyError):
            return []

    def save(self, tasks):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"tasks": tasks}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)


class MemoryStore:
    """테스트용 저장소."""

    def __init__(self, tasks=None):
        self.tasks = tasks or []
        self.saves = 0

    def load(self):
        return self.tasks

    def save(self, tasks):
        self.tasks = tasks
        self.saves += 1


class Ledger:
    def __init__(self, store, clock=datetime.now):
        self._store, self._clock = store, clock
        self.tasks = store.load()
        for t in self.tasks:  # 완료일을 정하지 않은 일은 만든 날이 기준(D-0 부터 시작)
            t["due"] = t.get("due") or t["date"]
            if "daily" in t:  # 예전 '매일 반복' 표시를 반복 규칙으로 옮긴다
                t["repeat"] = "day" if t.pop("daily") else t.get("repeat")
        self._store.save(self.tasks)

    # ---- 시간 ----
    def now(self):
        return self._clock().replace(microsecond=0)

    def today(self):
        return self.now().date().isoformat()

    # ---- 변경 ----
    def _find(self, tid):
        return next((t for t in self.tasks if t["id"] == tid), None)

    def _save(self):
        self._store.save(self.tasks)

    def add(self, text, parent=None, due=None, repeat=None):
        text = (text or "").strip()
        repeat = repeat if valid_rule(repeat) else None
        if text:
            first = self._first_occ(repeat) if repeat and not due else None
            self.tasks.append({"id": uuid.uuid4().hex[:10], "text": text, "date": self.today(), "created_at": self.now().isoformat(),
                               "done_at": None, "note": "", "parent": parent, "due": due or first or self.today(), "repeat": repeat})
            self._save()

    def _first_occ(self, rule):
        """오늘이 회차면 오늘, 아니면 다음 회차."""
        return occ_after(rule, self.now().date() - timedelta(days=1)).isoformat()

    def toggle(self, tid):
        t = self._find(tid)
        if t:
            t["done_at"] = None if t["done_at"] else self.now().isoformat()
            self._save()

    def edit(self, tid, text):
        t, text = self._find(tid), (text or "").strip()
        if t and text:
            t["text"] = text
            self._save()

    def set_note(self, tid, note):
        t = self._find(tid)
        if t:
            t["note"] = note
            self._save()

    def set_due(self, tid, due):
        t = self._find(tid)
        if t:
            t["due"] = due or t["date"]  # 비우면 만든 날로 되돌린다
            self._save()

    def set_repeat(self, tid, rule):
        """rule 이 없으면 반복을 끈다. 미완료라면 새 규칙의 첫 회차(오늘 또는 다음 회차)로 마감일을 옮긴다."""
        t = self._find(tid)
        if t:
            rule = rule if valid_rule(rule) else None
            t["repeat"] = rule
            if not t.get("done_at"):
                if rule:
                    t["due"] = self._first_occ(rule)
                elif t["due"] < self.today():
                    t["date"] = t["due"] = self.today()  # 반복을 끄면 오늘 할 일로 남긴다
            self._save()

    def remove_many(self, ids):
        ids = set(ids)
        self.tasks = [t for t in self.tasks if t["id"] not in ids]
        for t in self.tasks:
            if t.get("parent") in ids:
                t["parent"] = None
        self._save()

    def archive(self, ids):
        """엑셀에 담은 완료 항목을 목록에서 치운다(기록은 남아 다음 엑셀에도 들어간다)."""
        ids = set(ids)
        for t in self.tasks:
            if t["id"] in ids:
                t["archived"] = True
        self._save()

    # ---- 반복 루틴 ----
    def _roll_routines(self):
        """어제까지 완료한 루틴은 기록(보관)으로 남기고 다음 회차의 새 항목으로 되살린다.
        못 한 루틴은 밀린 일이 되지 않고, 다음 회차가 오면 기록 없이 그 회차로 넘어간다."""
        today_d, changed = self.now().date(), False
        today = today_d.isoformat()
        for t in list(self.tasks):
            rule = t.get("repeat")
            if not rule or t.get("archived"):
                continue
            done_day = t["done_at"][:10] if t.get("done_at") else None
            if done_day and done_day < today:
                nxt = occ_after(rule, parse_day(max(t["due"], done_day)))
                if nxt < today_d:  # 한동안 앱을 안 켰으면 지난 회차들은 건너뛴다
                    nxt = occ_on_or_before(rule, today_d)
                self.tasks.append({"id": uuid.uuid4().hex[:10], "text": t["text"], "date": nxt.isoformat(), "created_at": self.now().isoformat(),
                                   "done_at": None, "note": "", "parent": None, "due": nxt.isoformat(), "repeat": rule})
                t["repeat"] = None
                t["archived"] = True
                changed = True
            elif not done_day:
                cur = occ_on_or_before(rule, today_d).isoformat()
                if cur > t["due"]:
                    t["date"] = t["due"] = cur
                    changed = True
        if changed:
            self._save()

    # ---- 화면용 ----
    def view(self):
        """화면에 보일 목록. section: routine(반복 루틴) / late(밀린 일) / today(오늘) / upcoming(해야 할 일). 지난 완료분은 뺀다.
        미완료는 등록일이 아니라 마감일로 나눈다: 지남 = 밀린 일, 오늘(D-0) = 오늘, 아직(D-1 이상) = 해야 할 일.
        루틴은 회차 날이 되면(못 했으면 다음 회차 전까지) 루틴 구역에, 회차 전에는 해야 할 일에 놓인다."""
        self._roll_routines()
        today = self.today()
        today_d = self.now().date()
        shown = []
        for t in self.tasks:
            if t.get("archived"):
                continue
            done_day = t["done_at"][:10] if t.get("done_at") else None
            if t.get("repeat") and (done_day or t["repeat"] == "day" or t["due"] <= today):
                sec = "routine"
            elif done_day:
                sec = "today" if done_day == today else None
            elif t["due"] < today:
                sec = "late"
            elif t["due"] > today:
                sec = "upcoming"
            else:
                sec = "today"
            if not sec:
                continue
            gap = due_gap(t, parse_day(done_day) if done_day else today_d)
            shown.append({**t, "section": sec, "late_days": (today_d - parse_day(t["date"])).days,
                          "dday": None if gap is None else {"text": dday_text(gap), "kind": "plus" if gap > 0 else "zero" if gap == 0 else "minus"}})
        return {
            "today": today,
            "label": f"{today_d.month}월 {today_d.day}일",
            "year": f"{today_d.year}년",
            "weekday": WEEKDAY[today_d.weekday()] + "요일",
            "tasks": shown,
            "now": self.now().isoformat(),
        }
