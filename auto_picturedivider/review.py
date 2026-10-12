"""작업 후 사용자가 직접 확인해야 하는 항목(미매칭·유사 매칭·변환 실패 등)의 공통 형식.

photo_sort / pharma_zip 이 ReviewItem 을 만들고, GUI 는 format_review() 결과를 로그에 찍기만 한다.
"""
from dataclasses import dataclass

UNMATCHED = "미매칭"
FUZZY = "유사 매칭"
CONVERT_FAILED = "변환 실패"
PHARMA_UNKNOWN = "제약사 미확인"

_TAGS = {FUZZY: "fuzzy"}  # 나머지는 모두 "fail"


@dataclass(frozen=True)
class ReviewItem:
    kind: str
    filename: str
    detail: str = ""


def format_review(items: list[ReviewItem]) -> list[tuple[str, str]]:
    """(로그 문장, 로그 태그) 목록. 항목이 없으면 빈 목록."""
    lines: list[tuple[str, str]] = []
    for kind in dict.fromkeys(i.kind for i in items):
        group = [i for i in items if i.kind == kind]
        tag = _TAGS.get(kind, "fail")
        lines.append((f"\n[확인 필요] {kind} {len(group)}개", tag))
        for i in group:
            suffix = f"  ({i.detail})" if i.detail else ""
            lines.append((f"  ✗  {i.filename}{suffix}", tag))
    return lines
