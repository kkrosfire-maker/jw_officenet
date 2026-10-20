"""오피스보드 데이터 저장 어댑터.

main.py는 어느 백엔드를 쓰는지 전혀 모른 채 load()/save(payload)만 호출한다.
DATABASE_URL이 있으면 Postgres, 없으면 로컬 JSON 파일을 쓴다 — 그 결정은
get_storage() 한 곳에서만 이뤄진다.
"""
import json
import os
from contextlib import contextmanager


class FileStorage:
    """로컬 개발용: data.json 파일에 그대로 읽고 쓴다."""

    name = 'file'

    def __init__(self, path: str):
        self.path = path

    def init(self) -> None:
        pass

    def load(self) -> dict:
        if os.path.exists(self.path):
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save(self, payload: str) -> None:
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write(payload)

    def ping(self) -> tuple[bool, str | None]:
        return True, None


class PostgresStorage:
    """배포용: office_data 테이블 단일 행(id=1)에 JSONB로 전체 데이터를 저장한다."""

    name = 'postgres'

    def __init__(self, database_url: str):
        self.database_url = database_url

    @contextmanager
    def _conn(self):
        import psycopg2
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS office_data (
                    id INTEGER PRIMARY KEY,
                    data JSONB NOT NULL DEFAULT '{}'
                )
            """)
            cur.execute("""
                INSERT INTO office_data (id, data) VALUES (1, '{}')
                ON CONFLICT (id) DO NOTHING
            """)

    def load(self) -> dict:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT data FROM office_data WHERE id = 1")
            row = cur.fetchone()
            return row[0] if row else {}

    def save(self, payload: str) -> None:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO office_data (id, data) VALUES (1, %s)
                ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data
            """, (payload,))

    def ping(self) -> tuple[bool, str | None]:
        try:
            with self._conn() as conn:
                conn.cursor().execute("SELECT 1")
            return True, None
        except Exception as e:
            return False, str(e)


def get_storage(database_url: str | None, data_file: str):
    """DATABASE_URL 유무로 백엔드를 선택하는 유일한 지점."""
    if database_url:
        return PostgresStorage(database_url)
    return FileStorage(data_file)
