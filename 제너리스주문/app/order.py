"""주문(Order) 도메인 모델 — 품목 매칭 결과를 담는 OrderLine과 저장 전 검증 규칙.

Tkinter나 DB에 의존하지 않는 순수 로직만 둔다.
"""
import datetime as dt

from app.config import STALE_PRICE_DAYS

TAG_DANGER = "danger"
TAG_WARNING = "warning"
TAG_NORMAL = "normal"


def is_stale(base_date: str | None) -> bool:
    if not base_date:
        return True
    try:
        d = dt.date.fromisoformat(base_date)
    except ValueError:
        return True
    return (dt.date.today() - d).days > STALE_PRICE_DAYS


class OrderLine:
    def __init__(self, raw_text, item, quantity=1, requirement_text="", spec_text="",
                 buy_price=0, sell_price=0, match_type="수동", remark=""):
        self.raw_text = raw_text
        self.origin_text = raw_text  # 병원이 실제로 표현한 원문(별칭 학습/이력용, 화면 표시는 raw_text 사용)
        self.item = item  # dict 또는 None
        self.quantity = quantity
        self.requirement_text = requirement_text
        self.spec_text = spec_text
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.match_type = match_type
        self.remark = remark

    def is_margin_danger(self) -> bool:
        return bool(self.buy_price and self.sell_price and self.buy_price > self.sell_price)

    def is_price_stale(self) -> bool:
        return not self.item or is_stale(self.item.get("base_date"))

    def tag(self):
        if self.is_margin_danger():
            return TAG_DANGER
        if self.is_price_stale():
            return TAG_WARNING
        return TAG_NORMAL

    def price_changed_from_master(self) -> bool:
        """마스터 DB 가격과 다르게 수정됐는지(신규 등록 품목은 비교 대상 없음)."""
        if not self.item:
            return False
        return self.buy_price != self.item.get("buy_price") or self.sell_price != self.item.get("sell_price")

    def as_export_dict(self):
        return {
            "raw_text": self.raw_text,
            "quantity": self.quantity,
            "requirement_text": self.requirement_text,
            "spec_text": self.spec_text,
            "buy_price": self.buy_price,
            "sell_price": self.sell_price,
        }


def find_danger_lines(lines: list[OrderLine]) -> list[OrderLine]:
    """역마진(매입가 > 매출가) 라인을 찾는다."""
    return [line for line in lines if line.is_margin_danger()]


def find_price_updates(lines: list[OrderLine]) -> list[OrderLine]:
    """마스터 DB 단가와 달라져 저장 시 갱신이 필요한 라인을 찾는다."""
    return [line for line in lines if line.price_changed_from_master()]
