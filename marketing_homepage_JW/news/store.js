/* 게시판 데이터 접근 계층. 화면(news.html, news_view.html, 홈 8번)은 이 파일의 함수만 사용한다.
 *   NewsStore.list({page, per}) -> Promise<{items, total}>   (목록용: body 제외, 최신순)
 *   NewsStore.latest(n)         -> Promise<items>
 *   NewsStore.get(id)           -> Promise<{post, prev, next} | null>
 * 백엔드는 news/config.js 의 NEWS_BACKEND.type 으로 선택: 'static' | 'supabase'
 * 글 필드: id, date(YYYY-MM-DD), title, summary, body, link, thumb, [source, category, score, published]
 */
(function () {
  var cfg = window.NEWS_BACKEND || { type: 'static' };
  var LIST_COLS = 'id,date,title,summary,thumb,source,category';
  var DEF_THUMB = 'assets/news_thumbnail_default.webp';
  var fix = function (p) { if (p && !p.thumb) p.thumb = DEF_THUMB; return p; };
  var byNewest = function (a, b) { return (b.date || '').localeCompare(a.date || '') || b.id - a.id; };
  var strip = function (p) { var c = {}; LIST_COLS.split(',').forEach(function (k) { c[k] = p[k]; }); return fix(c); };

  /* ---------- static: news/posts.js 를 필요할 때만 읽는다 ---------- */
  var staticCache;
  function staticPosts() {
    if (staticCache) return staticCache;
    staticCache = new Promise(function (resolve, reject) {
      if (window.POSTS) return resolve(window.POSTS);
      var s = document.createElement('script');
      s.src = 'news/posts.js';
      s.onload = function () { resolve(window.POSTS || []); };
      s.onerror = function () { reject(new Error('news/posts.js 를 불러오지 못했습니다.')); };
      document.head.appendChild(s);
    }).then(function (all) {
      return all.filter(function (p) { return p.published !== false; }).sort(byNewest);
    });
    return staticCache;
  }
  var staticStore = {
    list: function (o) {
      var per = o.per || 12, page = o.page || 1;
      return staticPosts().then(function (all) {
        return { items: all.slice((page - 1) * per, page * per).map(strip), total: all.length };
      });
    },
    get: function (id) {
      return staticPosts().then(function (all) {
        var i = all.findIndex(function (p) { return p.id === id; });
        if (i < 0) return null;
        return { post: all[i], prev: all[i - 1] ? strip(all[i - 1]) : null, next: all[i + 1] ? strip(all[i + 1]) : null };
      });
    }
  };

  /* ---------- supabase: PostgREST 읽기 전용(anon 키). 쓰기는 관리자/자동화가 service_role 로 따로 한다 ---------- */
  function sb(path, extraHeaders) {
    var h = { apikey: cfg.anonKey, Authorization: 'Bearer ' + cfg.anonKey };
    for (var k in (extraHeaders || {})) h[k] = extraHeaders[k];
    return fetch(cfg.url.replace(/\/$/, '') + '/rest/v1/' + (cfg.table || 'posts') + '?' + path, { headers: h }).then(function (r) {
      if (!r.ok) throw new Error('게시판 데이터를 불러오지 못했습니다(' + r.status + ').');
      return r;
    });
  }
  var ORDER = 'order=date.desc,id.desc';
  var supabaseStore = {
    list: function (o) {
      var per = o.per || 12, page = o.page || 1;
      return sb('select=' + LIST_COLS + '&published=eq.true&' + ORDER + '&limit=' + per + '&offset=' + (page - 1) * per, { Prefer: 'count=exact' })
        .then(function (r) {
          var total = parseInt((r.headers.get('Content-Range') || '').split('/')[1], 10) || 0;
          return r.json().then(function (items) { return { items: items.map(fix), total: total }; });
        });
    },
    get: function (id) {
      return sb('select=*&published=eq.true&id=eq.' + encodeURIComponent(id)).then(function (r) { return r.json(); }).then(function (rows) {
        var p = fix(rows[0]);
        if (!p) return null;
        var d = encodeURIComponent(p.date), i = p.id;
        var older = 'select=' + LIST_COLS + '&published=eq.true&or=(date.lt.' + d + ',and(date.eq.' + d + ',id.lt.' + i + '))&order=date.desc,id.desc&limit=1';
        var newer = 'select=' + LIST_COLS + '&published=eq.true&or=(date.gt.' + d + ',and(date.eq.' + d + ',id.gt.' + i + '))&order=date.asc,id.asc&limit=1';
        return Promise.all([sb(newer).then(function (r) { return r.json(); }), sb(older).then(function (r) { return r.json(); })])
          .then(function (x) { return { post: p, prev: fix(x[0][0] || null), next: fix(x[1][0] || null) }; });
      });
    }
  };

  var impl = cfg.type === 'supabase' ? supabaseStore : staticStore;
  window.NewsStore = {
    list: impl.list,
    get: impl.get,
    latest: function (n) { return impl.list({ page: 1, per: n }).then(function (r) { return r.items; }); }
  };
})();
