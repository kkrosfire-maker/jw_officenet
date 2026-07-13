# CONTEXT.md

Officeboard 도메인 용어와 코드만 봐서는 바로 드러나지 않는 규칙을 기록한다.

## 비상주 (가상오피스) 임대료

- 개인 22,000원/월, 법인 44,000원/월 (부가세 별도 단가)
- **선납(일괄납부)**: 계약 전체 개월수를 계약 시작월에 한 번에 청구
  → `단가 × 개월수 × 1.1`
- **월납(개별납부)**: 매달 단가만 청구 → `단가 × 1.1`
- 예: 개인 1년 선납 = 22,000×12×1.1 = 290,400원
- 계산 구현: `office-domain.js`의 `computeVaRent(isCorp, prepaid, months)` — `dashboard.js`의 `vaComputeRent()`는 이 함수에 DOM 폼 값을 읽어 넘기기만 하는 얇은 어댑터.
- 회귀 테스트: `test_bugs.js`에 개인/법인 × 선납/월납 × 계약기간 조합 케이스로 커버.

## 엑셀 백업의 선납 재구성

- 엑셀 백업(.xlsx)에는 "선납" 여부가 컬럼으로 저장되지 않고 월별 납부 컬럼(`YYYY-MM 납부`)만 있다.
- 가져오기(import) 시 계약기간 내 모든 월이 완납이면 선납이었다고 역산한다.
- 계산 구현: `contract_calendar.py`의 `reconstruct_prepaid(start, end, paid_months)` — `excel_io.py`의 `parse_workbook()`은 워크북에서 읽은 완납 월 집합을 이 함수에 넘기기만 하는 얇은 어댑터.
- 회귀 테스트: `test_contract_calendar.py`에 같은 달/연내/연말 롤오버/기간 정보 없음 케이스로 커버.
