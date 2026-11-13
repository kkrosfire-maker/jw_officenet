window.HOME_URL = "index_(261113a)_섹션명.html";

// 게시판 데이터 저장소. 'static' = news/posts.js(내 PC 관리자), 'supabase' = Supabase 테이블 읽기
// Supabase 전환 시: type 을 'supabase' 로 바꾸고 url / anonKey 를 채운다(anonKey 는 공개용 키라 노출돼도 됨, service_role 키는 절대 넣지 말 것).
window.NEWS_BACKEND = { type: 'supabase', url: 'https://mfbclctzkjdsrrsivlmg.supabase.co', anonKey: 'sb_publishable_CKV18Z4BTPr0Z5huTM3d6A_xr07oeBc', table: 'posts' };
// type 을 'supabase' 로 바꾸면 방문자 화면이 Supabase 에서 글을 읽는다(전환 전에 news/seed_existing_posts.sql 실행 필요).
