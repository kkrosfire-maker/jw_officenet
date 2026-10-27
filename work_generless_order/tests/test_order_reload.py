"""저장된 주문을 불러와 고쳐 저장하는 흐름 테스트(DB는 임시 파일)."""
import tempfile
import unittest
from pathlib import Path

from app import db
from app.order import OrderEditSession, find_price_updates, line_from_saved
from app.order_log import month_usage, order_summaries


class OrderReloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        orig = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / "test.db"
        self.addCleanup(lambda: setattr(db, "DB_PATH", orig))
        db.init_db()
        self.needle_id = db.insert_item("니들", "23G 니들", "", "Needle 23G/100ea", "23G",
                                        "2026-10-01", 2000, 3000, "", "")

    def _save(self, order_id, date, qty, buy=2000, sell=3000):
        """main.OrderTab._save_order와 같은 순서로 DB에 쓴다."""
        if order_id is not None and db.reset_order(order_id, date):
            pass
        else:
            order_id = db.create_order(date)
        db.add_order_line(order_id, "23게이지", self.needle_id, qty, "Needle 23G/100ea", "23G",
                          buy, sell, "자동확인", "")
        return order_id

    def test_reload_and_edit_keeps_same_order_and_fixes_quota(self):
        order_id = self._save(None, "261027", 3)
        self.assertEqual(month_usage(db.order_log_rows(), 2026, 10)["니들"], 300)

        order, rows = db.get_order(order_id)
        self.assertEqual(order["order_date"], "261027")
        line = line_from_saved(rows[0], db.get_item(rows[0]["item_id"]))
        self.assertEqual(line.raw_text, "23G 니들")      # 화면엔 정식 품목명
        self.assertEqual(line.origin_text, "23게이지")    # 병원 원문은 그대로 보존
        self.assertEqual(line.quantity, 3)

        # 주문이 일부만 됐다 → 수량을 1로 고쳐 다시 저장
        again = self._save(order_id, "261027", 1)
        self.assertEqual(again, order_id)
        self.assertEqual(len(db.list_orders()), 1)
        self.assertEqual(month_usage(db.order_log_rows(), 2026, 10)["니들"], 100)
        self.assertEqual(order_summaries(db.order_log_rows())[order_id]["니들"], 100)

    def test_master_price_change_does_not_prompt_revert(self):
        order_id = self._save(None, "261027", 2, buy=1800, sell=2500)
        db.update_item_prices(self.needle_id, 2000, 3000)
        _, rows = db.get_order(order_id)
        line = line_from_saved(rows[0], db.get_item(self.needle_id))
        self.assertEqual((line.buy_price, line.sell_price), (1800, 2500))  # 그때 적용한 가격
        self.assertEqual(find_price_updates([line]), [])                    # 마스터 되돌리기 안 물음

    def test_deleted_order_leaves_quota_and_reset_falls_back(self):
        order_id = self._save(None, "261027", 2)
        db.delete_order(order_id)
        self.assertEqual(db.list_orders(), [])
        self.assertEqual(month_usage(db.order_log_rows(), 2026, 10)["니들"], 0)
        self.assertFalse(db.reset_order(order_id, "261027"))

    def test_line_without_master_item(self):
        row = {"raw_text": "없는품목", "quantity": 2, "requirement_text": "", "spec_text": "",
               "applied_buy": 0, "applied_sell": 0, "match_type": "수동", "remark": "메모"}
        line = line_from_saved(row, None)
        s = OrderEditSession()
        s.lines.append(line)
        self.assertEqual((line.raw_text, line.remark, line.item), ("없는품목", "메모", None))


if __name__ == "__main__":
    unittest.main()
