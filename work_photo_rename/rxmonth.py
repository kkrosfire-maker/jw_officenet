"""처방월 모듈 — '10월'·'08월'·10 처럼 흩어져 쓰이던 월 표기와, 처방 연도 계산을 한곳에 모은다.

  - 월 표기: '10월', '08월', '8' 모두 같은 달로 본다 (parse / same / label)
  - 기본 처방월 = 지난달, 월 → 처방 연도 (default_month / year_for)
  - 엑셀 한 줄의 처방 (연도, 월): 연도 열이 입력 연도로 적힌 줄(12월분을 2월에 입력)은 전년도로 본다 (period_of)
  - 최근 N개월 범위 (recent_periods)
화면(main)과 장부(ledger)가 같은 규칙을 쓰도록, 월·연도에 관한 규칙은 여기에만 둔다.
"""
import datetime
import re

_NUM = re.compile(r"\d+")


def parse(text):
    """'10월'·'08월'·'8'·10 → 정수 월(1~12). 읽을 수 없으면 None."""
    m = _NUM.match(str(text if text is not None else "").strip())
    v = int(m.group()) if m else None
    return v if v and 1 <= v <= 12 else None


def label(month: int) -> str:
    return f"{month}월"


def same(a, b) -> bool:
    """'8월' 과 '08월' 은 같은 달. 어느 쪽이든 읽을 수 없으면 False."""
    pa = parse(a)
    return pa is not None and pa == parse(b)


def default_month(today=None) -> int:
    """통계는 보통 다음 달에 정리하므로 기본 처방월은 '지난달'."""
    t = today or datetime.date.today()
    return (t.month - 2) % 12 + 1


def year_for(month: int, today=None) -> int:
    """처방월(정수)의 처방 연도: 올해 달 수 이하면 올해, 아니면 작년."""
    t = today or datetime.date.today()
    return t.year if month <= t.month else t.year - 1


def period_of(year, rx_month, input_month=None):
    """엑셀 한 줄의 처방 (연도, 월). 읽을 수 없으면 None.
    연도 열이 입력(정산) 연도로 적힌 줄이 있어서, 처방월이 입력월보다 크면(12월분을 2월에 입력) 전년도로 본다."""
    rx = parse(rx_month)
    if rx is None or not isinstance(year, int):
        return None
    im = parse(input_month)
    if im is not None and rx > im:
        year -= 1
    return year, rx


def recent_periods(latest, n=3):
    """latest=(연도, 월) 부터 거슬러 n개월의 (연도, 월) 집합. latest가 None이면 빈 집합."""
    if not latest:
        return set()
    y, m = latest
    out = set()
    for _ in range(n):
        out.add((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out
