"""화면에 보여줄 내용 계산 — 마감일정 × 엑셀 줄 → 날짜별 (담당자·병원·제약사) 목록과 요약.

순수 로직(창·파일 없음): 시험은 tests/ 에서 한다.
"""
import datetime as dt
from collections import OrderedDict, defaultdict

import names
import schedule


def build_view(year, month, deadlines, rows, aliases, today):
    book = names.NameBook.from_names([r.pharma for r in rows])
    groups = defaultdict(OrderedDict)         # 정규화 제약사 → {(담당자,병원): [줄들]}
    for r in rows:
        groups[names.norm(r.pharma)].setdefault((r.manager, r.hospital), []).append(r)

    items, unlinked, notices, linked = [], [], [], set()
    seen = set()
    for d in deadlines:
        if d.notice:
            notices.append(dict(day=d.day, text=d.name))
            continue
        pharma, how = schedule.resolve(d.name, book, aliases)
        if how == "ignored":
            continue
        if pharma is None:
            unlinked.append(dict(day=d.day, name=d.name, hour=d.hour, garbled=schedule.looks_garbled(d.name)))
            continue
        k = names.norm(pharma)
        linked.add(k)
        if (d.day, k) in seen:
            continue
        seen.add((d.day, k))
        date = dt.date(year, month, d.day).isoformat()
        for (mgr, hosp), rs in groups[k].items():
            done_n = sum(1 for r in rs if r.done)
            items.append(dict(date=date, day=d.day, hour=d.hour, pharma=pharma, raw=d.name, how=how,
                              manager=mgr, hospital=hosp, total=len(rs), done_n=done_n,
                              carried_n=sum(1 for r in rs if r.status == "통계이월"),
                              done=done_n == len(rs)))
    items.sort(key=lambda i: (i["date"], 99 if i["hour"] is None else i["hour"], i["pharma"], i["manager"], i["hospital"]))

    missing = []
    for k, display in book.latest.items():
        if k in linked:
            continue
        pend = sum(1 for rs in groups[k].values() for r in rs if not r.done)
        missing.append(dict(pharma=display, pending=pend, hospitals=len(groups[k])))
    missing.sort(key=lambda m: (-m["pending"], m["pharma"]))

    t = today.isoformat()
    pend_items = [i for i in items if not i["done"]]
    summary = dict(
        total=len(items), done=len(items) - len(pend_items), pending=len(pend_items),
        overdue=sum(1 for i in pend_items if i["date"] < t),
        today=sum(1 for i in pend_items if i["date"] == t),
    )
    return dict(year=year, month=month, today=t, items=items,
                first_day=min((d.day for d in deadlines), default=None),
                last_day=max((d.day for d in deadlines), default=None),     # 달력은 이 날이 든 주까지만 그린다
                unlinked=unlinked, notices=notices,
                missing=missing, summary=summary,
                managers=sorted({i["manager"] for i in items}),
                pharmas=sorted(book.latest.values(), key=names.sort_key))
