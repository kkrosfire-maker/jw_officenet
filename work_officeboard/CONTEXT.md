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

## 계약 레코드 판정 규칙 (비상주 / 납부)

- **비상주 판정**: `contractType === '비상주'` 이거나 호실 ID가 `V숫자`(예: V050)이면 비상주. 계약유형 칸이 비어 있어도 V숫자 ID면 비상주 시트로 내보낸다.
- **납부 판정**: `prepaid`가 켜져 있으면 모든 달이 납부, 아니면 `paid_YYYY-MM` 플래그.
- 같은 규칙이 JS(`office-domain.js`의 `isVirtual`/`isPaid`)와 Python(`contract_record.py`의 `is_virtual`/`is_paid`) 두 곳에 있다. 한쪽을 바꾸면 **`record_rules_cases.json` 표**를 고치고 `python test_contract_record.py`, `node test_bugs.js`를 둘 다 돌려 같은 답을 내는지 확인한다.
- 엑셀 입출력(`excel_io.py`)은 이 규칙을 `contract_record.py`에서 가져다 쓰는 얇은 어댑터.
- 할인율 "직접입력"(`discount: 'custom'`) 레코드는 엑셀에 `직접입력`으로 내보내진다. 가져오기는 0%로 읽고 월세(원)는 보존된다(`customRentBase`는 복원하지 않음).
