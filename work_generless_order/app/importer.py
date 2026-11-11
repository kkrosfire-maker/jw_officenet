"""엑셀 마스터 파일을 DB로 이관/갱신."""
import copy
import datetime as dt
import os
import re
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


def append_item_to_master(xlsx_path, *, category, order_name, manufacturer, product_name, spec,
                          base_date, buy_price, sell_price, welfare_type="", note="") -> int:
    """마스터 엑셀의 품목 시트 맨 아래에 품목 한 줄을 추가해 파일에 저장한다. 추가된 행 번호를 반환.

    - 마지막 데이터 행의 서식을 그대로 복사하고 이익금액·이익률·마진율 수식을 채운다.
    - 요약 시트의 '품목별 단가'!...$마지막행 범위 수식과 필터·드롭다운 범위도 새 행까지 늘린다.
    - 엑셀로 파일이 열려 있으면 PermissionError, 같은 제너리스주문명이 이미 있으면 ValueError.
    - 임시 파일에 먼저 저장한 뒤 교체하므로 중간에 실패해도 원본이 깨지지 않는다.
    """
    xlsx_path = Path(xlsx_path)
    with open(xlsx_path, "r+b"):  # 엑셀이 잠가 둔 파일이면 여기서 PermissionError
        pass

    wb = openpyxl.load_workbook(xlsx_path)  # 수식을 보존하려고 data_only 사용 안 함
    ws = wb[SOURCE_MASTER_SHEET] if SOURCE_MASTER_SHEET in wb.sheetnames else wb[wb.sheetnames[0]]

    last = ws.max_row
    while last > 1 and not _norm(ws.cell(last, COL_ORDER_NAME + 1).value):
        last -= 1
    for r in range(2, last + 1):
        if _norm(ws.cell(r, COL_ORDER_NAME + 1).value) == order_name:
            raise ValueError(f"마스터 엑셀에 같은 제너리스주문명이 이미 있습니다 ({r}행): {order_name}")

    new = last + 1
    for col in range(1, ws.max_column + 1):
        src, dst = ws.cell(last, col), ws.cell(new, col)
        if src.has_style:
            dst._style = copy.copy(src._style)
    if ws.row_dimensions[last].height:
        ws.row_dimensions[new].height = ws.row_dimensions[last].height

    base = dt.date.fromisoformat(base_date) if isinstance(base_date, str) and base_date else base_date
    values = {
        COL_CATEGORY: category, COL_ORDER_NAME: order_name, COL_MANUFACTURER: manufacturer,
        COL_PRODUCT_NAME: product_name, COL_SPEC: spec, COL_BASE_DATE: base,
        COL_BUY: buy_price, COL_SELL: sell_price,
        8: f"=H{new}-G{new}",
        9: f"=IFERROR((H{new}-G{new})/H{new},0)",
        10: f"=IFERROR((H{new}-G{new})/G{new},0)",
        COL_WELFARE: welfare_type or None, COL_NOTE: note or None,
    }
    for idx, value in values.items():
        ws.cell(new, idx + 1).value = value

    # 범위를 마지막 행까지만 잡고 있는 수식(요약 시트 등)을 새 행까지 늘린다.
    pattern = re.compile(r"(\$[A-Z]{1,3}\$)%d(?!\d)" % last)
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                v = cell.value
                if isinstance(v, str) and v.startswith("=") and ws.title in v:
                    cell.value = pattern.sub(lambda m: f"{m.group(1)}{new}", v)
    if ws.auto_filter.ref:
        ws.auto_filter.ref = re.sub(r"\d+$", str(new), ws.auto_filter.ref)
    for dv in ws.data_validations.dataValidation:  # 항목(A열)·급여구분(L열) 드롭다운
        cols = {r.min_col for r in dv.sqref.ranges if r.min_col == r.max_col}
        for col in cols & {1, COL_WELFARE + 1}:
            dv.sqref.add(f"{openpyxl.utils.get_column_letter(col)}{new}")

    tmp = xlsx_path.with_name(xlsx_path.name + ".tmp")
    try:
        wb.save(tmp)
        os.replace(tmp, xlsx_path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return new


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
