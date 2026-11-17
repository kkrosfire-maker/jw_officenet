/* GET /api/candidates?min=60  -> 관리자 화면의 '기사 후보' 목록 (관리자 전용)
 * 참고 사이트 API(medicalnews-tau)는 브라우저에서 직접 부를 수 없으므로 서버가 대신 가져온다.
 * 로그인 확인 방식은 og-image.js 와 같다(Supabase is_admin()).
 */
const SB_URL = 'https://mfbclctzkjdsrrsivlmg.supabase.co';
const SB_KEY = 'sb_publishable_CKV18Z4BTPr0Z5huTM3d6A_xr07oeBc'; // 공개용 키
const SOURCE_API = 'https://medicalnews-tau.vercel.app/api/news';

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
  const send = (code, obj) => { res.statusCode = code; res.setHeader('Content-Type', 'application/json; charset=utf-8'); res.end(JSON.stringify(obj)); };
  if (req.method === 'OPTIONS') { res.statusCode = 204; return res.end(); }

  const token = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  if (!token || !(await isAdmin(token))) return send(401, { error: '관리자 로그인이 필요합니다.' });

  const min = Math.min(100, Math.max(0, parseInt(new URL(req.url, 'http://x').searchParams.get('min'), 10) || 60));
  try {
    const qs = new URLSearchParams({ view: 'inbox', minScore: String(min), category: 'ALL', search: '', page: '1' });
    const r = await fetch(SOURCE_API + '?' + qs, { signal: AbortSignal.timeout(12000) });
    const d = await r.json();
    if (!r.ok || !d || !d.success) return send(502, { error: '후보 사이트가 응답하지 않습니다.' });
    const news = (d.news || [])
      .filter((n) => n.title && n.link && Number(n.score) >= min)
      .map((n) => ({ title: String(n.title), link: String(n.link), source: n.source || '', summary: String(n.summary || '').slice(0, 500),
        category: n.category || '', score: Number(n.score), pub_date: n.pub_date || '' }))
      .sort((a, b) => b.score - a.score || String(b.pub_date).localeCompare(String(a.pub_date)));
    send(200, { news });
  } catch (e) {
    send(502, { error: '후보를 가져오지 못했습니다.' });
  }
};
