"""공통 유틸: 월 표기, 이름 정규화, 숫자 파싱."""
from __future__ import annotations

import datetime as _dt
import os
import re
from typing import Optional

_MONTH_RE = re.compile(r"^(\d{4})[-/.](\d{1,2})")


def parse_month(value) -> Optional[str]:
    """'2026-07', datetime, '2026-07-01' 등을 'YYYY-MM'으로 바꾼다."""
    if value is None or value == "":
        return None
    if isinstance(value, (_dt.datetime, _dt.date)):
        return f"{value.year:04d}-{value.month:02d}"
    text = str(value).strip()
    m = _MONTH_RE.match(text)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    m = re.match(r"^(\d{2})[-/.](\d{1,2})$", text)
    if m:
        return f"{2000 + int(m.group(1)):04d}-{int(m.group(2)):02d}"
    m = re.match(r"^(\d{4})(\d{2})$", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


def month_to_date(month: str) -> _dt.datetime:
    """'YYYY-MM' → 해당 월 1일."""
    y, m = month.split("-")
    return _dt.datetime(int(y), int(m), 1)


def month_shift(month: str, delta: int) -> str:
    y, m = (int(x) for x in month.split("-"))
    total = y * 12 + (m - 1) + delta
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def two_digit_year_month(year2: int, month: int) -> str:
    return f"{2000 + year2:04d}-{month:02d}"


_NAME_STRIP_RE = re.compile(r"\[[^\]]*\]|_?\([^)]*\)|\s+")


def normalize_name(name) -> str:
    """제품명 비교용 정규화: [삭제된 제품], (성분), _(용량), 공백 제거."""
    if name is None:
        return ""
    text = str(name)
    prev = None
    while prev != text:
        prev = text
        text = _NAME_STRIP_RE.sub("", text)
    return text.strip().lower()


def suggest_final_name(rate_product_name) -> str:
    """요율표 제품명 → 최종 제품명 추천. 성분 괄호와 공백을 뺀다.

    예: '오바램정 100mg (실데나필)' → '오바램정100mg'
    """
    if rate_product_name is None:
        return ""
    text = str(rate_product_name)
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\[[^\]]*\]|_?\([^)]*\)", "", text)
    return re.sub(r"\s+", "", text).strip()


def clean_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def percent_text(value, digits: int = 2) -> str:
    """0.03 → '3%'. 소수점 뒤 0 은 떼고 보여준다."""
    if value is None or value == "":
        return ""
    try:
        number = float(value) * 100
    except (TypeError, ValueError):
        return str(value)
    text = f"{number:.{digits}f}".rstrip("0").rstrip(".")
    return f"{text or '0'}%"


def yymm(month: str) -> str:
    """'2026-09' → '2609'."""
    year, mon = month.split("-")
    return f"{year[2:]}{mon}"


def desktop_dir() -> "Path":
    """바탕화면 경로. OneDrive 로 옮겨진 경우도 레지스트리에서 찾는다."""
    from pathlib import Path as _Path

    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        )
        try:
            value, _ = winreg.QueryValueEx(key, "Desktop")
        finally:
            winreg.CloseKey(key)
        path = _Path(os.path.expandvars(value))
        if path.is_dir():
            return path
    except Exception:  # noqa: BLE001 - 윈도우가 아니거나 레지스트리를 못 읽는 경우
        pass
    fallback = _Path.home() / "Desktop"
    return fallback if fallback.is_dir() else _Path.home()


def code_key(value) -> str:
    """보험코드를 문자열 키로. 앞자리 0을 유지하고 공백을 없앤다."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def to_number(value):
    """엑셀 셀 값을 숫자로. 못 바꾸면 None."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    return int(num) if num.is_integer() else num


_AMOUNT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(억|만)?\s*원?")


def parse_threshold(raw) -> tuple[Optional[int], bool]:
    """최소 인정금액 문자열을 (금액, 확인필요) 로 바꾼다.

    '10만원' → (100000, False) / '없음' → (None, False) / 애매하면 (추정값, True)
    """
    text = clean_str(raw)
    if not text:
        return None, True
    if text in ("없음", "-"):
        return None, False
    m = _AMOUNT_RE.search(text)
    if not m:
        return None, True
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "만":
        value = int(num * 10_000)
    elif unit == "억":
        value = int(num * 100_000_000)
    else:
        value = int(num)
    # '10만원 (26.04부터)', '1만원 이상' 처럼 조건이 붙은 값은 사용자 확인이 필요하다.
    leftover = (text[: m.start()] + text[m.end():]).strip()
    return value, bool(leftover)
