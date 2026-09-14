"""SQLite 마스터 DB 접근 계층."""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterable, Optional

from app.config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    order_name TEXT NOT NULL,
    manufacturer TEXT,
    product_name TEXT,
    spec TEXT,
    base_date TEXT,
    buy_price REAL,
    sell_price REAL,
    welfare_type TEXT,
    note TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    alias_text TEXT NOT NULL,
    UNIQUE(item_id, alias_text)
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    changed_at TEXT NOT NULL,
    old_buy REAL,
    new_buy REAL,
    old_sell REAL,
    new_sell REAL,
    memo TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_date TEXT NOT NULL,
    exported_path TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    raw_text TEXT NOT NULL,
    item_id INTEGER REFERENCES items(id),
    quantity REAL,
    requirement_text TEXT,
    spec_text TEXT,
    applied_buy REAL,
    applied_sell REAL,
    match_type TEXT,
    remark TEXT
);
"""


@contextmanager
def connect():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(order_lines)").fetchall()}
    if "remark" not in cols:
        conn.execute("ALTER TABLE order_lines ADD COLUMN remark TEXT")


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


def is_empty() -> bool:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM items").fetchone()
        return row["c"] == 0


def insert_item(
    category, order_name, manufacturer, product_name, spec,
    base_date, buy_price, sell_price, welfare_type, note,
    aliases: Iterable[str] = (),
) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO items
            (category, order_name, manufacturer, product_name, spec, base_date,
             buy_price, sell_price, welfare_type, note, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (category, order_name, manufacturer, product_name, spec, base_date,
             buy_price, sell_price, welfare_type, note, now),
        )
        item_id = cur.lastrowid
        seen = set()
        for alias in list(aliases) + [order_name]:
            alias = (alias or "").strip()
            if not alias or alias in seen:
                continue
            seen.add(alias)
            conn.execute(
                "INSERT OR IGNORE INTO aliases (item_id, alias_text) VALUES (?,?)",
                (item_id, alias),
            )
        return item_id


def all_items_with_aliases():
    """매칭 엔진이 쓸 (item_row, [alias_texts]) 목록 전체를 반환."""
    with connect() as conn:
        items = conn.execute("SELECT * FROM items ORDER BY id").fetchall()
        alias_rows = conn.execute("SELECT item_id, alias_text FROM aliases").fetchall()
    alias_map: dict[int, list[str]] = {}
    for row in alias_rows:
        alias_map.setdefault(row["item_id"], []).append(row["alias_text"])
    return [(dict(item), alias_map.get(item["id"], [])) for item in items]


def get_item(item_id: int) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        return dict(row) if row else None


def search_items(keyword: str):
    kw = f"%{keyword}%"
    with connect() as conn:
        rows = conn.execute(
            """SELECT DISTINCT i.* FROM items i
               LEFT JOIN aliases a ON a.item_id = i.id
               WHERE i.order_name LIKE ? OR i.manufacturer LIKE ?
                     OR i.product_name LIKE ? OR a.alias_text LIKE ?
               ORDER BY i.category, i.order_name""",
            (kw, kw, kw, kw),
        ).fetchall()
        return [dict(r) for r in rows]


def all_items():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM items ORDER BY category, order_name").fetchall()
        return [dict(r) for r in rows]


def add_alias(item_id: int, alias_text: str) -> None:
    alias_text = (alias_text or "").strip()
    if not alias_text:
        return
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO aliases (item_id, alias_text) VALUES (?,?)",
            (item_id, alias_text),
        )


def get_aliases(item_id: int) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT alias_text FROM aliases WHERE item_id=? ORDER BY alias_text", (item_id,)
        ).fetchall()
        return [r["alias_text"] for r in rows]


def update_item_prices(item_id: int, new_buy: float, new_sell: float, memo: str = "") -> None:
    item = get_item(item_id)
    if item is None:
        return
    old_buy, old_sell = item["buy_price"], item["sell_price"]
    if old_buy == new_buy and old_sell == new_sell:
        return
    today = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """UPDATE items SET buy_price=?, sell_price=?, base_date=?, updated_at=?
               WHERE id=?""",
            (new_buy, new_sell, today, now, item_id),
        )
        conn.execute(
            """INSERT INTO price_history
               (item_id, changed_at, old_buy, new_buy, old_sell, new_sell, memo)
               VALUES (?,?,?,?,?,?,?)""",
            (item_id, now, old_buy, new_buy, old_sell, new_sell, memo),
        )


def get_price_history(item_id: int):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM price_history WHERE item_id=? ORDER BY changed_at DESC",
            (item_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def insert_new_item_from_order(order_name: str, manufacturer="", product_name="",
                                spec="", buy_price=0, sell_price=0, category="") -> int:
    today = date.today().isoformat()
    return insert_item(
        category, order_name, manufacturer, product_name, spec,
        today, buy_price, sell_price, "", "신규 등록(주문 화면에서 추가)",
    )


def create_order(order_date: str) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO orders (order_date, created_at) VALUES (?,?)",
            (order_date, now),
        )
        return cur.lastrowid


def add_order_line(order_id, raw_text, item_id, quantity, requirement_text,
                    spec_text, applied_buy, applied_sell, match_type, remark="") -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO order_lines
               (order_id, raw_text, item_id, quantity, requirement_text, spec_text,
                applied_buy, applied_sell, match_type, remark)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (order_id, raw_text, item_id, quantity, requirement_text, spec_text,
             applied_buy, applied_sell, match_type, remark),
        )
