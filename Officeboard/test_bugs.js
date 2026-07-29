// 회귀 테스트 — node test_bugs.js
// office-domain.js의 순수 함수만 테스트 (DOM 없음)

const fs = require('fs');
eval(fs.readFileSync('office-domain.js', 'utf8'));

let pass = 0, fail = 0;
function assert(cond, msg) {
  if (cond) { console.log('  ✓', msg); pass++; }
  else       { console.log('  ✗ FAIL:', msg); fail++; }
}

// ── Bug 1: isBeforeStart — month 파라미터 누락 시 동작 ──
console.log('\n[Bug 1] isBeforeStart month 파라미터 누락 회귀');
{
  const d = { start: '2026-08-01' };
  // 현재 달 2026-06 기준이면 미래 계약 → true
  assert(isBeforeStart(d, '2026-06') === true,  'month=2026-06 → 미래계약 true');
  // 현재 달 2026-08 기준이면 이번달 → false
  assert(isBeforeStart(d, '2026-08') === false, 'month=2026-08 → 이번달 false');
  // month 없이 호출 시 — undefined 비교 → 항상 false (renderVirtualList 버그)
  const withoutMonth = isBeforeStart(d, undefined);
  assert(withoutMonth === false, 'month=undefined → false (버그: 미래계약인데 false)');
}

// ── Bug 2: A018-2 접미사 비상주 computeStats 누락 ──
console.log('\n[Bug 2] A018-2 타입 비상주 computeStats 누락');
{
  const data = {
    'A018-2': {
      name: '테스트상사', contractType: '비상주',
      rent: 290400, start: '2026-01-01', end: '2026-12-31',
      'paid_2026-06': true,
    }
  };
  const stats = computeStats(data, '2026-06');
  assert(stats.virtualCount > 0,  'A018-2: virtualCount 1 이상이어야 함');
  assert(stats.vPaidAmt   > 0,   'A018-2: vPaidAmt 반영되어야 함');
  assert(stats.unpaidAmt  === 0, 'A018-2: unpaidAmt 0이어야 함');
}

// ── Bug 3: V 접두사 비상주 computeStats 정상 동작 확인 ──
console.log('\n[Bug 3] V-prefix 비상주 정상 동작');
{
  const data = {
    'V001': {
      name: '테스트비상주', contractType: '비상주',
      rent: 290400, start: '2026-01-01', end: '2026-12-31',
      'paid_2026-06': true,
    }
  };
  const stats = computeStats(data, '2026-06');
  assert(stats.virtualCount >= 1, 'V001: virtualCount 반영');
  assert(stats.vPaidAmt    > 0,   'V001: vPaidAmt 반영');
}

// ── 정상 동작 확인: isPaidThisMonth 선납 처리 ──
console.log('\n[정상] isPaidThisMonth 선납달 외 미합산');
{
  const d = { prepaid: true, prepaidAt: '2026-06', rent: 430000 };
  assert(isPaidThisMonth(d, '2026-06') === true,  '선납달 6월 → 합산 O');
  assert(isPaidThisMonth(d, '2026-07') === false, '7월 이후 → 합산 X');
  assert(isPaid(d, '2026-07') === true,           '7월 paid 상태는 여전히 true');
}

// ── Bug 5: computeVaRent — 개월수 곱셈 누락 회귀 ──
// (6개월/1년치를 선납해도 월 단가만 잡히던 버그)
console.log('\n[Bug 5] computeVaRent 선납 시 개월수 곱셈 누락 회귀');
{
  assert(computeVaRent(false, true, 6)  === 145200, '개인 6개월 선납 = 22,000×6×1.1');
  assert(computeVaRent(false, true, 12) === 290400, '개인 1년 선납 = 22,000×12×1.1');
  assert(computeVaRent(true,  true, 24) === 1161600, '법인 2년 선납 = 44,000×24×1.1');
}

// ── Bug 6: computeVaRent — VAT 누락 회귀 ──
// (부가세 10%를 빼먹어서 264,000으로 잡히던 버그 — 290,400이 맞는 값)
console.log('\n[Bug 6] computeVaRent VAT 10% 누락 회귀');
{
  assert(computeVaRent(false, true, 12) === 290400,
    '개인 1년 선납 VAT 포함 290,400 (VAT 빠지면 264,000이 나옴 — 버그)');
}

// ── 정상 동작 확인: computeVaRent 월납은 개월수를 곱하지 않음 ──
// (곱했다면 매달 결제 체크할 때마다 전체 계약금이 중복 집계되는 버그가 생김)
console.log('\n[정상] computeVaRent 월납은 단가만 (개월수 곱하면 안 됨)');
{
  assert(computeVaRent(false, false, 12) === 24200, '개인 월납 = 22,000×1.1 (12를 곱하면 안 됨)');
  assert(computeVaRent(true,  false, 24) === 48400,  '법인 월납 = 44,000×1.1 (24를 곱하면 안 됨)');
}

// ── computeExpiryAlerts — 오늘 기준 독립 동작 확인 ──
console.log('\n[후보4] computeExpiryAlerts 오늘 기준 분리');
{
  const today = new Date().toISOString().slice(0, 10);
  const nearEnd = new Date();
  nearEnd.setDate(nearEnd.getDate() + 10);
  const nearEndStr = nearEnd.toISOString().slice(0, 10);

  const farEnd = new Date();
  farEnd.setFullYear(farEnd.getFullYear() + 2);
  const farEndStr = farEnd.toISOString().slice(0, 10);

  const data = {
    'V001': { name: '만료임박', contractType: '비상주', rent: 290400, start: '2025-01-01', end: nearEndStr },
    'V002': { name: '여유있음', contractType: '비상주', rent: 290400, start: '2025-01-01', end: farEndStr  },
    'A018-2': { name: '접미사비상주', contractType: '비상주', rent: 290400, start: '2025-01-01', end: nearEndStr },
  };
  const alerts = computeExpiryAlerts(data);
  assert(alerts.vExpiring.length === 2,      '만료임박 2건(V001, A018-2) 감지');
  assert(alerts.vExpiring[0].diff <= 10,     'diff가 10일 이하');
  assert(alerts.expiring === 0,              '상주 만료임박 0건');

  // 과거 month로 computeStats 호출해도 알림은 오늘 기준
  const stats = computeStats(data, '2025-01');
  assert(!('expiring'  in stats), 'computeStats에 expiring 없음');
  assert(!('vExpiring' in stats), 'computeStats에 vExpiring 없음');
}

// ── addMonthsToDate — 후보1: 상주/비상주 날짜계산 중복 제거로 추출한 순수함수 ──
console.log('\n[후보1] addMonthsToDate 월/연 롤오버 및 말일 처리');
{
  assert(addMonthsToDate('2026-01-15', 6)  === '2026-07-15', '월 내 이동');
  assert(addMonthsToDate('2026-08-01', 6)  === '2027-02-01', '연도 롤오버');
  assert(addMonthsToDate('2026-01-31', 1)  === '2026-03-03', '말일 오버플로우 (JS Date 정규화, 기존 인라인 로직과 동일 동작)');
}

// ── paymentStatusInfo — 후보2: 비상주 목록 납부라벨이 statusClass()와 중복되던 것을 일원화 ──
console.log('\n[후보2] paymentStatusInfo가 statusClass()와 일관되게 매핑되는지 확인');
{
  const data = {
    'V001': { name: '완납고객', contractType: '비상주', rent: 24200, start: '2025-01-01', 'paid_2026-06': true },
    'V002': { name: '미납고객', contractType: '비상주', rent: 24200, start: '2025-01-01' },
    'V003': { name: '대기고객', contractType: '비상주', rent: 24200, start: '2027-01-01' },
  };
  assert(paymentStatusInfo('V001', data, '2026-06').label === '완납', 'paid → 완납');
  assert(paymentStatusInfo('V002', data, '2026-06').label === '미납', 'unpaid → 미납');
  assert(paymentStatusInfo('V003', data, '2026-06').label === '대기', 'pre-contract → 대기');
  // statusClass()가 내리는 원래 판단과 항상 일치해야 함(라벨이 판단 로직을 다시 구현하지 않고 매핑만 함)
  const expectedByClass = { 'paid': '완납', 'unpaid': '미납', 'pre-contract': '대기', 'vacant': '-' };
  ['V001', 'V002', 'V003'].forEach(id => {
    const cls = statusClass(id, data, '2026-06');
    assert(expectedByClass[cls] === paymentStatusInfo(id, data, '2026-06').label,
      `${id}: statusClass(${cls})와 paymentStatusInfo 라벨 일치`);
  });
}

// ── 결과 ──
console.log(`\n결과: PASS ${pass} / FAIL ${fail}`);
process.exit(fail > 0 ? 1 : 0);
