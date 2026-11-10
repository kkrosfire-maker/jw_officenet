/* 서버에서 게시판 페이지를 미리 그리는 공용 코드 (검색엔진·AI 크롤러·메신저 미리보기용)
 *   /news/:id   -> api/article.js   기사 상세
 *   /news       -> api/list.js      기사 목록
 *   /sitemap.xml-> api/sitemap.js   사이트맵(공개 글 자동 반영)
 * 글은 Supabase 에서 '공개된 글'만 읽는다(공개용 키, 읽기 전용). 응답은 CDN 이 5분간 보관한다.
 * 도메인을 연결하면 SITE 만 바꾸면 된다(환경변수 SITE_URL 로도 지정 가능).
 */
const SITE = (process.env.SITE_URL || 'https://jungwon-unius-homepage.vercel.app').replace(/\/$/, '');
const SB_URL = 'https://mfbclctzkjdsrrsivlmg.supabase.co';
const SB_KEY = 'sb_publishable_CKV18Z4BTPr0Z5huTM3d6A_xr07oeBc'; // 공개용 키(읽기 전용)
const DEF_THUMB = 'assets/news_thumbnail_default.webp';
const COLS = 'id,date,title,summary,thumb,source,category';

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const jsonLd = (o) => JSON.stringify(o).replace(/</g, '\\u003c');
const abs = (u) => (/^https?:\/\//i.test(u || '') ? u : SITE + '/' + String(u || DEF_THUMB).replace(/^\//, ''));
// 화면에 쓰는 이미지 주소: 상대 경로는 /news/2 같은 주소에서 깨지므로 사이트 루트(/) 기준으로 바꾼다
const src = (u) => (/^https?:\/\//i.test(u || '') ? u : '/' + String(u || DEF_THUMB).replace(/^\//, ''));
const fix = (p) => { if (p && !p.thumb) p.thumb = DEF_THUMB; return p; };
const dot = (d) => String(d || '').replace(/-/g, '.');
const clip = (s, n) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, n);

async function sb(path, extra) {
  const r = await fetch(SB_URL + '/rest/v1/posts?' + path, {
    headers: Object.assign({ apikey: SB_KEY, Authorization: 'Bearer ' + SB_KEY }, extra || {}),
    signal: AbortSignal.timeout(8000),
  });
  if (!r.ok) throw new Error('supabase ' + r.status);
  return r;
}

async function getPost(id) {
  const rows = await (await sb('select=*&published=eq.true&id=eq.' + encodeURIComponent(id))).json();
  const p = fix(rows[0]);
  if (!p) return null;
  const d = encodeURIComponent(p.date);
  const older = `select=${COLS}&published=eq.true&or=(date.lt.${d},and(date.eq.${d},id.lt.${p.id}))&order=date.desc,id.desc&limit=1`;
  const newer = `select=${COLS}&published=eq.true&or=(date.gt.${d},and(date.eq.${d},id.gt.${p.id}))&order=date.asc,id.asc&limit=1`;
  const [n, o] = await Promise.all([sb(newer).then((r) => r.json()), sb(older).then((r) => r.json())]);
  return { post: p, prev: fix(n[0] || null), next: fix(o[0] || null) };
}

async function listPosts(page, per) {
  const r = await sb(`select=${COLS}&published=eq.true&order=date.desc,id.desc&limit=${per}&offset=${(page - 1) * per}`, { Prefer: 'count=exact' });
  const total = parseInt((r.headers.get('content-range') || '').split('/')[1], 10) || 0;
  return { items: (await r.json()).map(fix), total };
}

async function allPostIds() {
  return (await (await sb('select=id,date&published=eq.true&order=date.desc,id.desc&limit=5000')).json());
}

/* 화면 뼈대: 홈·게시판과 같은 머리말/메뉴/바닥글. 링크는 모두 사이트 루트 기준이다. */
function layout({ title, desc, canonical, ogType, ogImage, robots, head, body }) {
  return `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}">
${robots ? `<meta name="robots" content="${robots}">\n` : ''}${canonical ? `<link rel="canonical" href="${esc(canonical)}">\n` : ''}<meta property="og:type" content="${ogType || 'website'}">
<meta property="og:locale" content="ko_KR">
<meta property="og:site_name" content="정원유니어스">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
${canonical ? `<meta property="og:url" content="${esc(canonical)}">\n` : ''}<meta property="og:image" content="${esc(ogImage || SITE + '/assets/09_social_share_1200x630.jpg')}">
<meta name="twitter:card" content="summary_large_image">
${head || ''}<link rel="icon" href="/assets/00_favicon_64.png">
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.css" rel="stylesheet">
<link rel="stylesheet" href="/assets/board.css">
</head>
<body>
<header><div class="in">
  <a href="/" class="logo"><img src="/assets/logo_jw.webp" alt="정원유니어스 로고"><span>정원유니어스<small>JUNGWON UNIUS</small></span></a>
  <div style="display:flex;align-items:center;gap:30px">
  <nav class="tnav"><a href="/#services">SERVICE</a><a href="/#process">PROCESS</a><a href="/news.html" class="on">NEWS</a><a href="/#faq">FAQ</a><a href="/#contact">CONTACT</a></nav>
  <button class="burger" id="bg" aria-label="메뉴"><i></i><i></i></button>
  </div>
</div></header>

<div class="menu-panel" id="mp">
  <div class="col"><h6>MENU</h6>
    <a href="/#about"><i>01</i>회사소개</a><a href="/#services"><i>02</i>파트너 서비스</a><a href="/#process"><i>03</i>정산 프로세스</a><a href="/news.html"><i>04</i>CSO 소식</a><a href="/#faq"><i>05</i>자주 묻는 질문</a><a href="/#contact"><i>06</i>상담 신청</a></div>
  <div class="side"><b>THE BEST MEDICAL PARTNER</b>경기 김포시 풍무로146번길 26<br>프라미스빌딩 4층 A01호<br>010-6498-0999<br>jungwonunius@naver.com</div>
</div>

${body}

<footer><div class="wrap">
  <div class="row">
    <div><a href="/" class="logo"><img src="/assets/logo_jw.webp" alt="" style="width:36px;height:36px;border-radius:9px"><span>정원유니어스(주)<small>JUNGWON UNIUS</small></span></a>
    <p>경기 김포시 풍무로146번길 26 프라미스빌딩 4층 A01호<br>010-6498-0999 · jungwonunius@naver.com</p></div>
    <div><p><a href="https://jwunius.imweb.me/?mode=policy">이용약관</a> &nbsp;|&nbsp; <a href="https://jwunius.imweb.me/?mode=privacy">개인정보처리방침</a> &nbsp;|&nbsp; <a href="/admin.html" rel="nofollow">관리자</a></p></div>
  </div>
  <div class="copy">© 2026 JUNGWON UNIUS. ALL RIGHTS RESERVED.</div>
</div></footer>
<script>
document.getElementById('bg').onclick=function(){document.body.classList.toggle('menu')};
document.querySelectorAll('#mp a').forEach(function(a){a.onclick=function(){document.body.classList.remove('menu')}});
document.querySelector('header .logo').addEventListener('click',function(){document.body.classList.remove('menu')});
</script>
</body>
</html>`;
}

const send = (res, status, html, cache) => {
  res.statusCode = status;
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.setHeader('Cache-Control', cache || 'public, s-maxage=300, stale-while-revalidate=86400');
  res.end(html);
};

module.exports = { SITE, esc, jsonLd, abs, src, dot, clip, getPost, listPosts, allPostIds, layout, send };
