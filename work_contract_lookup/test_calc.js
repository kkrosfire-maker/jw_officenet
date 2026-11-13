// 회귀 테스트 — node test_calc.js
const fs = require('fs');
eval(fs.readFileSync('www/room_rates.js', 'utf8'));
eval(fs.readFileSync('www/calc.js', 'utf8'));

let pass = 0, fail = 0;
function assert(cond, msg) {
  if (cond) { console.log('  ✓', msg); pass++; }
  else       { console.log('  ✗ FAIL:', msg); fail++; }
}

console.log('\n[addMonthsToDate — N개월 후 "전날"이 만료일]');
assert(addMonthsToDate('2026-01-15', 6) === '2026-07-14', '6개월 사용 시 만료일은 7/15가 아니라 7/14');
assert(addMonthsToDate('2026-08-01', 6) === '2027-01-31', '연도 롤오버 + 전날');

console.log('\n[monthsBetween — addMonthsToDate의 역연산]');
assert(monthsBetween('2026-01-15', '2026-07-14') === 6, '만료일 기준 정확히 6개월');
assert(monthsBetween('2026-01-15', '2026-07-13') === 5, '하루 모자란 6개월 → 5개월로 침');
assert(monthsBetween('2026-01-31', '2027-01-31') === 12, '1년');

console.log('\n[calcRent — B007 표준 330,000원 기준]');
assert(calcRent(330000, 0, false) === 330000, '표준 VAT별도');
assert(calcRent(330000, 0, true)  === 363000, '표준 VAT포함 (×1.1)');
assert(calcRent(330000, 0.3, false) === 231000, '할인 VAT별도 (×0.7)');
assert(calcRent(330000, 0.3, true)  === 254100, '할인 VAT포함 (×0.7×1.1)');

console.log('\n[depositAmount]');
assert(depositAmount(330000) === 660000, '표준금액의 2배');

console.log('\n[할인 적용 기준: 6개월 미만 미적용 / 6개월 이상 적용]');
{
  const months5 = monthsBetween('2026-01-01', '2026-06-01'); // 5개월
  assert((months5 >= 6 ? 0.3 : 0) === 0, '5개월은 할인 미적용');

  const months6 = monthsBetween('2026-01-15', '2026-07-14'); // 6개월
  assert((months6 >= 6 ? 0.3 : 0) === 0.3, '정확히 6개월은 할인 적용');
}

console.log('\n[computeContractInfo — 계약기간·금액 조합 규칙]');
{
  const r5 = computeContractInfo(330000, '2026-01-01', '2026-06-01'); // 5개월
  assert(r5.months === 5, '5개월 계약 기간 계산');
  assert(r5.discountRate === 0, '5개월은 할인율 0');
  assert(r5.discountExVat === r5.standardExVat, '할인 미적용 시 할인금액=표준금액');

  const r6 = computeContractInfo(330000, '2026-01-15', '2026-07-14'); // 6개월
  assert(r6.months === 6, '6개월 계약 기간 계산');
  assert(r6.discountRate === 0.3, '6개월은 할인율 0.3');
  assert(r6.standardExVat === 330000, '표준금액(VAT별도)은 할인과 무관하게 고정');
  assert(r6.discountExVat === 231000, '할인금액(VAT별도) = 표준 × 0.7');
  assert(r6.discountIncVat === 254100, '할인금액(VAT포함) = 표준 × 0.7 × 1.1');
  assert(r6.deposit === 660000, '예치금 = 표준금액 × 2 (할인·기간과 무관)');
}

console.log(`\n결과: PASS ${pass} / FAIL ${fail}`);
process.exit(fail > 0 ? 1 : 0);
