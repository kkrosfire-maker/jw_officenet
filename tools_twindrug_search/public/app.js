// 대체약 찾기 — data.json 을 한 번 받아 브라우저 안에서 검색한다.
// items: [제품코드, 제품명, 업체명, 주성분코드(동일제형), 상한금액, 단위, 규격, flags, 비고]
// flags: 1=생동인정, 2=생동대조약, 4=일반의약품

const $ = (s) => document.querySelector(s);
const qEl = $("#q"), resultsEl = $("#results"), detailEl = $("#detail");
const MAX_RESULTS = 80;
const EXAMPLES = ["리피토", "아토르바스타틴", "노바스크", "ㄴㅂㅅㅋ", "글리아티린", "종근당"];

let DB = null;          // 원본
let byCode = new Map(); // 제품코드 -> item
let byGroup = new Map();// 주성분코드 -> [item]
let index = [];         // [item, 검색문자열, 초성문자열, 앞이름]

// ---------- 글자 다루기 ----------
const CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
const norm = (s) => s.toLowerCase().replace(/[\s()\[\]_.,·\-\/]/g, "");
function chosung(s) {
  let out = "";
  for (const ch of s) {
    const c = ch.charCodeAt(0) - 0xac00;
    out += c >= 0 && c < 11172 ? CHO[Math.floor(c / 588)] : ch;
  }
  return norm(out);
}
const isChosungOnly = (s) => /^[ㄱ-ㅎ]+$/.test(s);
// 초성만 칠 때 입력기가 ㅂ+ㅅ → ㅄ 처럼 겹받침으로 합쳐 버린다. 초성에는 겹받침이 없으므로 두 글자로 되돌린다.
// (ㄲ ㄸ ㅃ ㅆ ㅉ 같은 쌍자음은 일부러 친 것이므로 그대로 둔다)
const SPLIT_JAMO = { "ㄳ": "ㄱㅅ", "ㄵ": "ㄴㅈ", "ㄶ": "ㄴㅎ", "ㄺ": "ㄹㄱ", "ㄻ": "ㄹㅁ", "ㄼ": "ㄹㅂ",
  "ㄽ": "ㄹㅅ", "ㄾ": "ㄹㅌ", "ㄿ": "ㄹㅍ", "ㅀ": "ㄹㅎ", "ㅄ": "ㅂㅅ" };
const splitCompoundJamo = (s) => s.replace(/[ㄳㄵㄶㄺㄻㄼㄽㄾㄿㅀㅄ]/g, (c) => SPLIT_JAMO[c]);
const mainName = (n) => n.split("_(")[0];
const subName = (n) => (n.includes("_(") ? n.slice(n.indexOf("_(") + 1) : "");
const won = (p) => (p == null ? "가격 없음" : p.toLocaleString("ko-KR") + "원");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ---------- 불러오기 ----------
fetch("data.json")
  .then((r) => r.json())
  .then((data) => {
    DB = data;
    for (const it of data.items) {
      byCode.set(it[0], it);
      if (!byGroup.has(it[3])) byGroup.set(it[3], []);
      byGroup.get(it[3]).push(it);
      const ing = data.groups[it[3]]?.[0] || "";
      index.push([it, norm(it[1] + ing + it[2]), chosung(mainName(it[1])), norm(mainName(it[1]))]);
    }
    for (const list of byGroup.values()) list.sort(byPrice);
    $("#basis").textContent = `${data.basis} 기준 · 약 ${data.items.length.toLocaleString()}개`;
    route();
  })
  .catch(() => {
    resultsEl.innerHTML = `<div class="msg"><b>자료를 불러오지 못했습니다.</b> 인터넷 연결을 확인하고 새로고침해 주세요.</div>`;
  });

function byPrice(a, b) {
  if (a[4] == null) return 1;
  if (b[4] == null) return -1;
  return a[4] - b[4] || a[1].localeCompare(b[1], "ko");
}

// ---------- 검색 ----------
function search(q) {
  const words = q.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const tests = words.map((w) => (isChosungOnly(w) ? [true, splitCompoundJamo(w)] : [false, norm(w)]));
  const hits = [];
  for (const row of index) {
    let score = 0, ok = true;
    for (const [cho, w] of tests) {
      if (cho) {
        const i = row[2].indexOf(w);
        if (i < 0) { ok = false; break; }
        score += i === 0 ? 0 : 1;
      } else {
        if (row[3].startsWith(w)) score += 0;
        else if (row[3].includes(w)) score += 1;
        else if (row[1].includes(w)) score += 2;
        else { ok = false; break; }
      }
    }
    if (ok) hits.push([score, row[0]]);
  }
  hits.sort((a, b) => a[0] - b[0] || a[1][1].length - b[1][1].length || a[1][1].localeCompare(b[1][1], "ko"));
  return hits.map((h) => h[1]);
}

function tagsHtml(it) {
  const f = it[7], t = [];
  if (f & 2) t.push(`<span class="tag ref">대조약</span>`);
  if (f & 1) t.push(`<span class="tag be">생동인정</span>`);
  if (f & 4) t.push(`<span class="tag otc">일반약</span>`);
  const note = it[8].trim();
  if (note) t.push(`<span class="tag${/정지/.test(note) ? " stop" : ""}">${esc(note)}</span>`);
  return t.length ? `<span class="tags">${t.join("")}</span>` : "";
}

function renderResults() {
  detailEl.hidden = true;
  resultsEl.hidden = false;
  if (!DB) return;
  const q = qEl.value;
  if (!q.trim()) {
    resultsEl.innerHTML = `<div class="msg">
      <b>약 이름을 입력하면 같은 성분·함량·제형의 대체 가능한 약이 가격순으로 나옵니다.</b><br>
      예시를 눌러 보세요:<div class="legend" style="margin-top:8px">
      ${EXAMPLES.map((e) => `<button class="btn" style="height:40px" data-ex="${esc(e)}">${esc(e)}</button>`).join("")}</div></div>`;
    return;
  }
  const hits = search(q);
  if (!hits.length) {
    resultsEl.innerHTML = `<div class="msg"><b>"${esc(q)}" 에 맞는 약이 없습니다.</b><br>
      글자를 줄이거나 성분명(영문)·제약사 이름으로 찾아보세요. 비급여 약은 목록에 없습니다.</div>`;
    return;
  }
  const shown = hits.slice(0, MAX_RESULTS);
  resultsEl.innerHTML = `<p class="count">${hits.length.toLocaleString()}개 찾음${hits.length > MAX_RESULTS ? ` · 앞의 ${MAX_RESULTS}개만 보여 줍니다. 더 자세히 입력해 보세요` : ""} · 눌러서 대체약 보기</p>
    <ul class="list">${shown.map((it) => {
      const n = byGroup.get(it[3]).length - 1;
      return `<li><button class="row" data-code="${it[0]}">
        <span class="dot" style="background:${n ? "#1E88E5" : "#9E9E9E"}" title="대체 가능한 약 수">${n}</span>
        <span class="body"><span class="name">${esc(mainName(it[1]))}</span>${tagsHtml(it)}
          <span class="sub">${esc(subName(it[1]))} · ${esc(it[2])} · 대체약 ${n}개</span></span>
        <span class="price">${won(it[4])}<small class="sub">/${esc(it[5])}</small></span>
      </button></li>`;
    }).join("")}</ul>`;
}

// ---------- 상세 ----------
function rowHtml(it, me, rank, cheapest) {
  let diff = "";
  if (me && it !== me && it[4] != null && me[4] != null) {
    const d = it[4] - me[4];
    diff = d < 0 ? `<small class="cheap">${d.toLocaleString()}원</small>`
         : d > 0 ? `<small class="dear">+${d.toLocaleString()}원</small>`
         : `<small class="sub">같음</small>`;
  } else if (it === me) diff = `<small class="sub">지금 약</small>`;
  const color = it === me ? "#1E88E5" : it[4] != null && it[4] === cheapest ? "#2E7D32" : "#5E9282";
  return `<li><button class="row${it === me ? " me" : ""}" data-code="${it[0]}">
    <span class="dot" style="background:${color}">${rank}</span>
    <span class="body"><span class="name">${esc(mainName(it[1]))}</span>${tagsHtml(it)}
      <span class="sub">${esc(it[2])}${subName(it[1]) ? " · " + esc(subName(it[1])) : ""}</span></span>
    <span class="price">${won(it[4])}${diff}</span>
  </button></li>`;
}

function listHtml(items, me) {
  const cheapest = items.find((i) => i[4] != null)?.[4];
  return `<ul class="list">${items.map((it, i) => rowHtml(it, me, i + 1, cheapest)).join("")}</ul>`;
}

function renderDetail(code) {
  const me = byCode.get(code);
  if (!me) return renderResults();
  resultsEl.hidden = true;
  detailEl.hidden = false;
  const [ing, routeName] = DB.groups[me[3]] || ["", ""];
  const same = byGroup.get(me[3]);
  const others = same.length - 1;
  const cheaper = same.filter((i) => i[4] != null && me[4] != null && i[4] < me[4]).length;

  // 같은 성분 + 같은 투여·제형인데 함량·규격만 다른 묶음
  const key = me[3].slice(0, 4) + me[3].slice(-3);
  const near = [...byGroup.keys()]
    .filter((g) => g !== me[3] && g.slice(0, 4) + g.slice(-3) === key)
    .sort();

  detailEl.innerHTML = `
    <button class="btn back" id="back">◀ 검색 결과로</button>
    <div class="card">
      <div class="name">${esc(mainName(me[1]))}${tagsHtml(me)}</div>
      <div class="sub">${esc(subName(me[1]))}</div>
      <div class="facts">
        <div><span>성분</span>${esc(ing)}</div>
        <div><span>제약사</span>${esc(me[2])}</div>
        <div><span>보험 상한가</span><b>${won(me[4])}</b> / ${esc(me[5])}</div>
        <div><span>투여</span>${esc(routeName)}</div>
        <div><span>제품코드</span>${esc(me[0])}</div>
      </div>
    </div>

    <h2 class="group-title"><span class="num n2">2</span>대체 가능한 약 ${others}개</h2>
    <p class="group-desc">${others
      ? `성분·함량·제형이 같은 약입니다. 싼 순서이고, 지금 약보다 싼 약이 <b class="cheap">${cheaper}개</b> 있습니다.`
      : "같은 성분·함량·제형의 다른 급여 약이 없습니다."}</p>
    <div class="legend"><span><span class="tag ref">대조약</span> 생동성 기준약(오리지널 격)</span>
      <span><span class="tag be">생동인정</span> 생동성 인정</span>
      <span>숫자 = 가격 순위, <b class="cheap">초록</b> = 가장 쌈</span></div>
    ${listHtml(same, me)}

    ${near.length ? `<details>
      <summary><h2 class="group-title"><span class="num n3">3</span>같은 성분 · 함량이나 규격이 다른 약 (${near.reduce((s, g) => s + byGroup.get(g).length, 0)}개)</h2></summary>
      <p class="group-desc">대체조제 대상은 아니고 참고용입니다. 함량이 다른 약과 포장 규격만 다른 약(시럽 등)이 함께 있습니다.</p>
      ${near.map((g) => `<div class="subhead">${esc(DB.groups[g][0])} <small>${byGroup.get(g).length}개</small></div>${listHtml(byGroup.get(g), null)}`).join("")}
    </details>` : ""}`;
  window.scrollTo(0, 0);
}

// ---------- 화면 전환 (뒤로가기 지원) ----------
function route() {
  const m = location.hash.match(/^#c=(\w+)/);
  if (m && DB) renderDetail(m[1]);
  else renderResults();
}
window.addEventListener("hashchange", route);

let timer;
qEl.addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    if (location.hash) history.replaceState(null, "", location.pathname);
    renderResults();
  }, 120);
});
$("#clear").addEventListener("click", () => {
  qEl.value = "";
  if (location.hash) history.replaceState(null, "", location.pathname);
  renderResults();
  qEl.focus();
});
document.addEventListener("click", (e) => {
  const ex = e.target.closest("[data-ex]");
  if (ex) { qEl.value = ex.dataset.ex; renderResults(); return; }
  if (e.target.closest("#back")) {
    // 검색어는 그대로 두고 목록으로 (폰의 뒤로가기 버튼도 hashchange 로 같은 동작)
    history.replaceState(null, "", location.pathname);
    renderResults();
    return;
  }
  const row = e.target.closest("[data-code]");
  if (row) location.hash = "c=" + row.dataset.code;
});
