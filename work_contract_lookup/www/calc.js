// ── 순수 계산 로직 (DOM 의존 없음) ──────────────────────

// 날짜를 toISOString()으로 변환하면 KST(UTC+9)에서 자정이 하루 앞으로 밀려
// 날짜가 하루 당겨지는 버그가 생긴다(officeboard에서 실제로 겪은 문제) — 항상 로컬 getter로 포맷한다.
function fmtDateLocal(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}

// "계약기간 N개월"은 입주일부터 N개월치를 쓴다는 뜻이라 만료일은 N개월 후 당일이 아니라
// 그 전날이다(1/15 시작 6개월 → 7/15가 아니라 7/14까지 사용).
function addMonthsToDate(dateStr, n) {
  const d = new Date(dateStr + 'T00:00:00');
  d.setMonth(d.getMonth() + n);
  d.setDate(d.getDate() - 1);
  return fmtDateLocal(d);
}

// 두 날짜 사이의 개월 수(만료일 당일까지 사용한 것으로 쳐서 계산 — addMonthsToDate의 역연산)
function monthsBetween(startStr, endStr) {
  const s = new Date(startStr + 'T00:00:00');
  const e = new Date(endStr + 'T00:00:00');
  e.setDate(e.getDate() + 1);
  let months = (e.getFullYear() - s.getFullYear()) * 12 + (e.getMonth() - s.getMonth());
  if (e.getDate() < s.getDate()) months -= 1;
  return Math.max(months, 0);
}

function fmtWon(n) {
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// officeboard의 calcRent()와 동일한 반올림 규칙(100원 단위 버림)
function calcRent(baseRent, discount, vat) {
  return Math.floor(Math.round(baseRent * (1 - discount) * (vat ? 1.1 : 1)) / 100) * 100;
}

function depositAmount(baseRent) {
  return baseRent * 2;
}

function fmtDateKorean(dateStr) {
  const [y, m, d] = dateStr.split('-');
  return `${y}년 ${m}월 ${d}일`;
}

function normalizeRoomName(raw) {
  return raw.trim().toUpperCase();
}

// 계약기간·금액 조합 규칙(6개월 이상 할인 30% 등)을 한곳에 모은 함수.
// DOM을 몰라서 테스트에서 직접 검증할 수 있다.
function computeContractInfo(baseRent, startVal, endVal) {
  const months = monthsBetween(startVal, endVal);
  const discountRate = months >= 6 ? 0.3 : 0;
  return {
    months,
    discountRate,
    standardExVat:  calcRent(baseRent, 0, false),
    standardIncVat: calcRent(baseRent, 0, true),
    discountExVat:  calcRent(baseRent, discountRate, false),
    discountIncVat: calcRent(baseRent, discountRate, true),
    deposit:        depositAmount(baseRent),
  };
}
