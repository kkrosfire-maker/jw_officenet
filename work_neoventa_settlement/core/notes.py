"""요율표 비고의 정산 제한 조건 해석.

핵심: 비고의 "O월 EDI"는 **처방월**을 뜻한다. 정산월이 아니다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .utils import two_digit_year_month

# '26년 3월 EDI까지', '26.07 EDI부터', '25.07월부터' 를 모두 잡는다.
_CLAUSE_RE = re.compile(
    r"(?P<y>\d{2})\s*(?:년|[.\-/])\s*(?P<m>\d{1,2})\s*월?\s*"
    r"(?:\s*EDI)?\s*(?:월)?\s*(?P<dir>까지|부터)"
)

_START_WORDS = ("정산가능", "정산재개", "정산 가능", "정산 재개")
_NEW_BAN_WORDS = ("신규금지", "신규 금지", "신규처금지", "신규처 금지")


@dataclass
class NoteRules:
    """비고에서 읽어낸 규칙."""

    raw: str = ""
    start_month: Optional[str] = None      # 이 처방월부터 정산 가능
    end_month: Optional[str] = None        # 이 처방월까지 정산 가능
    new_ban_from: Optional[str] = None     # 이 처방월부터 신규처 금지
    info: list[str] = field(default_factory=list)   # 해석하지 못한 참고 문구

    @property
    def has_rule(self) -> bool:
        return any((self.start_month, self.end_month, self.new_ban_from))


def parse_note(note: Optional[str]) -> NoteRules:
    """요율표 비고 한 칸을 해석한다. 여러 조건은 '/' 로 나뉜다."""
    rules = NoteRules(raw=(note or "").strip())
    if not rules.raw:
        return rules

    for clause in re.split(r"\s*/\s*|\n", rules.raw):
        clause = clause.strip()
        if not clause:
            continue
        matched = False
        for m in _CLAUSE_RE.finditer(clause):
            month = two_digit_year_month(int(m.group("y")), int(m.group("m")))
            direction = m.group("dir")
            if any(w in clause for w in _NEW_BAN_WORDS) and direction == "부터":
                rules.new_ban_from = month
                matched = True
            elif direction == "까지" and "정산" in clause:
                rules.end_month = month
                matched = True
            elif direction == "부터" and any(w in clause for w in _START_WORDS):
                rules.start_month = month
                matched = True
        if not matched:
            rules.info.append(clause)
    return rules


@dataclass
class Restriction:
    """한 행이 제한에 걸렸을 때의 설명."""

    kind: str        # 'END' | 'START' | 'NEW_BAN'
    message: str


def check_restrictions(
    rules: NoteRules,
    처방월: Optional[str],
    *,
    is_new_client: bool = False,
) -> list[Restriction]:
    """처방월 기준으로 제한 위반을 찾는다.

    is_new_client: 이 병원 × 이 제품이 신규처인지 (신규금지 판정에만 쓴다)
    """
    hits: list[Restriction] = []
    if not 처방월:
        return hits

    if rules.end_month and 처방월 > rules.end_month:
        hits.append(
            Restriction(
                "END",
                f"처방월 {처방월} 이 정산 종료월 {rules.end_month} 을 넘었습니다.",
            )
        )
    if rules.start_month and 처방월 < rules.start_month:
        hits.append(
            Restriction(
                "START",
                f"처방월 {처방월} 이 정산 시작월 {rules.start_month} 보다 앞섭니다.",
            )
        )
    if rules.new_ban_from and 처방월 >= rules.new_ban_from and is_new_client:
        hits.append(
            Restriction(
                "NEW_BAN",
                f"{rules.new_ban_from} 처방월부터 신규처 금지인데 이 병원은 신규처입니다.",
            )
        )
    return hits
