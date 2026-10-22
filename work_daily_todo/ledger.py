"""할 일 장부 - 할 일의 규칙(구역 분류·매일 반복 갱신·완료·보관·D-day)을 한 곳에 모은 모듈.
화면(pywebview)과 파일 저장을 모르기 때문에 날짜(clock)와 저장소(store)를 바꿔 끼워 테스트할 수 있다."""
import json
import os
import uuid
from datetime import datetime

WEEKDAY = "월화수목금토일"


def parse_day(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def dday_text(gap):
    """gap = 기준일 - 마감일. +지연 / 0 당일 / -여유."""
    return f"D+{gap}" if gap > 0 else "D-0" if gap == 0 else f"D{gap}"


def due_gap(task, ref_day):
    """마감일 대비 며칠 지났는가(ref_day 는 date). 마감일이 없으면 None."""
    return (ref_day - parse_day(task["due"])).days if task.get("due") else None


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

    def add(self, text, parent=None, due=None, daily=False):
        text = (text or "").strip()
        if text:
            self.tasks.append({"id": uuid.uuid4().hex[:10], "text": text, "date": self.today(), "created_at": self.now().isoformat(),
                               "done_at": None, "note": "", "parent": parent, "due": due or self.today(), "daily": bool(daily)})
            self._save()

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

    def set_daily(self, tid, on):
        t = self._find(tid)
        if t:
            t["daily"] = bool(on)
            if not on and not t.get("done_at"):
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

    # ---- 매일 반복 ----
    def _roll_daily(self):
        """어제까지 완료한 반복 항목은 기록(보관)으로 남기고 오늘 새 항목으로 되살리고, 못 한 건 밀린 일 없이 오늘로 옮긴다."""
        today, changed = self.today(), False
        for t in list(self.tasks):
            if not t.get("daily") or t.get("archived"):
                continue
            done_day = t["done_at"][:10] if t.get("done_at") else None
            if done_day and done_day < today:
                self.tasks.append({"id": uuid.uuid4().hex[:10], "text": t["text"], "date": today, "created_at": self.now().isoformat(),
                                   "done_at": None, "note": "", "parent": None, "due": today, "daily": True})
                t["daily"] = False
                t["archived"] = True
                changed = True
            elif not done_day and t["date"] < today:
                t["date"] = t["due"] = today
                changed = True
        if changed:
            self._save()

    # ---- 화면용 ----
    def view(self):
        """화면에 보일 목록. section: daily(매일 반복) / late(밀린 일) / today(오늘). 지난 완료분은 뺀다."""
        self._roll_daily()
        today = self.today()
        today_d = self.now().date()
        shown = []
        for t in self.tasks:
            if t.get("archived"):
                continue
            done_day = t["done_at"][:10] if t.get("done_at") else None
            if t.get("daily"):
                sec = "daily"
            elif done_day:
                sec = "today" if done_day == today else None
            elif t["date"] < today:
                sec = "late"
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
