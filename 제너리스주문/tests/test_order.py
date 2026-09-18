"""app.order의 순수 로직(OrderLine, OrderEditSession) 테스트.

tkinter/DB 없이 돌아가야 하는 부분만 검증한다.
"""
import unittest

from app.order import OrderEditSession, OrderLine, find_danger_lines, find_price_updates


def make_item(item_id=1, order_name="23G needle", buy_price=2310, sell_price=2800, base_date=None):
    return {
        "id": item_id, "order_name": order_name, "product_name": "표준품목",
        "spec": "23G 1\"", "buy_price": buy_price, "sell_price": sell_price,
        "base_date": base_date,
    }


class OrderLineApplyMatchTest(unittest.TestCase):
    def test_apply_match_fills_fields_from_item(self):
        line = OrderLine(raw_text="니들23", item=None)
        item = make_item()
        line.apply_match(item, "자동확인", origin_text="니들23")

        self.assertEqual(line.item, item)
        self.assertEqual(line.raw_text, "23G needle")
        self.assertEqual(line.origin_text, "니들23")
        self.assertEqual(line.requirement_text, "표준품목")
        self.assertEqual(line.buy_price, 2310)
        self.assertEqual(line.sell_price, 2800)
        self.assertEqual(line.match_type, "자동확인")

    def test_apply_match_keeps_previous_origin_text_when_not_given(self):
        line = OrderLine(raw_text="니들23", item=None)
        line.origin_text = "니들23(손글씨)"
        line.apply_match(make_item(), "수동선택")
        self.assertEqual(line.origin_text, "니들23(손글씨)")


class OrderEditSessionTest(unittest.TestCase):
    def test_add_line_appends_and_returns_line(self):
        session = OrderEditSession()
        line = session.add_line("니들23", 2, make_item(), "자동확인")
        self.assertEqual(session.lines, [line])
        self.assertEqual(line.quantity, 2)
        self.assertEqual(line.origin_text, "니들23")

    def test_rematch_line_replaces_item_in_place(self):
        session = OrderEditSession()
        session.add_line("니들23", 1, make_item(item_id=1), "자동확인")
        new_item = make_item(item_id=2, order_name="21G needle")
        session.rematch_line(0, "니들21", new_item, "수동선택")
        self.assertEqual(session.lines[0].item, new_item)
        self.assertEqual(session.lines[0].origin_text, "니들21")
        self.assertEqual(session.lines[0].match_type, "수동선택")

    def test_delete_line_removes_by_index(self):
        session = OrderEditSession()
        session.add_line("a", 1, make_item(item_id=1), "자동확인")
        session.add_line("b", 1, make_item(item_id=2), "자동확인")
        session.delete_line(0)
        self.assertEqual(len(session.lines), 1)
        self.assertEqual(session.lines[0].item["id"], 2)

    def test_set_quantity_accepts_valid_number(self):
        session = OrderEditSession()
        session.add_line("a", 1, make_item(), "자동확인")
        error = session.set_quantity(0, "3.5")
        self.assertIsNone(error)
        self.assertEqual(session.lines[0].quantity, 3.5)

    def test_set_quantity_rejects_non_numeric(self):
        session = OrderEditSession()
        session.add_line("a", 1, make_item(), "자동확인")
        error = session.set_quantity(0, "abc")
        self.assertIsNotNone(error)
        self.assertEqual(session.lines[0].quantity, 1)  # 변경되지 않음

    def test_set_price_updates_buy_or_sell(self):
        session = OrderEditSession()
        session.add_line("a", 1, make_item(), "자동확인")
        self.assertIsNone(session.set_price(0, "buy", "1000"))
        self.assertIsNone(session.set_price(0, "sell", "1500"))
        self.assertEqual(session.lines[0].buy_price, 1000)
        self.assertEqual(session.lines[0].sell_price, 1500)

    def test_set_price_rejects_non_numeric_with_field_specific_message(self):
        session = OrderEditSession()
        session.add_line("a", 1, make_item(), "자동확인")
        error = session.set_price(0, "sell", "abc")
        self.assertIn("매출가", error)

    def test_sort_toggles_direction_on_repeated_column(self):
        session = OrderEditSession()
        session.add_line("b", 2, make_item(item_id=1), "자동확인")
        session.add_line("a", 1, make_item(item_id=2), "자동확인")

        session.sort("qty")
        self.assertEqual([l.quantity for l in session.lines], [1, 2])
        self.assertFalse(session.sort_reverse)

        session.sort("qty")  # 같은 컬럼 재클릭 → 방향 토글
        self.assertEqual([l.quantity for l in session.lines], [2, 1])
        self.assertTrue(session.sort_reverse)


class SaveGateTest(unittest.TestCase):
    def test_find_danger_lines_flags_margin_below_zero(self):
        session = OrderEditSession()
        session.add_line("a", 1, make_item(buy_price=3000, sell_price=2000), "자동확인")
        session.add_line("b", 1, make_item(buy_price=1000, sell_price=2000), "자동확인")
        danger = find_danger_lines(session.lines)
        self.assertEqual(len(danger), 1)
        self.assertEqual(danger[0].buy_price, 3000)

    def test_find_price_updates_detects_changed_price(self):
        session = OrderEditSession()
        session.add_line("a", 1, make_item(item_id=1, buy_price=1000, sell_price=2000), "자동확인")
        session.set_price(0, "buy", "1200")
        updates = find_price_updates(session.lines)
        self.assertEqual(len(updates), 1)


if __name__ == "__main__":
    unittest.main()
