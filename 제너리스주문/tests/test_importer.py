"""마스터 엑셀 재불러오기(병합/전체교체) 동작 테스트.

임시 DB와 임시 엑셀만 쓰므로 실제 data/genelis.db는 건드리지 않는다.
"""
import tempfile
import unittest
from pathlib import Path

import openpyxl

from app import config, db, importer


def write_master_xlsx(path: Path, rows: list[dict]) -> None:
    """importer가 읽는 컬럼 위치대로 최소한의 마스터 엑셀을 만든다."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = config.SOURCE_MASTER_SHEET
    ws.append(["항목", "제너리스주문명", "제조사", "제품명", "규격", "기준일자", "매입가", "매출가",
               "", "", "", "급여구분", "", "비고", "별칭2", "별칭3"])
    for row in rows:
        ws.append([
            row.get("category", ""), row["order_name"], row.get("manufacturer", ""),
            row.get("product_name", ""), row.get("spec", ""), row.get("base_date", "2026-01-01"),
            row.get("buy", 1000), row.get("sell", 2000),
            "", "", "", "", "", "", row.get("alias", ""), "",
        ])
    wb.save(path)


class MasterSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp_dir = Path(self.tmp.name)

        self._orig_db_path = db.DB_PATH
        db.DB_PATH = tmp_dir / "test.db"
        self.addCleanup(lambda: setattr(db, "DB_PATH", self._orig_db_path))
        db.init_db()

        self.xlsx = tmp_dir / "master.xlsx"
        write_master_xlsx(self.xlsx, [
            {"order_name": "23G needle", "manufacturer": "성심", "buy": 2310, "sell": 2800},
            {"order_name": "2*2 거즈", "manufacturer": "수성", "buy": 1880, "sell": 2300},
        ])

    def test_first_sync_registers_all_rows(self):
        result = importer.sync_master(self.xlsx)
        self.assertEqual(result, {"added": 2, "updated": 0, "total": 2})
        self.assertEqual(len(db.all_items()), 2)

    def test_merge_updates_existing_and_adds_new(self):
        importer.sync_master(self.xlsx)
        item = db.find_item_by_order_name("23G needle")
        db.add_alias(item["id"], "니들23")  # 사용자가 학습시킨 별칭

        write_master_xlsx(self.xlsx, [
            {"order_name": "23G needle", "manufacturer": "성심메디칼", "buy": 2400, "sell": 2900},
            {"order_name": "2*2 거즈", "manufacturer": "수성", "buy": 1880, "sell": 2300},
            {"order_name": "3way", "manufacturer": "협성", "buy": 12300, "sell": 13200},
        ])
        result = importer.sync_master(self.xlsx)

        self.assertEqual(result, {"added": 1, "updated": 2, "total": 3})
        updated = db.find_item_by_order_name("23G needle")
        self.assertEqual(updated["manufacturer"], "성심메디칼")
        self.assertEqual(updated["buy_price"], 2400)
        self.assertIn("니들23", db.get_aliases(updated["id"]))  # 학습된 별칭 보존
        self.assertEqual(len(db.get_price_history(updated["id"])), 1)

    def test_replace_wipes_previous_items_and_aliases(self):
        importer.sync_master(self.xlsx)
        old_item = db.find_item_by_order_name("23G needle")
        db.add_alias(old_item["id"], "니들23")

        write_master_xlsx(self.xlsx, [{"order_name": "34G needle", "buy": 60500, "sell": 79500}])
        result = importer.sync_master(self.xlsx, replace=True)

        self.assertEqual(result, {"added": 1, "updated": 0, "total": 1})
        names = [i["order_name"] for i in db.all_items()]
        self.assertEqual(names, ["34G needle"])
        self.assertEqual(db.get_aliases(old_item["id"]), [])

    def test_remembered_master_path_is_used(self):
        importer.remember_master_path(self.xlsx)
        self.assertEqual(importer.current_master_path(), self.xlsx)


class ItemFieldUpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / "test.db"
        self.addCleanup(lambda: setattr(db, "DB_PATH", self._orig_db_path))
        db.init_db()
        self.item_id = db.insert_item(
            category="니들", order_name="23G needle", manufacturer="성심", product_name="일회용니들",
            spec='23G 1"', base_date="2026-01-01", buy_price=2310, sell_price=2800,
            welfare_type="", note="",
        )

    def test_update_item_fields_changes_only_known_columns(self):
        db.update_item_fields(self.item_id, manufacturer="성심메디칼", buy_price=99999)
        item = db.get_item(self.item_id)
        self.assertEqual(item["manufacturer"], "성심메디칼")
        self.assertEqual(item["buy_price"], 2310)  # 가격은 이력이 남는 경로로만 바뀐다

    def test_settings_roundtrip(self):
        self.assertIsNone(db.get_setting("master_xlsx_path"))
        db.set_setting("master_xlsx_path", r"C:\some\file.xlsx")
        db.set_setting("master_xlsx_path", r"C:\other\file.xlsx")
        self.assertEqual(db.get_setting("master_xlsx_path"), r"C:\other\file.xlsx")


if __name__ == "__main__":
    unittest.main()
