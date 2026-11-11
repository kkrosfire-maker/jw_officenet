"""읽은 마감일정을 저장 형태로 바꾸고, 제약사 이름을 엑셀 표기에 연결한다.

저장은 읽은 그대로(날짜·이름·시각·공지 여부). 엑셀의 어느 제약사인지는 보여줄 때마다 다시 계산한다
(엑셀에 새 제약사가 생겨도 반영되고, 사용자가 가르친 별칭도 바로 먹는다).
연결 순서: 별칭 → 같은 이름 → 비슷한 이름(0.8 이상, 오독 보정) → 연결 안 됨.
"""
import re
from dataclasses import dataclass

import names

AUTO_FIX = 0.8
_HANGUL_OK = re.compile(r"^[가-힣0-9A-Za-z()·.\- ]+$")


@dataclass
class Deadline:
    day: int
    name: str
    hour: "int | None" = None      # 마감 시각(시). None = 하루 종일
    notice: bool = False           # 제약사가 아닌 안내 문구(예: '코드등록도 마감')

    def to_json(self):
        return dict(day=self.day, name=self.name, hour=self.hour, notice=self.notice)

    @classmethod
    def from_json(cls, d):
        return cls(int(d["day"]), d["name"], d.get("hour"), bool(d.get("notice")))


def looks_garbled(text):
    """한글 이름 칸인데 영문 조각이 섞여 깨진 것으로 보이는가."""
    t = text or ""
    hangul = len(re.findall(r"[가-힣]", t))
    latin = len(re.findall(r"[A-Za-z]", t))
    return hangul < 2 or latin > 0 and latin >= hangul or not _HANGUL_OK.match(t)


def resolve(name, book, aliases=None):
    """(엑셀 표기, 'alias'|'ok'|'fixed') — 연결 안 되면 (None, 'none')."""
    k = names.norm(name)
    typo = False
    for bad in ("팡", "팝"):                       # OCR이 '팜'을 '팡'·'팝'으로 읽는 일관된 오독
        if k not in book.latest and bad in k and names.norm(name.replace(bad, "팜")) in book.latest:
            name = name.replace(bad, "팜")
            k = names.norm(name)
            typo = True
    if aliases and aliases.get(k) == "-":
        return None, "ignored"
    if aliases and k in aliases and names.norm(aliases[k]) in book.latest:
        return book.latest[names.norm(aliases[k])], "alias"
    if k in book.latest:
        return book.latest[k], "fixed" if typo else "ok"
    best, _ = book.closest(name, threshold=AUTO_FIX)
    if best:
        return best, "fixed"
    return None, "none"


def from_entries(entries, book, reread=None):
    """OCR 결과 → [Deadline]. 깨진 글자는 다른 방식으로 다시 읽어 이번 달 제약사와 맞는 걸 고른다."""
    out = []
    for e in entries:
        if e.is_notice:
            out.append(Deadline(e.day, e.name, e.hour, True))
            continue
        name, hour = e.name, e.hour
        if reread and looks_garbled(name) and resolve(name, book)[0] is None:
            from collections import Counter
            from deadline_ocr import Entry
            alts = [Entry(e.day, t) for t in reread(e)]
            hit = next((a for a in alts if resolve(a.name, book)[0]), None)
            if hit:                                   # 이번 달 제약사와 맞는 읽기가 있으면 그것
                name, hour = hit.name, hour if hour is not None else hit.hour
            else:                                     # 없으면(이번 달 거래 없는 제약사) 깨지지 않은 읽기 중 가장 많이 나온 것
                clean = Counter(a.name for a in alts if not looks_garbled(a.name))
                if clean:
                    name = max(clean.items(), key=lambda kv: (kv[1], len(kv[0])))[0]
                    hour = hour if hour is not None else next((a.hour for a in alts if a.name == name and a.hour), None)
        out.append(Deadline(e.day, name, hour))
    return out
