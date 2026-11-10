/* /news/:id  기사 상세를 서버에서 미리 그려 응답한다 (vercel.json 의 rewrites 가 연결) */
const { SITE, esc, jsonLd, abs, src, dot, clip, getPost, layout, send } = require('./_lib');

const NOCACHE = 'no-store';

module.exports = async (req, res) => {
  const id = parseInt(new URL(req.url, 'http://x').searchParams.get('id'), 10);
  const missing = () => send(res, 404, layout({
    title: '게시글을 찾을 수 없습니다 | 정원유니어스', desc: '요청하신 게시글을 찾을 수 없습니다.', robots: 'noindex',
    body: '<main class="view"><div class="wrap"><div class="crumb"><a href="/news.html">CSO 업계 소식</a></div><h1>게시글을 찾을 수 없습니다.</h1><div class="tolist"><a href="/news.html">목록으로</a></div></div></main>',
  }), 'public, s-maxage=60');
  if (!id) return missing();

  let r;
  try { r = await getPost(id); } catch (e) {
    return send(res, 503, layout({ title: '잠시 후 다시 시도해 주세요 | 정원유니어스', desc: '게시글을 불러오지 못했습니다.', robots: 'noindex',
      body: '<main class="view"><div class="wrap"><h1>게시글을 불러오지 못했습니다.</h1><p>잠시 후 다시 시도해 주세요.</p><div class="tolist"><a href="/news.html">목록으로</a></div></div></main>' }), NOCACHE);
  }
  if (!r) return missing();

  const { post: p, prev, next } = r;
  const url = `${SITE}/news/${p.id}`;
  const desc = clip(p.summary || p.title, 160);
  const img = abs(p.thumb);

  // 요약 박스와 같은 문장이 본문에 또 나오지 않게(자동 등록 글은 본문이 '요약 + 출처'로 저장된 경우가 있음)
  let body = String(p.body || '').trim();
  const sm = String(p.summary || '').trim();
  if (sm && body.startsWith(sm)) body = body.slice(sm.length).trim();
  if (p.source && body === '출처: ' + p.source) body = '';

  const org = { '@type': 'Organization', name: '정원유니어스(주)', url: SITE + '/' };
  const ld = {
    '@context': 'https://schema.org', '@type': 'NewsArticle', headline: p.title.slice(0, 110), inLanguage: 'ko-KR',
    datePublished: p.date, dateModified: p.date, mainEntityOfPage: { '@type': 'WebPage', '@id': url },
    image: [img], author: org, publisher: org,
  };
  if (p.summary) ld.description = p.summary;
  if (p.category) ld.articleSection = p.category;
  if (/^https?:\/\//i.test(p.link || '')) {
    ld.isBasedOn = { '@type': 'CreativeWork', url: p.link };
    if (p.source) ld.isBasedOn.publisher = { '@type': 'Organization', name: p.source };
  }

  const link = /^https?:\/\//i.test(p.link || '')
    ? `<a class="btn-orig" href="${esc(p.link)}" target="_blank" rel="noopener noreferrer">원문 보기 <i>›</i></a>` : '';
  const nav = (x, label, cls) => x
    ? `<a class="${cls}" href="/news/${x.id}"><small>${label}</small><b>${esc(x.title)}</b></a>` : '<a class="none"></a>';

  const html = layout({
    title: `${p.title} | 정원유니어스`, desc, canonical: url, ogType: 'article', ogImage: img,
    head: `<meta property="article:published_time" content="${esc(p.date)}">\n<script type="application/ld+json">${jsonLd(ld)}</script>\n`,
    body: `<main class="view"><div class="wrap">
  <div class="crumb"><a href="/news.html">CSO 업계 소식</a> › 상세</div>
  <div class="eyebrow">CSO news</div><h1>${esc(p.title)}</h1>
  <div class="meta">${esc(dot(p.date))} · ${esc(p.source || '정원유니어스')}</div>
  <div class="hero-img"><img src="${esc(src(p.thumb))}" alt="${esc(p.title)}"></div>
  ${p.summary ? `<div class="sum">${esc(p.summary)}</div>` : ''}
  ${body ? `<div class="body">${esc(body)}</div>` : ''}${link}
  <div class="pn">${nav(prev, '← 이전 글', 'l')}${nav(next, '다음 글 →', 'r')}</div>
  <div class="tolist"><a href="/news.html">목록으로</a></div>
</div></main>`,
  });
  send(res, 200, html);
};
