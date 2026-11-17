// 순수 도메인 함수 및 상수 — DOM 없음, 전역 상태 없음
// 이 파일만 import해서 Node.js/브라우저 양쪽에서 테스트 가능

const ZONE = {
  A: { color: '#1565c0', name: 'A구역' },
  B: { color: '#e65100', name: 'B구역' },
  C: { color: '#2e7d32', name: 'C구역' },
  D: { color: '#6a1b9a', name: 'D구역' },
};

const BASE_RENT = {
  A02:430000, A03:430000, A04:430000, A05:430000, A06:430000, A07:430000, A10:430000,
  A08:500000, A09:500000,
  A11:330000, A12:330000, A13:330000,
  A14:380000, A15:380000, A16:380000, A17:380000,
  B01:380000, B02:380000,
  B03:330000, B04:330000, B05:330000, B06:330000, B07:330000,
  B08:550000, B09:500000,
  B10:380000, B11:380000, B12:380000, B13:380000, B14:380000,
  C01:380000, C02:380000,
  C03:280000, C04:280000, C05:280000, C06:280000, C07:280000, C08:280000,
  C09:430000, C10:430000, C11:430000, C12:430000, C13:430000, C14:430000,
  C15:430000, C16:430000, C17:430000, C18:430000,
};

const VIRTUAL_RENT_INDIVIDUAL = 15000;
const VIRTUAL_RENT_CORP       = 20000;

const LAYOUT = [
  [null,null,null,null,null,null,null,null,null,null,'GAP',null,'GAP','A01'],
  [null,null,null,null,null,null,null,null,null,null,'GAP',null,'GAP','A02'],
  ['B08','B07','B06','B05','B04','B03',null,null,'B01','A18','GAP','A11','GAP','A03'],
  [null,null,null,null,null,null,null,null,'B02','A17','GAP','A12','GAP','A04'],
  ['B09','B10','B11','B12','B13','B14',null,null,'C01','A16','GAP','A13','GAP','A05'],
  ['C09','C08','C07','C06','C05','C04','C03',null,'C02','A15','GAP','A14','GAP','A06'],
  [null,null,null,null,null,null,null,null,null,null,'GAP',null,'GAP','A07'],
  ['C10','C11','C12','C13','C14','C15','C16','C17','C18','A10','GAP','A09','GAP','A08'],
];

const ALL_ROOMS = [...new Set([].concat.apply([], LAYOUT).filter(c => c && c !== 'U' && c !== 'CORR' && c !== 'GAP'))];

function fmtWon(n) {
  if (!n) return '';
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function todayLocal() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}

const pKey = (m) => 'paid_' + m;

const INACTIVE_STATUSES = ['계약만료', '계약해지'];

function isOccupied(d) { return !!(d && (d.name || d.tenantName)); }

function isVirtual(id, d) { return !!(d && d.contractType === '비상주') || /^V\d+$/.test(id); }

function isActiveContract(d) { return !INACTIVE_STATUSES.includes(d && d.contractStatus); }

// 화면 표시용 ID (저장 키는 그대로): "A001" → "A01", "A018" → "A18", "A018-2" → "A18(2)"
function displayVaId(id) {
  id = String(id).replace(/^([A-Za-z]+)0(\d{2,})/, '$1$2'); // 숫자부 앞의 0 하나 제거
  const m = id.match(/^(.+)-(\d+)$/);
  return m ? `${m[1]}(${m[2]})` : id;
}

// 비상주 고객 ID 표시용: 저장된 ID 그대로(0을 줄이지 않음), 접미사만 "A018-2" → "A018(2)"
function displayVaCustomerId(id) {
  const m = String(id).match(/^(.+)-(\d+)$/);
  return m ? `${m[1]}(${m[2]})` : String(id);
}

// 신규 등록 시 baseId가 이미 존재하면 충돌 없는 다음 키 반환
// A018 → A018, A018 이미 있으면 → A018-2, A018-2도 있으면 → A018-3
function nextSuffixedVaId(baseId, data) {
  if (!data[baseId]) return baseId;
  let n = 2;
  while (data[`${baseId}-${n}`]) n++;
  return `${baseId}-${n}`;
}

function isPaid(d, m) { return !!(d && (d.prepaid || d[pKey(m)])); }

// 이 달에 납부금액으로 집계되는지 (선납은 선납 처리한 달에만, 개별납부는 해당 달에만)
function isPaidThisMonth(d, m) {
  if (!d) return false;
  if (d.prepaid) return d.prepaidAt === m;
  return !!(d[pKey(m)]);
}

function isBeforeStart(d, month) {
  if (!d || !d.start) return false;
  return d.start.slice(0, 7) > month;
}

function daysLeft(end) {
  if (!end) return null;
  const today = new Date(); today.setHours(0,0,0,0);
  const endDate = new Date(end + 'T00:00:00');
  const diff = Math.round((endDate - today) / 864e5);
  if (diff < 0)  return '만료';
  if (diff <= 30) return 'D-' + diff;
  return null;
}

function zone(id) { return id[0]; }

function statusClass(id, data, month) {
  const d = data[id];
  if (!isOccupied(d)) return 'vacant';
  if (isBeforeStart(d, month)) return 'pre-contract';
  return isPaid(d, month) ? 'paid' : 'unpaid';
}

const PAYMENT_STATUS_INFO = {
  'pre-contract': { label: '대기', color: '#9e9e9e' },
  'paid':         { label: '완납', color: '#26a69a' },
  'unpaid':       { label: '미납', color: '#e91e63' },
  'vacant':       { label: '-',   color: '#9e9e9e' },
};

// statusClass()의 vacant/pre-contract/paid/unpaid 판단을 재사용해 라벨/색상만 매핑.
// (renderVirtualList가 같은 판단을 독립적으로 다시 계산하던 것을 여기로 일원화)
function paymentStatusInfo(id, data, month) {
  return PAYMENT_STATUS_INFO[statusClass(id, data, month)];
}

function computeStats(data, month) {
  const vKeys    = Object.keys(data).filter(r => isOccupied(data[r]) && isVirtual(r, data[r]) && !ALL_ROOMS.includes(r));
  const occ      = [...ALL_ROOMS.filter(r => isOccupied(data[r])), ...vKeys];
  const virtual  = occ.filter(r => isVirtual(r, data[r]));
  const resident = occ.filter(r => !isVirtual(r, data[r]));
  const paid     = occ.filter(r => !isBeforeStart(data[r], month) && isPaid(data[r], month));
  const unpaid   = occ.filter(r => !isBeforeStart(data[r], month) && !isPaid(data[r], month));
  const paidThisMonth = occ.filter(r => !isBeforeStart(data[r], month) && isPaidThisMonth(data[r], month));
  const rPaidAmt    = paidThisMonth.filter(r => !isVirtual(r, data[r])).reduce((s,r) => s + ((data[r] && data[r].rent)||0), 0);
  const vPaidAmt    = paidThisMonth.filter(r =>  isVirtual(r, data[r])).reduce((s,r) => s + ((data[r] && data[r].rent)||0), 0);
  const unpaidAmt   = unpaid.reduce((s,r) => s + ((data[r] && data[r].rent)||0), 0);
  const depositTotal = ALL_ROOMS
    .filter(r => isOccupied(data[r]) && !isVirtual(r, data[r]) && data[r] && data[r].depositPaid && data[r].depositPaidMonth === month)
    .reduce((s, r) => s + depositAmount(r), 0);
  const activeVirtualCount = virtual.filter(r => isActiveContract(data[r])).length;

  return {
    totalRooms:    ALL_ROOMS.length,
    residentCount: resident.length,
    virtualCount:  virtual.length,
    activeVirtualCount,
    vacantCount:   ALL_ROOMS.length - resident.length,
    occupancyRate: Math.round(resident.length / ALL_ROOMS.length * 100),
    rPaidAmt, vPaidAmt, totalPaidAmt: rPaidAmt + vPaidAmt + depositTotal, unpaidAmt, depositTotal,
    curMonthNum: parseInt(month.split('-')[1]),
  };
}

// 만료 알림 — 항상 오늘 기준 (뷰 월과 무관하게 지금 당장 임박한 계약을 표시)
function computeExpiryAlerts(data) {
  const today = new Date(); today.setHours(0, 0, 0, 0);

  const residentExpiring = ALL_ROOMS.filter(r => {
    const d = data[r];
    return isOccupied(d) && !isVirtual(r, d) && daysLeft(d.end) !== null;
  }).length;

  const vExpiring = Object.keys(data)
    .filter(r => isOccupied(data[r]) && isVirtual(r, data[r]) && !ALL_ROOMS.includes(r))
    .map(r => {
      const d = data[r]; if (!d.end) return null;
      const end  = new Date(d.end + 'T00:00:00');
      const diff = Math.ceil((end - today) / 86400000);
      return diff <= 30 ? { id: r, name: d.name || d.tenantName || r, diff } : null;
    })
    .filter(Boolean)
    .sort((a, b) => a.diff - b.diff);

  return { expiring: residentExpiring, vExpiring };
}

function calcRent(baseRent, discount, vat) {
  return Math.floor(Math.round(baseRent * (1 - discount) * (vat ? 1.1 : 1)) / 100) * 100;
}

// 비상주 계약금액 — 선납이면 계약 개월수 전체를 일괄 청구, 월납이면 단가만.
// VAT 10% 포함. 자세한 공식은 CONTEXT.md "비상주 임대료" 참고.
function computeVaRent(isCorp, prepaid, months) {
  var base   = isCorp ? VIRTUAL_RENT_CORP : VIRTUAL_RENT_INDIVIDUAL;
  var amount = prepaid ? base * months : base;
  return calcRent(amount, 0, true);
}

function proratedRent(monthlyRent, startDateStr) {
  if (!startDateStr) return null;
  var startDate = new Date(startDateStr + 'T00:00:00');
  var day = startDate.getDate();
  if (day === 1) return null;
  var month = startDate.getMonth();
  var daysInMonth = new Date(startDate.getFullYear(), month + 1, 0).getDate();
  var daysUsed = daysInMonth - day + 1;
  return {
    month: month + 1, day, daysInMonth, daysUsed,
    amount: Math.floor(Math.round(monthlyRent / daysInMonth * daysUsed) / 100) * 100,
  };
}

// 퇴거 일할계산 — 계약 만료일이 속한 마지막 달의 1일~만료일까지 요금.
// 만료일이 말일이면 마지막 달도 온전한 한 달이라 null. 시작월과 같은 달에 끝나면(단기) null.
function proratedRentExit(monthlyRent, startDateStr, endDateStr) {
  if (!endDateStr) return null;
  var endDate = new Date(endDateStr + 'T00:00:00');
  var day = endDate.getDate();
  var month = endDate.getMonth();
  var daysInMonth = new Date(endDate.getFullYear(), month + 1, 0).getDate();
  if (day === daysInMonth) return null;
  if (startDateStr) {
    var s = new Date(startDateStr + 'T00:00:00');
    if (s.getFullYear() === endDate.getFullYear() && s.getMonth() === month) return null;
  }
  return {
    month: month + 1, day, daysInMonth, daysUsed: day,
    amount: Math.floor(Math.round(monthlyRent / daysInMonth * day) / 100) * 100,
  };
}

function inferContractMonths(d) {
  if (d && d.contractMonths) return d.contractMonths;
  return 12;
}

function depositAmount(roomId) {
  return (BASE_RENT[roomId] || 0) * 2;
}

// UTC 변환(toISOString) 대신 로컬 getter로 포맷 — KST(UTC+9)에서 toISOString을 쓰면
// 자정이 하루 앞으로 밀려 날짜가 하루씩 당겨지는 버그가 생김 (todayLocal()과 동일한 이유)
function addMonthsToDate(dateStr, n) {
  var d = new Date(dateStr + 'T00:00:00');
  d.setMonth(d.getMonth() + n);
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}

function addDays(dateStr, n) {
  var d = new Date(dateStr + 'T00:00:00');
  d.setDate(d.getDate() + n);
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}

// 계약기간 종료일 — 실제 사용일수 기준(시작일 포함, N개월 뒤 하루 전날이 마지막 날).
// 예: 1/1 시작 12개월 → 12/31 (다음해 1/1이 아님), 2/1 시작 12개월 → 익년 1/31.
function contractEndDate(startDateStr, months) {
  return addDays(addMonthsToDate(startDateStr, months), -1);
}

function getMonthRange(start, end) {
  if (!start) return [];
  var s = new Date(start.slice(0, 7) + '-01');
  var e = end ? new Date(end.slice(0, 7) + '-01') : s;
  var months = [];
  var cur = new Date(s);
  while (cur <= e) {
    months.push(cur.getFullYear() + '-' + String(cur.getMonth() + 1).padStart(2, '0'));
    cur.setMonth(cur.getMonth() + 1);
  }
  return months;
}
