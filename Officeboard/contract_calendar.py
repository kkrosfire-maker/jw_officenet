"""계약기간 ↔ 월 목록 변환, 선납 재구성 계산. openpyxl/Flask에 의존하지 않는 순수 함수.

엑셀 백업에는 "선납" 여부가 컬럼으로 저장되지 않고 월별 납부 컬럼만 있다.
계약기간 내 모든 월이 완납이면 선납이었다고 역산하는 규칙이 여기 있다.
(선납/월납 단가 규칙 자체는 CONTEXT.md 참고.)
"""


def contract_months(start: str, end: str) -> list[str]:
    """'YYYY-MM-DD' 시작/종료일 → 그 사이 모든 'YYYY-MM' 월 목록 (양끝 포함).

    start/end가 비어 있으면 빈 목록을 반환한다.
    """
    if not start or not end:
        return []
    s, e = start[:7], end[:7]
    cur_y, cur_m = int(s[:4]), int(s[5:7])
    end_y, end_m = int(e[:4]), int(e[5:7])

    months = []
    while (cur_y, cur_m) <= (end_y, end_m):
        months.append(f'{cur_y}-{cur_m:02d}')
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1
    return months


def reconstruct_prepaid(start: str, end: str, paid_months: set) -> bool:
    """계약기간의 모든 월이 완납 상태면 선납으로 간주."""
    months = contract_months(start, end)
    return bool(months) and all(m in paid_months for m in months)
