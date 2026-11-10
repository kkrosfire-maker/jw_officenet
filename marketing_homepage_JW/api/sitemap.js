/* /sitemap.xml  공개된 글이 자동으로 들어가는 사이트맵 (vercel.json 의 rewrites 가 연결) */
const { SITE, esc, allPostIds } = require('./_lib');

const entry = (loc, lastmod, freq, prio) =>
  `  <url>\n    <loc>${esc(loc)}</loc>\n    <lastmod>${lastmod}</lastmod>\n    <changefreq>${freq}</changefreq>\n    <priority>${prio}</priority>\n  </url>`;

module.exports = async (req, res) => {
  let posts;
  try { posts = await allPostIds(); } catch (e) {
    res.statusCode = 503; res.setHeader('Cache-Control', 'no-store'); return res.end('temporarily unavailable');
  }
  const kst = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
  const newest = posts.length ? posts[0].date : kst;
  const rows = [entry(`${SITE}/`, kst, 'weekly', '1.0'), entry(`${SITE}/news`, newest, 'daily', '0.8')]
    .concat(posts.map((p) => entry(`${SITE}/news/${p.id}`, p.date, 'monthly', '0.6')));
  res.statusCode = 200;
  res.setHeader('Content-Type', 'application/xml; charset=utf-8');
  res.setHeader('Cache-Control', 'public, s-maxage=300, stale-while-revalidate=86400');
  res.end(`<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${rows.join('\n')}\n</urlset>\n`);
};
