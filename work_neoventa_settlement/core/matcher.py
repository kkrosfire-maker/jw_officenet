"""3단계 제품 매칭.

1. 보험코드(또는 이전 보험코드)로 찾는다
2. lawdata 약제명이 별칭 목록에 있는지 본다 → PRODUCT_CODE_CHANGED
3. 비슷한 이름을 찾는다 → PRODUCT_RENAMED
4. 그래도 없으면 NEW_PRODUCT
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .master import Product, ProductMaster
from .utils import code_key

MATCH_EXACT = "EXACT"
MATCH_CODE_CHANGED = "PRODUCT_CODE_CHANGED"
MATCH_RENAMED = "PRODUCT_RENAMED"
MATCH_NEW = "NEW_PRODUCT"


@dataclass
class MatchResult:
    kind: str
    product: Optional[Product] = None
    candidates: list[tuple[Product, float]] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.kind != MATCH_EXACT


def match(master: ProductMaster, 보험코드: str, 약제명: str) -> MatchResult:
    code = code_key(보험코드)

    product = master.by_code(code)
    if product is not None:
        return MatchResult(MATCH_EXACT, product)

    product = master.by_alias(약제명)
    if product is not None:
        return MatchResult(MATCH_CODE_CHANGED, product)

    candidates = master.similar(약제명)
    if candidates:
        return MatchResult(MATCH_RENAMED, candidates[0][0], candidates)

    return MatchResult(MATCH_NEW)
