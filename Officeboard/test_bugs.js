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

// ── 결과 ──
console.log(`\n결과: PASS ${pass} / FAIL ${fail}`);
process.exit(fail > 0 ? 1 : 0);
