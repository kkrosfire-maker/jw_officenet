/* 원문 링크의 대표 이미지(og:image) 찾기·내려받기 - 관리자 화면의 '원문에서 이미지 가져오기'용
 * 서버가 대신 가져오므로 내부망 주소(SSRF)를 막는다: http/https 만, 사설·루프백·링크로컬 IP 거부,
 * 리다이렉트는 한 단계씩 다시 검사, 크기·시간 제한.
 */
const dns = require('dns').promises;
const net = require('net');

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';
const MAX_HTML = 2 * 1024 * 1024;
const MAX_IMG = 4 * 1024 * 1024; // Vercel 함수 응답 한도(4.5MB) 아래로

function privateIp(ip) {
  if (net.isIPv4(ip)) {
    const [a, b] = ip.split('.').map(Number);
    return a === 0 || a === 10 || a === 127 || (a === 100 && b >= 64 && b <= 127) || (a === 169 && b === 254) ||
      (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 192 && b === 0) || a >= 224;
  }
  const v = ip.toLowerCase();
  if (v === '::1' || v === '::' || v.startsWith('fe80') || v.startsWith('fc') || v.startsWith('fd')) return true;
  const m = v.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/);
  return m ? privateIp(m[1]) : false;
}

async function assertPublic(u) {
  if (!/^https?:$/.test(u.protocol)) throw new Error('http/https 주소만 가능합니다.');
  const host = u.hostname.replace(/^\[|\]$/g, '');
  const addrs = net.isIP(host) ? [{ address: host }] : await dns.lookup(host, { all: true });
  if (!addrs.length || addrs.some((a) => privateIp(a.address))) throw new Error('허용되지 않는 주소입니다.');
}

async function readCapped(res, max) {
  const chunks = []; let n = 0;
  for await (const c of res.body) {
    n += c.length;
    if (n > max) throw Object.assign(new Error('파일이 너무 큽니다.'), { tooBig: true });
    chunks.push(c);
  }
  return Buffer.concat(chunks);
}

async function get(url, accept, max) {
  let u = new URL(url);
  for (let hop = 0; hop < 5; hop++) {
    await assertPublic(u);
    const r = await fetch(u, { redirect: 'manual', headers: { 'User-Agent': UA, Accept: accept, 'Accept-Language': 'ko,en;q=0.8' }, signal: AbortSignal.timeout(9000) });
    if (r.status >= 300 && r.status < 400 && r.headers.get('location')) { u = new URL(r.headers.get('location'), u); continue; }
    if (!r.ok) throw new Error('원문 사이트가 응답하지 않습니다 (' + r.status + ').');
    return { res: r, url: u, buf: await readCapped(r, max) };
  }
  throw new Error('리다이렉트가 너무 많습니다.');
}

const decode = (s) => s.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;|&#x27;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>');

/* HTML 에서 대표 이미지 주소 후보를 우선순위대로 뽑는다 */
function findImages(html, base) {
  const out = [];
  const want = ['og:image:secure_url', 'og:image', 'twitter:image', 'twitter:image:src'];
  const metas = html.match(/<meta\b[^>]*>/gi) || [];
  const found = {};
  for (const m of metas) {
    const key = (m.match(/\b(?:property|name)\s*=\s*["']([^"']+)["']/i) || [])[1];
    const val = (m.match(/\bcontent\s*=\s*["']([^"']*)["']/i) || [])[1];
    if (key && val && want.includes(key.toLowerCase()) && !found[key.toLowerCase()]) found[key.toLowerCase()] = val;
  }
  for (const k of want) if (found[k]) out.push(found[k]);
  const link = (html.match(/<link\b[^>]*\brel\s*=\s*["']image_src["'][^>]*>/i) || [''])[0].match(/\bhref\s*=\s*["']([^"']+)["']/i);
  if (link) out.push(link[1]);
  return out.map((v) => { try { return new URL(decode(v.trim()), base).href; } catch (e) { return null; } }).filter(Boolean);
}

async function fetchArticleImage(pageUrl) {
  const page = await get(pageUrl, 'text/html,application/xhtml+xml', MAX_HTML);
  const cands = findImages(page.buf.toString('utf8'), page.url);
  if (!cands.length) throw Object.assign(new Error('원문 페이지에서 대표 이미지를 찾지 못했습니다.'), { notFound: true });
  let lastErr;
  for (const c of cands) {
    try {
      const img = await get(c, 'image/*,*/*;q=0.5', MAX_IMG);
      const type = (img.res.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
      if (/^image\/(jpeg|png|webp|gif)$/.test(type)) return { type, buf: img.buf, from: c };
      lastErr = new Error('이미지 형식이 아닙니다.');
    } catch (e) { lastErr = e; }
  }
  throw lastErr || new Error('이미지를 가져오지 못했습니다.');
}

module.exports = { fetchArticleImage, findImages, privateIp, assertPublic };
