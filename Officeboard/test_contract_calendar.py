"""
회귀 테스트 — contract_calendar.py (계약월 계산 / 선납 재구성)
실행: python test_contract_calendar.py

엑셀 워크북 없이 날짜 경계값(연말 롤오버 등)을 표 기반으로 검증한다.
"""
import sys

sys.stdout.reconfigure(encoding='utf-8')

from contract_calendar import contract_months, reconstruct_prepaid

pass_count = 0
fail_count = 0


def check(label, actual, expected):
    global pass_count, fail_count
    ok = actual == expected
    mark = '✓' if ok else '✗ FAIL'
    print(f'  {mark} {label}: got={actual!r} expected={expected!r}')
    if ok:
        pass_count += 1
    else:
        fail_count += 1


def test_contract_months():
    print('[contract_months]')
    check('같은 달', contract_months('2026-06-01', '2026-06-30'),
          ['2026-06'])
    check('한 해 안', contract_months('2026-06-01', '2026-09-01'),
          ['2026-06', '2026-07', '2026-08', '2026-09'])
    check('연말 롤오버', contract_months('2026-11-01', '2027-02-01'),
          ['2026-11', '2026-12', '2027-01', '2027-02'])
    check('start 없음', contract_months('', '2026-09-01'), [])
    check('end 없음', contract_months('2026-06-01', ''), [])
    check('둘 다 없음', contract_months('', ''), [])


def test_reconstruct_prepaid():
    print('\n[reconstruct_prepaid]')
    check('전월 완납 -> 선납',
          reconstruct_prepaid('2026-06-01', '2026-08-01', {'2026-06', '2026-07', '2026-08'}),
          True)
    check('한달 미납 -> 선납 아님',
          reconstruct_prepaid('2026-06-01', '2026-08-01', {'2026-06', '2026-08'}),
          False)
    check('연말 롤오버 전월 완납 -> 선납',
          reconstruct_prepaid('2026-11-01', '2027-01-01', {'2026-11', '2026-12', '2027-01'}),
          True)
    check('납부 컬럼 자체가 없음 -> 선납 아님',
          reconstruct_prepaid('2026-06-01', '2026-08-01', set()),
          False)
    check('기간 정보 없음 -> 선납 아님',
          reconstruct_prepaid('', '', {'2026-06'}),
          False)


def main():
    test_contract_months()
    test_reconstruct_prepaid()
    print(f'\n결과: PASS {pass_count} / FAIL {fail_count}')
    sys.exit(1 if fail_count else 0)


if __name__ == '__main__':
    main()
