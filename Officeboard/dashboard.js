// ── 상태 ────────────────────────────────────────────
let currentMonth   = new Date().toISOString().slice(0, 7);
let currentRoom    = null;
let _editingVaId   = null; // VA 수정 시 원본 ID 추적 (ID 변경 감지용)
let _vaShowInactive = false; // 비상주 목록 계약해지·만료 표시 여부 유지
let _vaSort = { col: 'start', asc: true }; // 비상주 목록 정렬 상태

// ── 데이터 레이어 ────────────────────────────────────
let _DATA       = {};
let _dataLoaded = false;

function getAllData() { return _DATA; }

async function store(data, force) {
  if (!_dataLoaded && !force) throw new Error('데이터 로드 미완료 — 새로고침 후 시도해주세요.');
  const res = await fetch('/data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('서버 저장 실패 (' + res.status + ')');
  _DATA = data;
}

async function removeRoom(id) {
  const data = Object.assign({}, getAllData());
  delete data[id];
  return store(data);
}

// ── PaymentGrid ──────────────────────────────────────
// 납부 현황 그리드 — 체크박스 상태를 DOM이 아닌 JS 변수로 보유.
// residentGrid / vaGrid 두 인스턴스가 같은 인터페이스를 구현 → 실제 seam.
class PaymentGrid {
  constructor({ gridId, prepaidId, wrapId, cbClass }) {
    this.gridId    = gridId;
    this.prepaidId = prepaidId;
    this.wrapId    = wrapId;
    this.cbClass   = cbClass;
    this._state    = {}; // YYYY-MM -> bool
    this._months   = [];
  }

  // 최초 로드: 저장된 데이터 기준으로 상태 초기화 후 렌더
  load(storedData, months) {
    this._months = months;
    const next = {};
    months.forEach(m => { next[m] = !!(storedData && storedData['paid_' + m]); });
    this._state = next;
    this._render();
  }

  // 계약 기간 변경: 기존 미저장 변경사항 보존, 새 달은 DB에서 채움
  setMonths(months, storedData) {
    const next = {};
    months.forEach(m => {
      next[m] = (m in this._state) ? this._state[m] : !!(storedData && storedData['paid_' + m]);
    });
    this._state  = next;
    this._months = months;
    this._render();
  }

  // 선납완료 체크박스
  setAll(val) {
    this._months.forEach(m => { this._state[m] = val; });
    this._render();
  }

  // saveRoom / saveVirtualCustomer 에서 호출
  getValues() {
    const out = {};
    this._months.forEach(m => { out['paid_' + m] = !!this._state[m]; });
    return out;
  }

  _render() {
    const grid = document.getElementById(this.gridId);
    grid.innerHTML = '';
    this._months.forEach(m => {
      const paid = !!this._state[m];
      const lbl  = document.createElement('label');
      lbl.className = 'month-pay-item' + (paid ? ' is-paid' : '');
      lbl.innerHTML =
        `<input type="checkbox" class="${this.cbClass}" value="${m}"${paid ? ' checked' : ''}> ${m.replace('-', '.')}`;
      lbl.querySelector('input').addEventListener('change', e => {
        this._state[m] = e.target.checked;
        lbl.classList.toggle('is-paid', e.target.checked);
        if (!e.target.checked) {
          document.getElementById(this.prepaidId).checked = false;
          document.getElementById(this.wrapId).classList.remove('active');
        }
      });
      grid.appendChild(lbl);
    });
  }
}

const residentGrid = new PaymentGrid({
  gridId: 'month-pay-grid', prepaidId: 'f-prepaid', wrapId: 'prepaid-wrap', cbClass: 'month-pay-checkbox',
});
const vaGrid = new PaymentGrid({
  gridId: 'va-month-pay-grid', prepaidId: 'va-prepaid', wrapId: 'va-prepaid-wrap', cbClass: 'va-month-pay-cb',
});

// ── 공통 헬퍼 ──────────────────────────────────────
function _addMonths(ym, n) {
  var y = parseInt(ym.slice(0, 4));
  var m = parseInt(ym.slice(5, 7)) + n;
  while (m > 12) { m -= 12; y++; }
  while (m < 1)  { m += 12; y--; }
  return y + '-' + String(m).padStart(2, '0');
}

// 납부그리드: 계약 시작월 기준 12개월 (3행 × 4열)
function _gridMonths(startVal) {
  var base = startVal ? startVal.slice(0, 7) : currentMonth;
  var months = [];
  for (var i = 0; i < 12; i++) months.push(_addMonths(base, i));
  return months;
}

// ── 상주 모달 — 내부 헬퍼 ──────────────────────────
function _populateDepositMonthSelect(startStr, savedMonth) {
  var sel  = document.getElementById('f-deposit-month');
  var base = startStr ? startStr.slice(0, 7) : currentMonth;
  sel.innerHTML = '';
  [-1, 0, 1].forEach(function(offset) {
    var ym  = _addMonths(base, offset);
    var opt = document.createElement('option');
    opt.value       = ym;
    opt.textContent = parseInt(ym.slice(5, 7)) + '월';
    sel.appendChild(opt);
  });
  var target = savedMonth || base;
  sel.value = Array.from(sel.options).some(o => o.value === target) ? target : base;
}

function _applyServiceState() {
  var isService  = document.getElementById('f-service').checked;
  var sWrap      = document.getElementById('prorated-service-wrap');
  if (!sWrap || sWrap.style.display === 'none') return;
  var resultEl   = document.getElementById('prorated-result');
  var serviceMsg = document.getElementById('daily-service-msg');
  if (isService) {
    resultEl.style.display   = 'none';
    serviceMsg.style.display = 'block';
    sWrap.style.background   = '#e8f5e9';
    sWrap.style.borderColor  = '#66bb6a';
  } else {
    resultEl.style.display   = '';
    serviceMsg.style.display = 'none';
    sWrap.style.background   = '#fff8e1';
    sWrap.style.borderColor  = '#ffe082';
  }
}

function _updateDailyRent() {
  var sWrap   = document.getElementById('prorated-service-wrap');
  var startVal = document.getElementById('f-start').value;
  if (!startVal) { sWrap.style.display = 'none'; return; }
  var monthly = parseInt(document.getElementById('f-rent').value.replace(/,/g, '').trim(), 10);
  if (!monthly) { sWrap.style.display = 'none'; return; }
  var result = proratedRent(monthly, startVal);
  if (!result)  { sWrap.style.display = 'none'; return; }
  document.getElementById('prorated-result').textContent = fmtWon(result.amount) + '원';
  document.getElementById('prorated-detail-line').textContent =
    result.month + '월 ' + result.day + '일~' + result.daysInMonth + '일 (' +
    result.daysUsed + '일, ' + result.daysInMonth + '일 기준)';
  sWrap.style.display = '';
  _applyServiceState();
}

// ── roomToForm — DB 데이터 → 모달 폼 채우기 ──────────
function _roomToForm(roomId, d) {
  var base  = BASE_RENT[roomId];
  var z     = zone(roomId);
  var color = ZONE[z].color;

  document.getElementById('modal-type-bar').style.background   = color;
  document.getElementById('modal-title').textContent           = roomId;
  document.getElementById('modal-type-label').textContent      = ZONE[z].name;
  document.getElementById('modal-type-label').style.background = color;

  document.getElementById('f-name').value        = d.name        || '';
  document.getElementById('f-tenant-name').value = d.tenantName  || '';
  document.getElementById('f-phone').value       = d.phone       || '';
  document.getElementById('f-start').value       = d.start       || '';
  document.getElementById('f-end').value         = d.end         || '';
  document.getElementById('f-memo').value        = d.memo        || '';
  document.getElementById('f-memo2').value       = d.memo2       || '';

  var cStatus = d.contractStatus || '계약중';
  document.querySelectorAll('.status-btn').forEach(function(b) {
    b.classList.remove('s-active', 's-expired', 's-canceled');
    if (b.getAttribute('data-status') === cStatus) applyStatusClass(b);
  });

  if (base) {
    document.getElementById('base-rent-display').textContent      = fmtWon(base) + '원';
    document.getElementById('base-rent-row').style.display        = 'flex';
    document.getElementById('deposit-amount-display').textContent = fmtWon(depositAmount(roomId)) + '원';
    document.getElementById('f-deposit-paid').checked             = !!(d.depositPaid);
    document.getElementById('deposit-group').style.display        = '';
    _populateDepositMonthSelect(d.start, d.depositPaidMonth);
  } else {
    document.getElementById('base-rent-row').style.display  = 'none';
    document.getElementById('deposit-group').style.display  = 'none';
  }

  document.getElementById('f-invoice').checked = !!(d['invoice_' + currentMonth]);
  document.getElementById('f-vat').checked = !!(d.vat);
  var discSel = document.getElementById('f-discount-select');
  if (discSel) discSel.value = String(d.discount || 0);

  if (d.rent) {
    document.getElementById('f-rent').value = fmtWon(d.rent);
  } else if (base) {
    document.getElementById('f-rent').value = fmtWon(calcRent(base, d.discount || 0, !!(d.vat)));
  } else {
    document.getElementById('f-rent').value = '';
  }

  document.getElementById('f-prepaid').checked = !!(d.prepaid);
  document.getElementById('prepaid-wrap').classList.toggle('active', !!(d.prepaid));
  residentGrid.load(d, _gridMonths(d.start));

  var tag  = daysLeft(d.end);
  var warn = document.getElementById('expiry-warn');
  if (tag && isOccupied(d)) {
    warn.style.display = 'block';
    warn.textContent   = tag === '만료'
      ? '⚠ 계약이 만료되었습니다 (' + d.end + ')'
      : '⚠ 계약 만료 ' + tag + ' (만료일: ' + d.end + ')';
  } else {
    warn.style.display = 'none';
  }

  document.getElementById('f-service').checked = !!(d.dailyService);
  document.getElementById('prorated-service-wrap').style.display = 'none';
  document.getElementById('btn-vacate').style.display = isOccupied(d) ? 'inline-block' : 'none';
  _updateDailyRent();
}

// ── formToRoom — 모달 폼 읽기 → RoomData 객체 ────────
function _formToRoom(prev) {
  var vat      = document.getElementById('f-vat').checked;
  var discSel  = document.getElementById('f-discount-select');
  var discount = discSel ? parseFloat(discSel.value) : 0;
  var rent     = parseInt(document.getElementById('f-rent').value.replace(/,/g, '').trim(), 10) || 0;

  return Object.assign({}, prev, {
    name:       document.getElementById('f-name').value.trim(),
    tenantName: document.getElementById('f-tenant-name').value.trim(),
    ['invoice_' + currentMonth]: document.getElementById('f-invoice').checked,
    phone:      document.getElementById('f-phone').value.trim(),
    start:      document.getElementById('f-start').value,
    end:        document.getElementById('f-end').value,
    rent, vat, discount,
    depositPaid: document.getElementById('f-deposit-paid').checked,
    depositPaidMonth: document.getElementById('f-deposit-paid').checked
      ? document.getElementById('f-deposit-month').value
      : null,
    contractStatus: (function() {
      var b = document.querySelector(
        '#modal-overlay .status-btn.s-active,' +
        '#modal-overlay .status-btn.s-expired,' +
        '#modal-overlay .status-btn.s-canceled'
      );
      return b ? b.getAttribute('data-status') : '계약중';
    })(),
    memo:         document.getElementById('f-memo').value.trim(),
    memo2:        document.getElementById('f-memo2').value.trim(),
    prepaid:      document.getElementById('f-prepaid').checked,
    prepaidAt:    document.getElementById('f-prepaid').checked
      ? (prev.prepaidAt || currentMonth)
      : null,
    dailyService: document.getElementById('f-service').checked,
  }, residentGrid.getValues());
}

// ── 상주 모달 — 이벤트 핸들러 ───────────────────────
function openModal(id) {
  currentRoom = id;
  _roomToForm(id, getAllData()[id] || {});
  document.getElementById('modal-overlay').classList.add('active');
  setTimeout(() => document.getElementById('f-name').focus(), 60);
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('active');
  resetOverlay();
  currentRoom = null;
}

// 계약 시작일 변경 → 임대료 파생 + 납부그리드 + 보증금월 (3개 업데이트를 단일 핸들러로 집약)
function onStartChange() {
  var startVal   = document.getElementById('f-start').value;
  var storedData = currentRoom ? (getAllData()[currentRoom] || {}) : {};
  _updateDailyRent();
  residentGrid.setMonths(_gridMonths(startVal), storedData);
  _populateDepositMonthSelect(startVal, document.getElementById('f-deposit-month').value);
}

// 계약 만료일 변경 → 그리드는 시작월 기준이므로 변화 없음 (호환성 유지)
function onEndChange() {}

// VAT / 할인율 변경 → 임대료 자동 계산
function updateRentCalc() {
  if (!currentRoom || !BASE_RENT[currentRoom]) return;
  var vat      = document.getElementById('f-vat').checked;
  var discSel  = document.getElementById('f-discount-select');
  var discount = discSel ? parseFloat(discSel.value) : 0;
  document.getElementById('f-rent').value = fmtWon(calcRent(BASE_RENT[currentRoom], discount, vat));
  _updateDailyRent();
}

// 임대료 직접 입력 → 일할계산 갱신
function updateDailyRent() { _updateDailyRent(); }

// 보증금 납부완료 체크 → 계약 시작월로 리셋
function onDepositPaidChange() {
  if (!document.getElementById('f-deposit-paid').checked) return;
  var startVal = document.getElementById('f-start').value;
  if (startVal) _populateDepositMonthSelect(startVal, startVal.slice(0, 7));
}

// 선납완료 체크
function onPrepaidChange() {
  var prepaid = document.getElementById('f-prepaid').checked;
  document.getElementById('prepaid-wrap').classList.toggle('active', prepaid);
  residentGrid.setAll(prepaid);
}

// 서비스 기간 체크
function onServiceChange() { _applyServiceState(); }

// 계약 상태 버튼
function applyStatusClass(btn) {
  var map = { '계약중': 's-active', '계약만료': 's-expired', '계약해지': 's-canceled' };
  btn.classList.add(map[btn.getAttribute('data-status')] || 's-active');
}

function selectContractStatus(btn) {
  document.querySelectorAll('#modal-overlay .status-btn').forEach(function(b) {
    b.classList.remove('s-active', 's-expired', 's-canceled');
  });
  applyStatusClass(btn);
}

async function saveRoom() {
  if (!currentRoom) return;
  const data     = Object.assign({}, getAllData());
  const prev     = data[currentRoom] || {};
  const roomData = _formToRoom(prev);

  if (!roomData.name && !roomData.tenantName) {
    delete data[currentRoom];
  } else {
    data[currentRoom] = roomData;
  }
  try {
    await store(data);
    closeModal();
    renderFloor();
    renderStats();
    toast('저장되었습니다.');
  } catch(e) {
    toast('저장 실패 — 네트워크를 확인 후 다시 시도해주세요.');
  }
}

async function vacateRoom() {
  if (!currentRoom) return;
  if (!confirm(currentRoom + ' 퇴실 처리하시겠습니까?\n입력된 모든 정보가 삭제됩니다.')) return;
  try {
    await removeRoom(currentRoom);
    closeModal();
    renderFloor();
    renderStats();
    toast('퇴실 처리되었습니다.');
  } catch(e) {
    toast('저장 실패 — 네트워크를 확인 후 다시 시도해주세요.');
  }
}

// ── 비상주 모달 ─────────────────────────────────────
function nextVirtualId() {
  const data = getAllData();
  let max = 0;
  Object.keys(data).forEach(id => {
    const m = id.match(/^V(\d+)$/);
    if (m) { const n = parseInt(m[1], 10); if (n > max) max = n; }
  });
  return 'V' + String(max + 1).padStart(3, '0');
}

function openVirtualAdd(id) {
  const data  = getAllData();
  const d     = id ? (data[id] || {}) : {};
  const newId = id || nextVirtualId();
  _editingVaId = id || null;

  document.getElementById('virtual-add-title').textContent = id ? (displayVaId(id) + ' 수정') : '비상주 신규 등록';
  var idInput = document.getElementById('va-id');
  idInput.value      = newId;
  idInput.readOnly   = false;
  idInput.style.background = '';
  idInput.style.color      = '';

  document.getElementById('va-name').value   = d.name       || '';
  document.getElementById('va-tenant').value = d.tenantName || '';
  document.getElementById('va-phone').value  = d.phone      || '';
  document.getElementById('va-start').value  = d.start      || '';
  document.getElementById('va-end').value    = d.end        || '';
  document.getElementById('va-memo').value   = d.memo       || '';

  var years = inferContractYears(d);
  document.querySelectorAll('.period-btn').forEach(function(b) {
    b.classList.remove('selected');
    if (parseInt(b.getAttribute('data-years'), 10) === years) b.classList.add('selected');
  });
  document.getElementById('va-rent').value = fmtWon(VIRTUAL_RENT_BASE * years);
  document.getElementById('va-btn-delete').style.display = id ? 'inline-block' : 'none';

  var cStatus = d.contractStatus || '계약중';
  document.querySelectorAll('#va-status-options .status-btn').forEach(function(b) {
    b.classList.remove('s-active', 's-expired', 's-canceled');
    if (b.getAttribute('data-status') === cStatus) applyStatusClass(b);
  });

  document.getElementById('va-prepaid').checked = !!(d.prepaid);
  document.getElementById('va-prepaid-wrap').classList.toggle('active', !!(d.prepaid));
  vaGrid.load(d, _gridMonths(d.start));

  document.getElementById('virtual-add-overlay').classList.add('active');
}

function closeVirtualAdd() {
  document.getElementById('virtual-add-overlay').classList.remove('active');
}

function getVaPeriodYears() {
  var sel = document.querySelector('.period-btn.selected');
  return sel ? parseInt(sel.getAttribute('data-years'), 10) : 1;
}

function selectVaPeriod(btn) {
  document.querySelectorAll('.period-btn').forEach(function(b) { b.classList.remove('selected'); });
  btn.classList.add('selected');
  var startVal = document.getElementById('va-start').value;
  if (startVal) _updateVaEndFromPeriod(startVal);
  document.getElementById('va-rent').value = fmtWon(VIRTUAL_RENT_BASE * getVaPeriodYears());
}

function _updateVaEndFromPeriod(startVal) {
  var years = getVaPeriodYears();
  var d     = new Date(startVal + 'T00:00:00');
  d.setFullYear(d.getFullYear() + years);
  document.getElementById('va-end').value = d.toISOString().slice(0, 10);
  var storedData = getAllData()[document.getElementById('va-id').value] || {};
  vaGrid.setMonths(_gridMonths(startVal), storedData);
}

function onVaStartChange() {
  var startVal = document.getElementById('va-start').value;
  if (!startVal) return;
  _updateVaEndFromPeriod(startVal);
}

function onVaEndChange() {
  var startVal   = document.getElementById('va-start').value;
  var storedData = getAllData()[document.getElementById('va-id').value] || {};
  vaGrid.setMonths(_gridMonths(startVal), storedData);
}

function onVaPrepaidChange() {
  var prepaid = document.getElementById('va-prepaid').checked;
  document.getElementById('va-prepaid-wrap').classList.toggle('active', prepaid);
  vaGrid.setAll(prepaid);
}

function selectVaStatus(btn) {
  document.querySelectorAll('#va-status-options .status-btn').forEach(function(b) {
    b.classList.remove('s-active', 's-expired', 's-canceled');
  });
  applyStatusClass(btn);
}

async function saveVirtualCustomer() {
  const data        = Object.assign({}, getAllData());
  const id          = document.getElementById('va-id').value.trim();
  const name        = document.getElementById('va-name').value.trim();
  const tenantName  = document.getElementById('va-tenant').value.trim();
  if (!id)                    { toast('고객 ID를 입력해주세요.'); return; }
  if (!name && !tenantName)   { toast('상호명 또는 입주자 이름을 입력해주세요.'); return; }

  // 신규 등록 시 ID 충돌이면 자동으로 A018-2, A018-3 등 부여
  const finalId  = _editingVaId ? id : nextSuffixedVaId(id, data);
  const prevData = _editingVaId ? (data[_editingVaId] || {}) : {};
  if (_editingVaId && _editingVaId !== finalId) delete data[_editingVaId];

  var years     = getVaPeriodYears();
  var rentInput = parseInt(document.getElementById('va-rent').value.replace(/,/g, '').trim(), 10) || 0;
  var statusBtn = document.querySelector(
    '#va-status-options .status-btn.s-active,' +
    '#va-status-options .status-btn.s-expired,' +
    '#va-status-options .status-btn.s-canceled'
  );

  data[finalId] = Object.assign({}, prevData, {
    name, tenantName,
    phone:         document.getElementById('va-phone').value.trim(),
    start:         document.getElementById('va-start').value,
    end:           document.getElementById('va-end').value,
    vat:           true,
    discount:      0,
    rent:          rentInput,
    contractYears: years,
    contractType:  '비상주',
    contractStatus: statusBtn ? statusBtn.getAttribute('data-status') : '계약중',
    memo:          document.getElementById('va-memo').value.trim(),
    prepaid:       document.getElementById('va-prepaid').checked,
    prepaidAt:     document.getElementById('va-prepaid').checked
      ? (prevData.prepaidAt || currentMonth)
      : null,
  }, vaGrid.getValues());

  try {
    await store(data);
    closeVirtualAdd();
    renderFloor();
    renderStats();
    toast(finalId !== id ? `${displayVaId(finalId)}로 저장되었습니다.` : '저장되었습니다.');
    setTimeout(showVirtualList, 80);
  } catch(e) { toast('저장 실패 — 네트워크를 확인해주세요.'); }
}

async function deleteVirtualCustomer() {
  const id = document.getElementById('va-id').value;
  if (!id || !confirm(id + ' 고객을 삭제하시겠습니까?')) return;
  try {
    await removeRoom(id);
    closeVirtualAdd();
    renderFloor();
    renderStats();
    toast('삭제되었습니다.');
    setTimeout(showVirtualList, 80);
  } catch(e) { toast('삭제 실패.'); }
}

// ── 평면도 렌더 ─────────────────────────────────────
function renderFloor() {
  const data = getAllData();
  const grid = document.getElementById('floor-grid');
  grid.innerHTML = '';

  LAYOUT.forEach(row => {
    const rowEl = document.createElement('div');
    rowEl.className = 'floor-row';

    row.forEach(cell => {
      const el = document.createElement('div');
      el.className = 'cell';

      if (!cell) {
        el.classList.add('cell-empty');
      } else if (cell === 'GAP') {
        el.classList.add('cell-gap');
      } else if (cell === 'U') {
        el.classList.add('cell-util');
      } else if (cell === 'CORR') {
        el.classList.add('cell-corridor');
        el.textContent = '복도';
      } else {
        const z     = zone(cell);
        const raw   = data[cell] || {};
        const d     = isVirtual(cell, raw) ? {} : raw; // 비상주 ID는 상주 상황판에서 공실로 표시
        const st    = statusClass(cell, { ...data, [cell]: d }, currentMonth);
        const tag   = daysLeft(d.end);
        const color = ZONE[z].color;

        el.classList.add('cell-room', st);
        if (tag === '만료' && isOccupied(d)) el.classList.add('expired');
        el.onclick = () => openModal(cell);

        let html = `<div class="type-strip" style="background:${color}"></div>`;
        html += `<div class="room-id">${cell}</div>`;
        html += `<div class="room-name">${d.name || d.tenantName || '공실'}</div>`;
        if (isOccupied(d) && d.rent) {
          html += `<div class="room-rent">${fmtWon(d.rent)}원</div>`;
        } else if (!isOccupied(d) && BASE_RENT[cell]) {
          html += `<div class="room-vacant-price">${fmtWon(calcRent(BASE_RENT[cell], 0.3, false))}원</div>`;
        }
        const isExpired = tag === '만료';
        if (isOccupied(d) && st === 'paid'         && !isExpired) html += `<div class="badge-paid">완</div>`;
        if (isOccupied(d) && st === 'unpaid'       && !isExpired) html += `<div class="badge-miss">미</div>`;
        if (isOccupied(d) && d['invoice_' + currentMonth] && !isExpired) html += `<div class="badge-invoice">완</div>`;
        if (tag && isOccupied(d))                                 html += `<div class="badge-expiry">${tag}</div>`;
        if (isVirtual(cell, d) && isOccupied(d))                  html += `<div class="badge-virtual">비상주</div>`;

        el.innerHTML = html;
      }
      rowEl.appendChild(el);
    });
    grid.appendChild(rowEl);
  });
}

// ── 통계 렌더 ───────────────────────────────────────
function renderStats() {
  const data = getAllData();
  const {
    totalRooms, residentCount, activeVirtualCount, vacantCount, occupancyRate,
    rPaidAmt, vPaidAmt, totalPaidAmt, unpaidAmt,
    depositTotal, curMonthNum,
  } = computeStats(data, currentMonth);
  const { expiring, vExpiring } = computeExpiryAlerts(data);

  const vAlerts = vExpiring.map(a => {
    const col = a.diff < 0 ? '#c62828' : a.diff <= 7 ? '#e91e63' : '#e65100';
    const lbl = a.diff < 0 ? '계약만료' : `만료 D-${a.diff}`;
    return `<div class="stat-card stat-card-btn" style="border:1.5px solid ${col};background:#fff;" onclick="openVirtualAdd('${a.id}')">
      <div class="stat-value" style="color:${col};font-size:16px;">${displayVaId(a.id)}</div>
      <div class="stat-label" style="color:${col};">${lbl}</div>
    </div>`;
  }).join('');

  document.getElementById('stats-bar').innerHTML = `
    <div class="stat-card" style="background:#fff;border-color:#ddd;">
      <div class="stat-value" style="color:#1a1a1a">${totalRooms}</div>
      <div class="stat-label" style="color:#666;">전체 호실</div>
    </div>
    <div class="stat-card" style="background:#fff;border-color:#ddd;">
      <div class="stat-value" style="color:#0d47a1">${residentCount}</div>
      <div class="stat-label" style="color:#666;">상주</div>
    </div>
    <div class="stat-card stat-card-btn" style="background:#fff;border-color:#ddd;" onclick="showVirtualList()">
      <div class="stat-value" style="color:#546e7a">${activeVirtualCount}</div>
      <div class="stat-label" style="color:#666;">비상주 &#9654;</div>
    </div>
    <div class="stat-card" style="background:#fff;border-color:#ddd;">
      <div class="stat-value" style="color:#888">${vacantCount}</div>
      <div class="stat-label" style="color:#666;">공실</div>
    </div>
    <div class="stat-card" style="background:#fff;border-color:#ddd;">
      <div class="stat-value" style="color:#1a1a1a">${occupancyRate}%</div>
      <div class="stat-label" style="color:#666;">점유율</div>
    </div>
    <div class="stat-card" style="background:#fff;border-color:#ddd;">
      <div class="stat-value" style="color:#00695c">${rPaidAmt.toLocaleString()}</div>
      <div class="stat-label" style="color:#666;">상주납부금액 (원)</div>
    </div>
    <div class="stat-card" style="background:#fff;border-color:#ddd;">
      <div class="stat-value" style="color:#7b1fa2">${depositTotal.toLocaleString()}</div>
      <div class="stat-label" style="color:#666;">보증금 합계 (원)</div>
    </div>
    <div class="stat-card" style="background:#fff;border-color:#ddd;">
      <div class="stat-value" style="color:#546e7a">${vPaidAmt.toLocaleString()}</div>
      <div class="stat-label" style="color:#666;">비상주납부금액 (원)</div>
    </div>
    <div class="stat-card" style="background:#fff;border-color:#ddd;">
      <div class="stat-value" style="color:#1a237e">${totalPaidAmt.toLocaleString()}</div>
      <div class="stat-label" style="color:#666;">${curMonthNum}월 합계금액 (원)</div>
    </div>
    <div class="stat-card" style="background:#fff;border-color:#ddd;">
      <div class="stat-value" style="color:#c62828">${unpaidAmt.toLocaleString()}</div>
      <div class="stat-label" style="color:#666;">미납 (원)</div>
    </div>
    ${expiring > 0 ? `
    <div class="stat-card" style="background:#fff;border-color:#ddd;">
      <div class="stat-value" style="color:#ff6f00">${expiring}건</div>
      <div class="stat-label" style="color:#666;">만료임박·만료</div>
    </div>` : ''}
    <div style="flex:1;min-width:0;"></div>
    ${vAlerts}
    <button class="btn-excel" style="background:#546e7a;align-self:center;white-space:nowrap;font-size:14px;padding:7px 14px;" onclick="openVirtualAdd(null)">&#128203; 비상주 등록하기</button>
  `;

  document.getElementById('type-summary').innerHTML = ['A','B','C','D'].map(z => {
    const rooms   = ALL_ROOMS.filter(r => zone(r) === z);
    const zocc    = rooms.filter(r => isOccupied(data[r])).length;
    const zunpaid = rooms.filter(r =>
      isOccupied(data[r]) && !isBeforeStart(data[r], currentMonth) && !isPaid(data[r], currentMonth)
    ).length;
    return `
      <div class="type-card">
        <div class="type-badge" style="background:${ZONE[z].color}">${z}</div>
        <div class="type-info">
          <strong>${ZONE[z].name} &nbsp; ${zocc}/${rooms.length}</strong>
          ${zunpaid > 0
            ? `<span style="color:#e91e63">미납 ${zunpaid}건</span>`
            : `<span style="color:#26a69a">납부 완료</span>`}
        </div>
      </div>`;
  }).join('');
}

// ── 월 탐색 ─────────────────────────────────────────
function changeMonth(delta) {
  const [y, m] = currentMonth.split('-').map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  currentMonth = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
  updateMonthDisplay();
  renderFloor();
  renderStats();
}

function updateMonthDisplay() {
  const [y, m] = currentMonth.split('-').map(Number);
  document.getElementById('month-display').textContent = y + '년 ' + m + '월';
}

// ── 비상주 목록 ─────────────────────────────────────
function _vaSortRooms(rooms, data) {
  const { col, asc } = _vaSort;
  return rooms.slice().sort((a, b) => {
    const va = col === 'id' ? a : (data[a].start || '');
    const vb = col === 'id' ? b : (data[b].start || '');
    return asc ? va.localeCompare(vb) : vb.localeCompare(va);
  });
}

function _vaSortToggle(col) {
  if (_vaSort.col === col) _vaSort.asc = !_vaSort.asc;
  else _vaSort = { col, asc: true };
  renderVirtualList(_vaShowInactive);
}

function renderVirtualList(showInactive) {
  const data    = getAllData();
  const rooms   = _vaSortRooms(
    Object.keys(data)
      .filter(r => isOccupied(data[r]) && isVirtual(r, data[r]))
      .filter(r => showInactive || isActiveContract(data[r])),
    data
  );
  const content = document.getElementById('virtual-list-content');

  const statusColor = { '계약중': '#1b2838', '계약만료': '#e65100', '계약해지': '#c62828' };
  const addBtn = `<div style="margin-bottom:10px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
    <button class="btn-excel" style="background:#546e7a;" onclick="closeVirtualModal();openVirtualAdd(null);">&#43; 새 고객 추가</button>
    <label style="display:flex;align-items:center;gap:6px;font-size:13px;color:#555;cursor:pointer;user-select:none;">
      <input type="checkbox" id="va-show-inactive" ${showInactive ? 'checked' : ''} onchange="_vaShowInactive=this.checked;renderVirtualList(this.checked)" style="width:15px;height:15px;cursor:pointer;">
      계약해지·만료 포함
    </label>
  </div>`;

  const allRooms = Object.keys(getAllData()).filter(r => isOccupied(getAllData()[r]) && isVirtual(r, getAllData()[r]));
  const hasHidden = !showInactive && allRooms.length > rooms.length;
  const emptyMsg = hasHidden
    ? '계약중인 비상주 고객이 없습니다. (계약해지·만료 포함 체크 시 전체 표시)'
    : '등록된 비상주 고객이 없습니다.';

  if (rooms.length === 0) {
    content.innerHTML = addBtn + `<p style="color:#aaa;text-align:center;padding:20px;">${emptyMsg}</p>`;
  } else {
    const rows = rooms.map(r => {
      const d   = data[r];
      const pre = isBeforeStart(d, currentMonth);
      const ok  = !pre && isPaid(d, currentMonth);
      const cs  = d.contractStatus || '계약중';
      const payColor = ok ? '#26a69a' : pre ? '#9e9e9e' : '#e91e63';
      const payLabel = ok ? '완납'    : pre ? '대기'    : '미납';
      const rowStyle = !isActiveContract(d) ? ' style="opacity:0.5;"' : '';
      return `<tr${rowStyle} onclick="closeVirtualModal();openVirtualAdd('${r}')">
        <td><strong>${displayVaId(r)}</strong></td>
        <td>${d.name || '-'}</td>
        <td>${d.tenantName || '-'}</td>
        <td>${d.phone || '-'}</td>
        <td>${d.start || '-'}</td>
        <td>${d.end || '-'}</td>
        <td>${fmtWon(d.rent) || '-'}</td>
        <td><span style="color:${payColor};font-weight:700;">${payLabel}</span></td>
        <td><span style="color:${statusColor[cs]||'#1b2838'};font-weight:700;">${cs}</span></td>
      </tr>`;
    }).join('');
    const arrow = (col) => _vaSort.col === col ? (_vaSort.asc ? ' ▲' : ' ▼') : '';
    const thStyle = 'cursor:pointer;user-select:none;';
    content.innerHTML = addBtn + `<table class="virtual-table">
      <thead><tr>
        <th style="${thStyle}" onclick="_vaSortToggle('id')">ID${arrow('id')}</th>
        <th>상호명</th><th>입주자</th><th>연락처</th>
        <th style="${thStyle}" onclick="_vaSortToggle('start')">계약시작${arrow('start')}</th>
        <th>계약종료</th><th>월세(원)</th><th>납부현황</th><th>계약상태</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  }
}

function showVirtualList() {
  renderVirtualList(_vaShowInactive);
  document.getElementById('virtual-modal-overlay').classList.add('active');
}

function closeVirtualModal() {
  document.getElementById('virtual-modal-overlay').classList.remove('active');
}

// ── 유틸리티 ────────────────────────────────────────
function formatPhone(input) {
  var v = input.value.replace(/\D/g, '').slice(0, 11);
  if (v.startsWith('02')) {
    if (v.length <= 2)      input.value = v;
    else if (v.length <= 6) input.value = v.slice(0,2) + '-' + v.slice(2);
    else                    input.value = v.slice(0,2) + '-' + v.slice(2, v.length-4) + '-' + v.slice(v.length-4);
  } else {
    if (v.length <= 3)      input.value = v;
    else if (v.length <= 7) input.value = v.slice(0,3) + '-' + v.slice(3);
    else                    input.value = v.slice(0,3) + '-' + v.slice(3,7) + '-' + v.slice(7);
  }
}

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 2000);
}

// ── 엑셀 ────────────────────────────────────────────
async function importExcel(event) {
  const file = event.target.files[0];
  event.target.value = '';
  if (!file) return;
  if (!confirm('현재 데이터를 업로드한 엑셀 파일로 교체합니다.\n계속하시겠습니까?')) return;
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/import', { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await res.text());
    const imported = await res.json();
    if (Object.keys(imported).length === 0) {
      toast('업로드된 데이터가 없습니다. 파일을 확인해주세요.');
      return;
    }
    await store(imported, true);
    _dataLoaded = true;
    renderFloor();
    renderStats();
    toast(Object.keys(imported).length + '개 호실 데이터를 업로드했습니다.');
  } catch(e) {
    toast('업로드 실패 — ' + e.message);
  }
}

async function exportExcel() {
  const data = getAllData();
  if (Object.keys(data).length === 0) { toast('저장된 데이터가 없습니다.'); return; }
  try {
    const res = await fetch('/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data, month: currentMonth }),
    });
    if (!res.ok) throw new Error('서버 오류');
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    const today = new Date();
    a.download = `${String(today.getFullYear()).slice(2)}${String(today.getMonth()+1).padStart(2,'0')}${String(today.getDate()).padStart(2,'0')} 공유오피스 운영 대시보드 백업.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
    toast('엑셀 파일이 저장되었습니다.');
  } catch(e) {
    toast('엑셀 내보내기는 대시보드 프로그램에서만 사용 가능합니다.');
  }
}

// ── 모바일 키보드 대응 ───────────────────────────────
function adjustOverlayForKeyboard() {
  const vv = window.visualViewport;
  if (!vv) return;
  const overlay = document.getElementById('modal-overlay');
  if (!overlay.classList.contains('active')) return;
  overlay.style.top    = vv.offsetTop + 'px';
  overlay.style.height = vv.height + 'px';
  overlay.style.bottom = 'auto';
  const focused = overlay.querySelector('input:focus, select:focus, textarea:focus');
  if (focused) focused.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function resetOverlay() {
  const overlay = document.getElementById('modal-overlay');
  overlay.style.top    = '';
  overlay.style.height = '';
  overlay.style.bottom = '';
}

if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', adjustOverlayForKeyboard);
  window.visualViewport.addEventListener('scroll', adjustOverlayForKeyboard);
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
document.getElementById('modal-overlay').addEventListener('focusin', e => {
  if (e.target.matches('input, select, textarea')) setTimeout(adjustOverlayForKeyboard, 300);
});

// ── 초기화 ──────────────────────────────────────────
document.getElementById('today-display').textContent =
  new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' });

async function init() {
  updateMonthDisplay();
  renderFloor();
  renderStats();
  try {
    const res = await fetch('/data', { credentials: 'same-origin' });
    if (res.status === 401) { window.location.href = '/login'; return; }
    if (!res.ok) throw new Error('서버 오류 ' + res.status);
    _DATA       = await res.json();
    _dataLoaded = true;
  } catch(e) {
    _dataLoaded = false;
    const banner = document.createElement('div');
    banner.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#c62828;color:#fff;text-align:center;padding:12px;font-size:15px;z-index:9999;';
    banner.textContent = '데이터 로드 실패 — 탭을 새로고침 해주세요.';
    document.body.appendChild(banner);
  }
  renderFloor();
  renderStats();
}

init();
