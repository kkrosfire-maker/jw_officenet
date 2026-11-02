"""
회귀 테스트 — contract_record.py 및 엑셀 왕복(내보내기→가져오기)
실행: python test_contract_record.py

record_rules_cases.json은 test_bugs.js도 읽는다 — Python과 JS가 같은 답을 내는지 고정.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from contract_record import is_virtual, is_paid, months_with_prefix
from excel_io import build_workbook, parse_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, 'record_rules_cases.json'), encoding='utf-8') as f:
    CASES = json.load(f)

pass_count = 0
fail_count = 0


def check(label, actual, expected):
    global pass_count, fail_count
    ok = actual == expected
    print(f"  {'✓' if ok else '✗ FAIL'} {label}: got={actual!r} expected={expected!r}")
    if ok:
        pass_count += 1
    else:
        fail_count += 1


print('\n[is_virtual] 공유 표')
for c in CASES['is_virtual']:
    check(f"{c['id']} {c['record']}", is_virtual(c['id'], c['record']), c['expected'])

print('\n[is_paid] 공유 표')
for c in CASES['is_paid']:
    check(f"{c['record']} @ {c['month']}", is_paid(c['record'], c['month']), c['expected'])

print('\n[months_with_prefix]')
recs = [{'paid_2026-05': True, 'invoice_2026-05': True, 'name': 'x'}, {'paid_2026-06': False}]
check('paid_', months_with_prefix(recs, 'paid_'), {'2026-05', '2026-06'})
check('invoice_', months_with_prefix(recs, 'invoice_'), {'2026-05'})

print('\n[왕복] V숫자 ID + contractType 없음 → 내보내기에서도 비상주 시트')
data = {
    'A001': {'name': '상주상호', 'tenantName': 'a', 'contractType': '입주', 'rent': 430000,
             'start': '2026-01-01', 'end': '2026-12-31'},
    'V050': {'name': '비상주상호', 'tenantName': 'b', 'rent': 24200,
             'start': '2026-01-01', 'end': '2026-12-31'},  # contractType 비어 있음
}
wb = build_workbook(data, '2026-06')
sheet_rooms = {ws.title: [r[0] for r in ws.iter_rows(min_row=2, values_only=True)] for ws in wb.worksheets}
check('상주 시트', sheet_rooms['상주'], ['A001'])
check('비상주 시트', sheet_rooms['비상주'], ['V050'])
back = parse_workbook(wb)
check('가져오기 후 V050 계약유형', back['V050']['contractType'], '비상주')

print('\n[왕복] 할인율 직접입력(custom) 레코드가 있어도 내보내기가 죽지 않음')
data_custom = {'A004': {'name': '직접', 'tenantName': 'c', 'discount': 'custom', 'customRentBase': 299000,
                        'rent': 328900, 'contractType': '입주'}}
back = parse_workbook(build_workbook(data_custom, '2026-06'))
check('금액 보존', back['A004']['rent'], 328900)

print(f'\n결과: PASS {pass_count} / FAIL {fail_count}')
sys.exit(1 if fail_count else 0)
