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

    def apply_match(self, item: dict, match_type: str, origin_text: str | None = None) -> None:
        """매칭 결과를 라인에 반영한다(신규 생성/재매칭 공통 경로)."""
        if origin_text is not None:
            self.origin_text = origin_text
        self.raw_text = item.get("order_name", self.raw_text)
        self.item = item
        self.requirement_text = item.get("product_name", "")
        self.spec_text = item.get("spec", "")
        self.buy_price = item.get("buy_price", 0)
        self.sell_price = item.get("sell_price", 0)
        self.match_type = match_type

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


class OrderEditSession:
    """주문 라인 목록의 편집 상태와 전이 규칙.

    tkinter Treeview/위젯을 전혀 몰라도 되는 순수 로직만 둬서, OrderTab은
    이 세션에 위임하는 얇은 오케스트레이션(화면 렌더링·다이얼로그 호출)만 맡는다.
    """

    SORT_KEYS = {
        "raw": lambda line: line.raw_text,
        "qty": lambda line: line.quantity,
        "req": lambda line: line.requirement_text,
        "spec": lambda line: line.spec_text,
        "buy": lambda line: line.buy_price,
        "sell": lambda line: line.sell_price,
        "remark": lambda line: line.remark,
    }

    def __init__(self):
        self.lines: list[OrderLine] = []
        self.pending_qty = "1"
        self.sort_col: str | None = None
        self.sort_reverse = False

    def add_line(self, raw_text: str, quantity: float, item: dict, match_type: str) -> OrderLine:
        line = OrderLine(raw_text=raw_text, item=item, quantity=quantity)
        line.apply_match(item, match_type, origin_text=raw_text)
        self.lines.append(line)
        return line

    def rematch_line(self, idx: int, new_raw_text: str, item: dict, match_type: str) -> OrderLine:
        line = self.lines[idx]
        line.apply_match(item, match_type, origin_text=new_raw_text)
        return line

    def delete_line(self, idx: int) -> None:
        del self.lines[idx]

    def set_quantity(self, idx: int, text: str) -> str | None:
        """성공하면 None, 실패하면 사용자에게 보여줄 오류 메시지를 반환한다."""
        try:
            self.lines[idx].quantity = float(text)
        except ValueError:
            return "수량은 숫자여야 합니다."
        return None

    def set_price(self, idx: int, field: str, text: str) -> str | None:
        """field는 'buy' 또는 'sell'. 성공하면 None, 실패하면 오류 메시지를 반환한다."""
        try:
            value = float(text)
        except ValueError:
            return ("매입가" if field == "buy" else "매출가") + "는 숫자여야 합니다."
        if field == "buy":
            self.lines[idx].buy_price = value
        else:
            self.lines[idx].sell_price = value
        return None

    def set_remark(self, idx: int, text: str) -> None:
        self.lines[idx].remark = text

    def sort(self, col: str) -> None:
        if self.sort_col == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col = col
            self.sort_reverse = False
        self.lines.sort(key=self.SORT_KEYS[col], reverse=self.sort_reverse)
