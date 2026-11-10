/* /news  기사 목록을 서버에서 미리 그려 응답한다. 페이지는 /news?page=N 링크로 이동한다. */
const { SITE, esc, abs, src, dot, clip, listPosts, layout, send } = require('./_lib');

const PER = 12;

module.exports = async (req, res) => {
  const q = new URL(req.url, 'http://x').searchParams;
  let page = Math.max(parseInt(q.get('page'), 10) || 1, 1);
  let r;
  try {
    r = await listPosts(page, PER);
    const pages = Math.max(1, Math.ceil(r.total / PER));
    if (page > pages) { page = pages; r = await listPosts(page, PER); }
  } catch (e) {
    return send(res, 503, layout({ title: '잠시 후 다시 시도해 주세요 | 정원유니어스', desc: '게시글을 불러오지 못했습니다.', robots: 'noindex',
      body: '<main class="view"><div class="wrap"><h1>게시글을 불러오지 못했습니다.</h1><p>잠시 후 다시 시도해 주세요.</p></div></main>' }), 'no-store');
  }
  const pages = Math.max(1, Math.ceil(r.total / PER));
  const href = (n) => (n === 1 ? '/news' : '/news?page=' + n);
  const canonical = SITE + href(page);

  const card = (p) => `<a class="bc" href="/news/${p.id}"><div class="th"><img loading="lazy" decoding="async" src="${esc(src(p.thumb))}" alt=""></div><div class="tx"><time>${esc(dot(p.date))}</time><h3>${esc(p.title)}</h3><p>${esc(p.summary)}</p><span class="go">자세히 보기 <i>›</i></span></div></a>`;
  const nums = () => {
    if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
    const a = [...new Set([1, pages, page - 1, page, page + 1])].filter((n) => n >= 1 && n <= pages).sort((x, y) => x - y);
    const out = [];
    a.forEach((n, i) => { if (i && n - a[i - 1] > 1) out.push('…'); out.push(n); });
    return out;
  };
  const pager = pages <= 1 ? '' :
    (page > 1 ? `<a href="${href(page - 1)}" aria-label="이전">‹</a>` : '') +
    nums().map((n) => (n === '…' ? '<span>…</span>' : `<a class="${n === page ? 'on' : ''}" href="${href(n)}">${n}</a>`)).join('') +
    (page < pages ? `<a href="${href(page + 1)}" aria-label="다음">›</a>` : '');

  const html = layout({
    title: page > 1 ? `CSO 업계 소식 ${page}페이지 | 정원유니어스` : 'CSO 업계 소식 | 정원유니어스',
    desc: '제약 CSO 시장의 최신 동향과 수수료·품목·정책 소식을 모아 전합니다. 정원유니어스의 CSO 업계 소식 게시판.',
    canonical,
    head: `<script type="application/ld+json">${JSON.stringify({ '@context': 'https://schema.org', '@type': 'CollectionPage', name: 'CSO 업계 소식', url: canonical, inLanguage: 'ko-KR',
      hasPart: r.items.map((p) => ({ '@type': 'NewsArticle', headline: p.title.slice(0, 110), url: `${SITE}/news/${p.id}`, datePublished: p.date })) }).replace(/</g, '\\u003c')}</script>\n`,
    body: `<section class="phead">
  <div class="ghost">NEWS</div>
  <div class="wrap">
    <div class="eyebrow">CSO news</div>
    <h1>CSO 업계 소식</h1>
    <p>제약 CSO 시장의 최신 동향과 정원유니어스의 소식을 전해드립니다.</p>
    <div class="cnt">전체 게시글 <b>${r.total}</b>개</div>
  </div>
</section>
<section class="board" id="list"><div class="wrap">
  <div class="grid">${r.items.length ? r.items.map(card).join('') : '<div class="empty">등록된 게시글이 없습니다.</div>'}</div>
  <div class="pager">${pager}</div>
</div></section>`,
  });
  send(res, 200, html);
};
