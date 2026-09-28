"""엑셀 마스터 파일을 DB로 이관/갱신."""
import datetime as dt
from pathlib import Path

import openpyxl

from app import db
from app.config import MASTER_PATH_SETTING, SOURCE_MASTER_SHEET, SOURCE_MASTER_XLSX

# 시트 컬럼 인덱스(0-based) — 01.제너리스_주문 최종.xlsx > 품목별 단가 시트 헤더 기준
COL_CATEGORY = 0
COL_ORDER_NAME = 1
COL_MANUFACTURER = 2
COL_PRODUCT_NAME = 3
COL_SPEC = 4
COL_BASE_DATE = 5
COL_BUY = 6
COL_SELL = 7
COL_WELFARE = 11
COL_NOTE = 13
COL_ALIAS2 = 14  # 제너리스주문명 (두번째)
COL_ALIAS3 = 15  # 품목자료병합


def _cell(row, idx):
    return row[idx] if idx < len(row) else None


def _norm(v):
    if v is None:
        return ""
    return str(v).strip()


def _to_iso_date(v):
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    return _norm(v) or None


def current_master_path() -> Path:
    """현재 사용 중인 마스터 엑셀 경로(사용자가 교체했으면 그 경로)."""
    saved = db.get_setting(MASTER_PATH_SETTING)
    return Path(saved) if saved else SOURCE_MASTER_XLSX


def remember_master_path(xlsx_path) -> None:
    db.set_setting(MASTER_PATH_SETTING, str(Path(xlsx_path)))


def _open_sheet(xlsx_path):
    """마스터 시트를 연다. 지정한 시트가 없으면 첫 시트를 쓴다."""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    if SOURCE_MASTER_SHEET in wb.sheetnames:
        return wb[SOURCE_MASTER_SHEET]
    return wb[wb.sheetnames[0]]


def read_master_rows(xlsx_path) -> list[dict]:
    """마스터 엑셀을 품목 dict 목록으로 읽는다(DB에 쓰지 않는 순수 파싱)."""
    ws = _open_sheet(xlsx_path)
    parsed = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        order_name = _norm(_cell(row, COL_ORDER_NAME))
        if not order_name:
            continue
        aliases = []
        for idx in (COL_ALIAS2, COL_ALIAS3):
            alt = _norm(_cell(row, idx))
            if alt and alt != order_name:
                aliases.append(alt)
        parsed.append({
            "category": _norm(_cell(row, COL_CATEGORY)),
            "order_name": order_name,
            "manufacturer": _norm(_cell(row, COL_MANUFACTURER)),
            "product_name": _norm(_cell(row, COL_PRODUCT_NAME)),
            "spec": _norm(_cell(row, COL_SPEC)),
            "base_date": _to_iso_date(_cell(row, COL_BASE_DATE)),
            "buy_price": _cell(row, COL_BUY) or 0,
            "sell_price": _cell(row, COL_SELL) or 0,
            "welfare_type": _norm(_cell(row, COL_WELFARE)),
            "note": _norm(_cell(row, COL_NOTE)),
            "aliases": aliases,
        })
    return parsed


def sync_master(xlsx_path, replace: bool = False) -> dict:
    """마스터 엑셀로 DB를 갱신한다.

    replace=False(병합): 제너리스주문명이 같은 품목은 내용/단가만 갱신하고,
      없는 품목은 새로 등록한다. 학습된 별칭·가격 이력이 보존된다.
    replace=True(전체 교체): 기존 품목을 모두 지우고 엑셀 내용으로 다시 만든다.

    반환값: {"added": n, "updated": n, "total": n}
    """
    rows = read_master_rows(xlsx_path)

    if replace:
        db.delete_all_items()
        for parsed in rows:
            db.insert_item(**parsed)
        return {"added": len(rows), "updated": 0, "total": len(rows)}

    added = updated = 0
    for parsed in rows:
        existing = db.find_item_by_order_name(parsed["order_name"])
        if existing is None:
            db.insert_item(**parsed)
            added += 1
            continue

        item_id = existing["id"]
        db.update_item_fields(
            item_id,
            category=parsed["category"], manufacturer=parsed["manufacturer"],
            product_name=parsed["product_name"], spec=parsed["spec"],
            welfare_type=parsed["welfare_type"], note=parsed["note"],
        )
        if parsed["buy_price"] != existing["buy_price"] or parsed["sell_price"] != existing["sell_price"]:
            db.update_item_prices(item_id, parsed["buy_price"], parsed["sell_price"],
                                  memo="마스터 엑셀 재불러오기")
        elif parsed["base_date"]:
            db.update_item_fields(item_id, base_date=parsed["base_date"])
        for alias in parsed["aliases"]:
            db.add_alias(item_id, alias)
        updated += 1

    return {"added": added, "updated": updated, "total": len(rows)}


if __name__ == "__main__":
    db.init_db()
    if db.is_empty():
        n = sync_master(current_master_path())["total"]
        print(f"{n}개 품목을 마스터 DB로 이관했습니다.")
    else:
        print("DB에 이미 데이터가 있어 이관을 건너뜁니다.")
