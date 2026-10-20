"""
회귀 테스트 — storage.py 어댑터
실행: python test_storage.py

FileStorage/PostgresStorage 각각이 load()/save()/ping() 계약을 지키는지,
get_storage()가 DATABASE_URL 유무로 올바른 어댑터를 고르는지 검증한다.
Postgres 연결 자체는 실제 DB가 필요하므로 여기서는 검증하지 않는다
(그건 main.py를 실제로 띄운 /ping 엔드포인트가 담당).
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')

from storage import FileStorage, PostgresStorage, get_storage

pass_count = 0
fail_count = 0


def assert_eq(label, actual, expected):
    global pass_count, fail_count
    ok = actual == expected
    mark = '✓' if ok else '✗ FAIL'
    print(f'  {mark} {label}: got={actual!r} expected={expected!r}')
    if ok:
        pass_count += 1
    else:
        fail_count += 1


def test_get_storage_picks_file_without_database_url():
    print('\n[get_storage] DATABASE_URL 없으면 FileStorage')
    s = get_storage(None, '/tmp/whatever.json')
    assert_eq('type', type(s).__name__, 'FileStorage')
    assert_eq('name', s.name, 'file')


def test_get_storage_picks_postgres_with_database_url():
    print('\n[get_storage] DATABASE_URL 있으면 PostgresStorage')
    s = get_storage('postgresql://user:pw@host/db', '/tmp/whatever.json')
    assert_eq('type', type(s).__name__, 'PostgresStorage')
    assert_eq('name', s.name, 'postgres')


def test_file_storage_round_trip():
    print('\n[FileStorage] 저장 -> 로드 왕복')
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'data.json')
        s = FileStorage(path)
        s.init()  # no-op이어야 함, 예외 없이 통과

        assert_eq('파일 없을 때 load()', s.load(), {})

        payload = json.dumps({'A001': {'name': '테스트'}}, ensure_ascii=False)
        s.save(payload)
        assert_eq('저장 후 load()', s.load(), {'A001': {'name': '테스트'}})

        ok, err = s.ping()
        assert_eq('ping() ok', ok, True)
        assert_eq('ping() error', err, None)


def main():
    test_get_storage_picks_file_without_database_url()
    test_get_storage_picks_postgres_with_database_url()
    test_file_storage_round_trip()

    print(f'\n결과: PASS {pass_count} / FAIL {fail_count}')
    sys.exit(1 if fail_count else 0)


if __name__ == '__main__':
    main()
