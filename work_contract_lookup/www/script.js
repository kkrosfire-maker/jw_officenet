// ── DOM 연결 (계산 로직은 calc.js) ─────────────────────
function showError(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.style.display = msg ? 'block' : 'none';
}

function calculate() {
  showError('');
  const roomName = normalizeRoomName(document.getElementById('room-name').value);
  const startVal = document.getElementById('start-date').value;

  if (!roomName) { showError('방 이름을 입력해주세요.'); return; }
  const baseRent = BASE_RENT[roomName];
  if (baseRent === undefined) { showError('등록되지 않은 호실입니다: ' + roomName); return; }
  if (!startVal) { showError('입주개시일을 입력해주세요.'); return; }
  const endVal = document.getElementById('end-date').value;
  if (!endVal) { showError('입주만료일을 입력해주세요.'); return; }

  const info = computeContractInfo(baseRent, startVal, endVal);

  document.getElementById('result-room').textContent = roomName;
  document.getElementById('out-months').textContent   = info.months + '개월';
  document.getElementById('out-start').textContent    = fmtDateKorean(startVal);
  document.getElementById('out-end').textContent       = fmtDateKorean(endVal);

  document.getElementById('out-standard-ex').textContent  = fmtWon(info.standardExVat) + '원';
  document.getElementById('out-standard-inc').textContent = fmtWon(info.standardIncVat) + '원';
  document.getElementById('out-discount-ex').textContent  = fmtWon(info.discountExVat) + '원';
  document.getElementById('out-discount-inc').textContent = fmtWon(info.discountIncVat) + '원';
  document.getElementById('out-deposit').textContent      = fmtWon(info.deposit) + '원';
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('calc-btn').addEventListener('click', calculate);
  document.getElementById('today-btn').addEventListener('click', () => {
    document.getElementById('start-date').value = fmtDateLocal(new Date());
  });
  document.getElementById('months-calc-btn').addEventListener('click', () => {
    showError('');
    const startVal = document.getElementById('start-date').value;
    const monthsInput = parseInt(document.getElementById('months-input').value, 10);
    if (!startVal) { showError('입주개시일을 입력해주세요.'); return; }
    if (!monthsInput || monthsInput <= 0) { showError('개월수를 입력해주세요.'); return; }
    document.getElementById('end-date').value = addMonthsToDate(startVal, monthsInput);
  });
  document.getElementById('room-name').addEventListener('keydown', e => { if (e.key === 'Enter') calculate(); });
});
