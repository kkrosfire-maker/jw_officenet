"""병원 주문 원문 텍스트 ↔ 마스터 품목 유사도 매칭."""
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app import db
from app.config import CANDIDATE_THRESHOLD, MAX_CANDIDATES

_STRIP_RE = re.compile(r"[\s\-_/()\.]")


def normalize(text: str) -> str:
    text = (text or "").strip().lower()
    text = _STRIP_RE.sub("", text)
    return text


@dataclass
class Candidate:
    item: dict
    matched_alias: str
    score: float


def _score(query_norm: str, alias_norm: str) -> float:
    if not query_norm or not alias_norm:
        return 0.0
    ratio = SequenceMatcher(None, query_norm, alias_norm).ratio()
    if query_norm == alias_norm:
        return 1.0
    if query_norm in alias_norm or alias_norm in query_norm:
        # 포함 관계면 가중치를 더 준다(짧은 쪽 기준 포함 비율도 반영)
        shorter, longer = sorted((query_norm, alias_norm), key=len)
        containment = len(shorter) / len(longer)
        ratio = max(ratio, 0.75 + 0.2 * containment)
    return ratio


def find_candidates(query_text: str, items_with_aliases=None) -> list[Candidate]:
    """query_text와 가장 유사한 품목 후보를 점수 내림차순으로 반환."""
    if items_with_aliases is None:
        items_with_aliases = db.all_items_with_aliases()

    query_norm = normalize(query_text)
    best_per_item: dict[int, Candidate] = {}

    for item, aliases in items_with_aliases:
        candidates_text = [item["order_name"], *aliases]
        best_score = 0.0
        best_alias = item["order_name"]
        for alias in candidates_text:
            s = _score(query_norm, normalize(alias))
            if s > best_score:
                best_score = s
                best_alias = alias
        if best_score >= CANDIDATE_THRESHOLD:
            best_per_item[item["id"]] = Candidate(item=item, matched_alias=best_alias, score=best_score)

    ranked = sorted(best_per_item.values(), key=lambda c: c.score, reverse=True)
    return ranked[:MAX_CANDIDATES]
