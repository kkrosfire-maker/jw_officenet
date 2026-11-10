/* 관리자 로그인 (Supabase Auth, 이메일+비밀번호). 방문자 가입은 Supabase 쪽에서 막혀 있다.
 *   NewsAuth.hasSession()            -> 로그인 정보가 브라우저에 있는지(동기, 가벼움)
 *   NewsAuth.signIn(email, pw)       -> Promise
 *   NewsAuth.signOut()
 *   NewsAuth.isAdmin()               -> Promise<boolean>  (DB 의 is_admin() 으로 서버가 판정)
 *   NewsAuth.rest(method, path, body, headers) -> Promise<json|null>   (로그인 토큰으로 REST 호출)
 *   NewsAuth.upload(name, blob) / NewsAuth.removeFile(url)             (썸네일 Storage)
 */
(function () {
  var cfg = window.NEWS_BACKEND || {}, KEY = 'news_auth_v1';
  var base = (cfg.url || '').replace(/\/$/, '');
  var read = function () { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } };
  var write = function (s) { try { s ? localStorage.setItem(KEY, JSON.stringify(s)) : localStorage.removeItem(KEY); } catch (e) {} };
  function pack(j) { return { access_token: j.access_token, refresh_token: j.refresh_token, expires_at: Math.floor(Date.now() / 1000) + (j.expires_in || 3600), email: (j.user || {}).email || '' }; }
  function authCall(grant, body) {
    return fetch(base + '/auth/v1/token?grant_type=' + grant, { method: 'POST', headers: { apikey: cfg.anonKey, 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(r.status === 400 ? '이메일 또는 비밀번호가 올바르지 않습니다.' : (j.msg || j.error_description || '로그인에 실패했습니다.')); return j; }); });
  }
  function token() {
    var s = read(); if (!s) return Promise.reject(new Error('로그인이 필요합니다.'));
    if (s.expires_at - 60 > Date.now() / 1000) return Promise.resolve(s.access_token);
    return authCall('refresh_token', { refresh_token: s.refresh_token }).then(function (j) { var n = pack(j); write(n); return n.access_token; })
      .catch(function (e) { write(null); throw new Error('로그인이 만료되었습니다. 다시 로그인해 주세요.'); });
  }
  function hdr(t, extra) { var h = { apikey: cfg.anonKey, Authorization: 'Bearer ' + t }; for (var k in (extra || {})) h[k] = extra[k]; return h; }
  window.NewsAuth = {
    hasSession: function () { return !!read(); },
    email: function () { return (read() || {}).email || ''; },
    signIn: function (email, pw) { return authCall('password', { email: email, password: pw }).then(function (j) { write(pack(j)); }); },
    signOut: function () { write(null); },
    isAdmin: function () {
      return token().then(function (t) { return fetch(base + '/rest/v1/rpc/is_admin', { method: 'POST', headers: hdr(t, { 'Content-Type': 'application/json' }), body: '{}' }); })
        .then(function (r) { return r.ok ? r.json() : false; }).then(function (v) { return v === true; }).catch(function () { return false; });
    },
    rest: function (method, path, body, extra) {
      return token().then(function (t) {
        return fetch(base + '/rest/v1/' + path, { method: method, headers: hdr(t, Object.assign({ 'Content-Type': 'application/json', Prefer: 'return=representation' }, extra || {})), body: body ? JSON.stringify(body) : undefined });
      }).then(function (r) {
        if (r.status === 204) return null;
        return r.json().catch(function () { return null; }).then(function (j) {
          if (!r.ok) throw new Error(r.status === 409 ? '이미 같은 원문 링크의 글이 있습니다.' : (r.status === 401 || r.status === 403 ? '권한이 없습니다. 관리자 계정으로 로그인해 주세요.' : ((j && j.message) || '요청에 실패했습니다.')));
          return j;
        });
      });
    },
    upload: function (name, blob) {
      return token().then(function (t) { return fetch(base + '/storage/v1/object/news-thumbs/' + name, { method: 'POST', headers: hdr(t, { 'Content-Type': blob.type || 'image/jpeg', 'x-upsert': 'true' }), body: blob }); })
        .then(function (r) { if (!r.ok) throw new Error('썸네일 업로드에 실패했습니다.'); return base + '/storage/v1/object/public/news-thumbs/' + name; });
    },
    removeFile: function (url) {
      var p = '/storage/v1/object/public/news-thumbs/', i = (url || '').indexOf(p); if (i < 0) return Promise.resolve();
      var name = url.slice(i + p.length);
      return token().then(function (t) { return fetch(base + '/storage/v1/object/news-thumbs/' + name, { method: 'DELETE', headers: hdr(t) }); }).catch(function () {});
    }
  };
})();
