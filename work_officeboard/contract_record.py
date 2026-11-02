"""계약 레코드(data dict의 한 항목)에 대한 판정 규칙. openpyxl/Flask에 의존하지 않는 순수 함수.

엑셀 가져오기/내보내기(excel_io.py)가 쓰는 규칙을 한곳에 모았다.
같은 규칙이 office-domain.js(isVirtual, isPaid)에도 있으므로, 양쪽은
record_rules_cases.json 표를 함께 읽는 테스트로 같은 답을 내는지 고정한다.
"""
import re

PAID_PREFIX = 'paid_'
INVOICE_PREFIX = 'invoice_'

_VIRTUAL_ID = re.compile(r'^V\d+$')


def is_virtual(room_id: str, record: dict | None) -> bool:
    """비상주 여부 — contractType이 '비상주'이거나 ID가 V숫자 형태면 비상주.

    office-domain.js의 isVirtual()과 같은 규칙.
    """
    if record and record.get('contractType') == '비상주':
        return True
    return bool(_VIRTUAL_ID.match(room_id))


def is_paid(record: dict | None, month: str) -> bool:
    """해당 월 납부 여부 — 선납이면 모든 달이 납부, 아니면 paid_YYYY-MM 플래그.

    office-domain.js의 isPaid()와 같은 규칙.
    """
    return bool(record and (record.get('prepaid') or record.get(PAID_PREFIX + month)))


def months_with_prefix(records, prefix: str) -> set[str]:
    """레코드들의 키에서 prefix(paid_/invoice_) 뒤의 월(YYYY-MM)을 모두 모은다."""
    return {k[len(prefix):] for rec in records for k in rec if k.startswith(prefix)}
