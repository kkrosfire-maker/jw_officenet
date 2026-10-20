// 금액 100원 버림 로직 회귀 테스트
// node test_rounding.js

const BASE_RENT = {
  A002:430000, A003:430000, A004:430000, A005:430000, A006:430000, A007:430000, A010:430000,
  A008:500000, A009:500000,
  A011:330000, A012:330000, A013:330000,
  A014:380000, A015:380000, A016:380000, A017:380000,
  B001:380000, B002:380000,
  B003:330000, B004:330000, B005:330000, B006:330000, B007:330000,
  B008:550000, B009:550000,
  B010:380000, B011:380000, B012:380000, B013:382000, B014:380000,
  C001:380000, C002:380000,
  C003:280000, C004:280000, C005:280000, C006:280000, C007:280000, C008:280000,
  C009:430000, C010:430000, C011:430000, C012:430000, C013:430000, C014:430000,
  C015:430000, C016:430000, C017:430000, C018:430000,
};

const OLD_floor100 = (x) => Math.floor(x / 100) * 100;
const NEW_floor100 = (x) => Math.floor(Math.round(x) / 100) * 100;

const DISCOUNTS = [0, 0.1, 0.2, 0.25, 0.3];
const VATS      = [1.0, 1.1];

let pass = 0;
let fail = 0;
const failures = [];

// 케이스 1: 빈 호실 표시 (base * 0.7)
console.log('=== 케이스 1: 빈 호실 가격 (base × 0.7) ===');
for (const [room, base] of Object.entries(BASE_RENT)) {
  const raw = base * 0.7;
  const result = NEW_floor100(raw);
  const isMultipleOf100 = result % 100 === 0;
  const isReasonable = result >= base * 0.65 && result <= base * 0.75;
  if (isMultipleOf100 && isReasonable) {
    pass++;
  } else {
    fail++;
    failures.push({ case: `${room} 빈호실`, base, raw, result, isMultipleOf100, isReasonable });
  }
}

// 케이스 2: VAT + 할인율 조합
console.log('=== 케이스 2: VAT + 할인율 조합 ===');
for (const [room, base] of Object.entries(BASE_RENT)) {
  for (const d of DISCOUNTS) {
    for (const v of VATS) {
      const raw = base * (1 - d) * v;
      const result = NEW_floor100(raw);
      const isMultipleOf100 = result % 100 === 0;
      // 결과는 버림이므로 raw보다 작거나 같아야 함
      // Math.round()로 FP 오차를 제거한 정수 기준으로 버림 검증
      const exact = Math.round(raw);
      const isFlooredCorrectly = result === Math.floor(exact / 100) * 100;
      if (isMultipleOf100 && isFlooredCorrectly) {
        pass++;
      } else {
        fail++;
        failures.push({ case: `${room} discount=${d} vat=${v}`, base, raw, result, isMultipleOf100, isFlooredCorrectly });
      }
    }
  }
}

// 케이스 3: 일할 계산 (대표값)
console.log('=== 케이스 3: 일할 계산 ===');
const dailyCases = [
  { rent: 330000, days: 31, used: 20 },
  { rent: 430000, days: 30, used: 15 },
  { rent: 430000, days: 31, used: 1  },
  { rent: 280000, days: 28, used: 7  },
  { rent: 550000, days: 31, used: 31 },
];
for (const { rent, days, used } of dailyCases) {
  const raw = rent / days * used;
  const result = NEW_floor100(raw);
  const isMultipleOf100 = result % 100 === 0;
  const exact = Math.round(raw);
  const isFlooredCorrectly = result === Math.floor(exact / 100) * 100;
  if (isMultipleOf100 && isFlooredCorrectly) {
    pass++;
  } else {
    fail++;
    failures.push({ case: `일할 rent=${rent} ${used}/${days}일`, raw, result, isMultipleOf100, isFlooredCorrectly });
  }
}

// 케이스 4: 부동소수점 오차 특정 케이스 (이 버그의 핵심)
console.log('=== 케이스 4: 부동소수점 위험 케이스 ===');
const fpCases = [
  { label: '330000 × 0.7', raw: 330000 * 0.7, expected: 231000 },
  { label: '330000 × 0.75 × 1.1', raw: 330000 * 0.75 * 1.1, expected: 272200 },
  { label: '430000 × 0.75 × 1.1', raw: 430000 * 0.75 * 1.1, expected: 354700 },
  { label: '280000 × 0.75 × 1.1', raw: 280000 * 0.75 * 1.1, expected: 231000 },
  { label: '382000 × 0.7', raw: 382000 * 0.7, expected: 267400 },
];
for (const { label, raw, expected } of fpCases) {
  const result = NEW_floor100(raw);
  const oldResult = OLD_floor100(raw);
  const correct = result === expected;
  const wasWrong = oldResult !== expected;
  console.log(`  ${label}`);
  console.log(`    raw JS값: ${raw}`);
  console.log(`    OLD: ${oldResult.toLocaleString()}원  NEW: ${result.toLocaleString()}원  기댓값: ${expected.toLocaleString()}원  ${correct ? '✓ PASS' : '✗ FAIL'}`);
  if (wasWrong && correct) console.log(`    ↑ OLD에서 버그 → NEW에서 수정됨`);
  if (correct) pass++; else { fail++; failures.push({ label, raw, result, expected }); }
}

// 결과
console.log('\n=== 결과 ===');
console.log(`PASS: ${pass}  FAIL: ${fail}`);
if (failures.length > 0) {
  console.log('\n실패 케이스:');
  for (const f of failures) console.log(' ', JSON.stringify(f));
  process.exit(1);
} else {
  console.log('모든 케이스 통과');
  process.exit(0);
}
