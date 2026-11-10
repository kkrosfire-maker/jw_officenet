-- 삭제한 글이 자동 등록으로 다시 올라오지 않게 하는 '재등록 방지 목록'
-- Supabase 대시보드 > SQL Editor 에 붙여넣고 Run 한 번 실행하면 된다. (여러 번 실행해도 안전)
-- 관리자 화면에서 글을 삭제하면 그 글의 원문 링크·제목이 여기에 기록되고,
-- 자동 등록(news_auto/auto_post.py)은 이 목록에 있는 링크와 비슷한 제목을 건너뛴다.

create table if not exists public.rejected_posts (
  src_key    text primary key,                 -- 삭제한 글의 원문 링크
  title      text,                             -- 삭제한 글의 제목(비슷한 기사 거르기용)
  created_at timestamptz not null default now()
);

alter table public.rejected_posts enable row level security;

drop policy if exists "관리자: 재등록 방지 목록" on public.rejected_posts;
create policy "관리자: 재등록 방지 목록" on public.rejected_posts
  for all to authenticated
  using (public.is_admin()) with check (public.is_admin());

grant select, insert, update, delete on public.rejected_posts to authenticated;
-- 방문자(anon)에게는 아무 권한도 주지 않는다. 자동 등록은 비밀 키(service_role)로 읽는다.
