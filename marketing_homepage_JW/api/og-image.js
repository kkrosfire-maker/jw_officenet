/* GET /api/og-image?url=<원문 주소>  -> 원문 기사의 대표 이미지 파일을 돌려준다 (관리자 전용)
 * 로그인 토큰(Authorization: Bearer)을 Supabase 의 is_admin() 으로 확인한다. 쿠키를 쓰지 않으므로 CORS 는 열어 둔다
 * (로컬 PC 의 관리자 화면 127.0.0.1:8787 에서도 이 주소를 부를 수 있게).
 */
const { fetchArticleImage } = require('./_og');

const SB_URL = 'https://mfbclctzkjdsrrsivlmg.supabase.co';
const SB_KEY = 'sb_publishable_CKV18Z4BTPr0Z5huTM3d6A_xr07oeBc'; // 공개용 키

async function isAdmin(token) {
  try {
    const r = await fetch(SB_URL + '/rest/v1/rpc/is_admin', {
      method: 'POST', headers: { apikey: SB_KEY, Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' }, body: '{}',
      signal: AbortSignal.timeout(6000),
    });
    return r.ok && (await r.json()) === true;
  } catch (e) { return false; }
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Authorization');
  res.setHeader('Cache-Control', 'no-store');
  const fail = (code, msg) => { res.statusCode = code; res.setHeader('Content-Type', 'application/json; charset=utf-8'); res.end(JSON.stringify({ error: msg })); };
  if (req.method === 'OPTIONS') { res.statusCode = 204; return res.end(); }

  const token = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  if (!token || !(await isAdmin(token))) return fail(401, '관리자 로그인이 필요합니다.');

  const target = new URL(req.url, 'http://x').searchParams.get('url') || '';
  if (!/^https?:\/\//i.test(target)) return fail(400, '원문 링크가 올바르지 않습니다.');

  try {
    const img = await fetchArticleImage(target);
    res.statusCode = 200;
    res.setHeader('Content-Type', img.type);
    res.setHeader('Content-Length', img.buf.length);
    res.end(img.buf);
  } catch (e) {
    fail(e.notFound ? 404 : e.tooBig ? 413 : 502, e.message || '이미지를 가져오지 못했습니다.');
  }
};
