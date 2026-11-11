"""이름 처리 모듈 — 병원·제약사 이름을 "같다/비슷하다"고 판단하는 규칙을 한곳에 모은다.

같은 이름 기준 하나(norm)를 입력 칸 후보, 엑셀 줄 찾기, 메모 열쇠, 중복 제거, 사진 글자 매칭이 모두 쓴다.
기준: '(주)'·'㈜'·'주식회사'·공백·기호를 빼고 소문자로 본다. ('이든파마' == '(주)이든파마')
"""
import difflib
import re

_STRIP = re.compile(r"\(주\)|㈜|주식회사|[^0-9A-Za-z가-힣]")
_SUFFIX_NUM = re.compile(r"\s*(?:\(\d+\)|\d+)\s*$")


def norm(text: str) -> str:
    """이름 비교용 정규화."""
    return _STRIP.sub("", (text or "")).lower()


def clean_pharma(name: str) -> str:
    """분류용으로 붙였던 끝 번호('명문제약 (2)', '명문제약2')를 떼어 낸다 ('(주)이든파마'는 그대로)."""
    return _SUFFIX_NUM.sub("", name or "").strip()


def same(a: str, b: str) -> bool:
    k = norm(a)
    return bool(k) and k == norm(b)


def hospital_key(name):
    """'라임비뇨기과' 와 '라임비뇨기과의원' 을 같은 병원으로 보는 기준: 공백·끝의 '의원' 제거."""
    k = re.sub(r"\s+", "", name or "")
    return k[:-2] if k.endswith("의원") and len(k) > 4 else k


def memo_key(hospital: str, pharma: str) -> str:
    """병원×제약사 메모의 열쇠. (제약사는 표기가 달라도, 병원은 '의원' 유무가 달라도 같은 열쇠)"""
    return f"{hospital_key(hospital)}|{norm(pharma)}"


def rekey_memo_key(key: str) -> str:
    """예전 방식(병원명 그대로)으로 저장된 열쇠를 현재 규칙으로 바꾼다."""
    h, sep, p = key.partition("|")
    return f"{hospital_key(h)}|{p}" if sep else key


def sort_key(name: str) -> str:
    """가나다순 정렬 기준 ((주)·기호 무시)."""
    return norm(name)


class NameBook:
    """알고 있는 이름들(정규화 이름 → 엑셀에서 가장 최근에 쓰인 표기)로 대표 표기를 고르고 비슷한 이름을 찾는다."""

    def __init__(self, latest=None):
        self.latest = dict(latest or {})

    @classmethod
    def from_names(cls, names_oldest_first):
        """오래된 것 → 최근 순으로 준 이름들에서, 같은 이름 그룹마다 가장 최근 표기를 대표로 삼는다."""
        latest = {}
        for n in names_oldest_first:
            k = norm(n)
            if k:
                latest[k] = n
        return cls(latest)

    def display(self, name: str, prefer=None) -> str:
        """대표 표기: prefer(사용자가 최근 저장한 표기) > 엑셀에서 가장 최근 표기 > 받은 이름 그대로."""
        k = norm(name)
        return (prefer or {}).get(k) or self.latest.get(k) or name

    def dedupe(self, names, prefer=None, drop_norms=(), sort=False):
        """같은 이름(norm 기준)은 하나만 남긴다. 순서는 유지(그룹의 첫 자리). drop_norms 그룹은 뺀다. sort면 가나다순."""
        seen, out = set(), []
        for n in names:
            k = norm(n)
            if not k or k in seen or k in drop_norms:
                continue
            seen.add(k)
            out.append(self.display(n, prefer))
        if sort:
            out.sort(key=sort_key)
        return out

    def closest(self, raw: str, prefer=None, favored_norms=(), threshold: float = 0.6):
        """사진에서 읽은 글자(raw)와 가장 비슷한 이름을 (대표 표기, 유사도)로. 없으면 (None, 0.0).
        favored_norms(예: 그 병원에서 처방이 나왔던 제약사)는 점수를 조금 더 쳐준다."""
        nr = norm(raw)
        if len(nr) < 2:
            return None, 0.0
        best, best_s, best_r = None, 0.0, 0.0
        for k in self.latest:
            r = difflib.SequenceMatcher(None, nr, k).ratio()
            s = r + (0.05 if k in favored_norms else 0.0)
            if r >= threshold and s > best_s:
                best, best_s, best_r = k, s, r
        if best is None:
            return None, 0.0
        return (prefer or {}).get(best) or self.latest[best], best_r
