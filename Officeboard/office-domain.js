// 순수 도메인 함수 및 상수 — DOM 없음, 전역 상태 없음
// 이 파일만 import해서 Node.js/브라우저 양쪽에서 테스트 가능

const ZONE = {
  A: { color: '#1565c0', name: 'A구역' },
  B: { color: '#e65100', name: 'B구역' },
  C: { color: '#2e7d32', name: 'C구역' },
  D: { color: '#6a1b9a', name: 'D구역' },
};

const BASE_RENT = {
  A002:430000, A003:430000, A004:430000, A005:430000, A006:430000, A007:430000, A010:430000,
  A008:500000, A009:500000,
  A011:330000, A012:330000, A013:330000,
  A014:380000, A015:380000, A016:380000, A017:380000,
  B001:380000, B002:380000,
  B003:330000, B004:330000, B005:330000, B006:330000, B007:330000,
  B008:550000, B009:550000,
  B010:380000, B011:380000, B012:380000, B013:380000, B014:380000,
  C001:380000, C002:380000,
  C003:280000, C004:280000, C005:280000, C006:280000, C007:280000, C008:280000,
  C009:430000, C010:430000, C011:430000, C012:430000, C013:430000, C014:430000,
  C015:430000, C016:430000, C017:430000, C018:430000,
};

const VIRTUAL_RENT_BASE = 290400;

const LAYOUT = [
  [null,null,null,null,null,null,null,null,null,null,'GAP',null,'GAP','A001'],
  [null,null,null,null,null,null,null,null,null,null,'GAP',null,'GAP','A002'],
  ['B008','B007','B006','B005','B004','B003',null,null,'B001','A018','GAP','A011','GAP','A003'],
  [null,null,null,null,null,null,null,null,'B002','A017','GAP','A012','GAP','A004'],
  ['B009','B010','B011','B012','B013','B014',null,null,'C001','A016','GAP','A013','GAP','A005'],
  ['C009','C008','C007','C006','C005','C004','C003',null,'C002','A015','GAP','A014','GAP','A006'],
  [null,null,null,null,null,null,null,null,null,null,'GAP',null,'GAP','A007'],
  ['C010','C011','C012','C013','C014','C015','C016','C017','C018','A010','GAP','A009','GAP','A008'],
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

// "A018-2" → "A018(2)", "A018" → "A018"
function displayVaId(id) {
  const m = id.match(/^(.+)-(\d+)$/);
  return m ? `${m[1]}(${m[2]})` : id;
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

function isBeforeStart(d) { return !!(d && d.start && d.start > todayLocal()); }

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
  if (isBeforeStart(d)) return 'pre-contract';
  return isPaid(d, month) ? 'paid' : 'unpaid';
}

function computeStats(data, month) {
  const vKeys    = Object.keys(data).filter(r => /^V\d+$/.test(r) && isOccupied(data[r]));
  const occ      = [...ALL_ROOMS.filter(r => isOccupied(data[r])), ...vKeys.filter(r => !ALL_ROOMS.includes(r))];
  const virtual  = occ.filter(r => isVirtual(r, data[r]));
  const resident = occ.filter(r => !isVirtual(r, data[r]));
  const paid     = occ.filter(r => !isBeforeStart(data[r]) && isPaid(data[r], month));
  const unpaid   = occ.filter(r => !isBeforeStart(data[r]) && !isPaid(data[r], month));
  const rPaidAmt    = paid.filter(r => !isVirtual(r, data[r])).reduce((s,r) => s + ((data[r] && data[r].rent)||0), 0);
  const vPaidAmt    = paid.filter(r =>  isVirtual(r, data[r])).reduce((s,r) => s + ((data[r] && data[r].rent)||0), 0);
  const unpaidAmt   = unpaid.reduce((s,r) => s + ((data[r] && data[r].rent)||0), 0);
  const depositTotal = ALL_ROOMS
    .filter(r => isOccupied(data[r]) && !isVirtual(r, data[r]) && data[r] && data[r].depositPaid && data[r].depositPaidMonth === month)
    .reduce((s, r) => s + depositAmount(r), 0);
  const expiring    = occ.filter(r => !isVirtual(r, data[r]) && !isBeforeStart(data[r]) && daysLeft(data[r] && data[r].end) !== null).length;

  const today = new Date(); today.setHours(0,0,0,0);
  const vExpiring = vKeys.map(r => {
    const d = data[r]; if (!d.end) return null;
    const end = new Date(d.end + 'T00:00:00');
    const diff = Math.ceil((end - today) / 86400000);
    return diff <= 30 ? { id: r, name: d.name || d.tenantName || r, diff } : null;
  }).filter(Boolean).sort((a,b) => a.diff - b.diff);

  const activeVirtualCount = virtual.filter(r => isActiveContract(data[r])).length;

  return {
    totalRooms:    ALL_ROOMS.length,
    residentCount: resident.length,
    virtualCount:  virtual.length,
    activeVirtualCount,
    vacantCount:   ALL_ROOMS.length - resident.length,
    occupancyRate: Math.round(resident.length / ALL_ROOMS.length * 100),
    rPaidAmt, vPaidAmt, totalPaidAmt: rPaidAmt + vPaidAmt + depositTotal, unpaidAmt, depositTotal,
    expiring, vExpiring,
    curMonthNum: parseInt(month.split('-')[1]),
  };
}

function calcRent(baseRent, discount, vat) {
  return Math.floor(Math.round(baseRent * (1 - discount) * (vat ? 1.1 : 1)) / 100) * 100;
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

function inferContractYears(d) {
  if (d && d.contractYears) return d.contractYears;
  return Math.max(1, Math.min(3, Math.round(((d && d.rent) || VIRTUAL_RENT_BASE) / VIRTUAL_RENT_BASE)));
}

function depositAmount(roomId) {
  return (BASE_RENT[roomId] || 0) * 2;
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
