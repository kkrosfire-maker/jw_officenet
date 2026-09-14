"""기존 엑셀 마스터 파일을 DB로 1회성 이관."""
import datetime as dt

import openpyxl

from app import db
from app.config import SOURCE_MASTER_SHEET, SOURCE_MASTER_XLSX

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


def import_master(xlsx_path=None) -> int:
    """마스터 엑셀을 읽어 items/aliases 테이블을 채운다. 반환값: 등록된 품목 수."""
    xlsx_path = xlsx_path or SOURCE_MASTER_XLSX
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb[SOURCE_MASTER_SHEET]

    rows = list(ws.iter_rows(min_row=2, values_only=True))
    count = 0
    for row in rows:
        order_name = _norm(_cell(row, COL_ORDER_NAME))
        if not order_name:
            continue

        aliases = []
        for idx in (COL_ALIAS2, COL_ALIAS3):
            alt = _norm(_cell(row, idx))
            if alt and alt != order_name:
                aliases.append(alt)

        db.insert_item(
            category=_norm(_cell(row, COL_CATEGORY)),
            order_name=order_name,
            manufacturer=_norm(_cell(row, COL_MANUFACTURER)),
            product_name=_norm(_cell(row, COL_PRODUCT_NAME)),
            spec=_norm(_cell(row, COL_SPEC)),
            base_date=_to_iso_date(_cell(row, COL_BASE_DATE)),
            buy_price=_cell(row, COL_BUY) or 0,
            sell_price=_cell(row, COL_SELL) or 0,
            welfare_type=_norm(_cell(row, COL_WELFARE)),
            note=_norm(_cell(row, COL_NOTE)),
            aliases=aliases,
        )
        count += 1
    return count


if __name__ == "__main__":
    db.init_db()
    if db.is_empty():
        n = import_master()
        print(f"{n}개 품목을 마스터 DB로 이관했습니다.")
    else:
        print("DB에 이미 데이터가 있어 이관을 건너뜁니다.")
