-- Supabase SQL Editor 에서 한 번 실행. 관리자 1명 + 자동 글은 검토 후 공개.
-- 실행 전: Authentication > Providers > Email 에서 "Allow new users to sign up" 을 끄고,
--          Authentication > Users 에서 관리자 이메일 계정을 직접 생성(Add user)한다.

create table if not exists public.posts (
  id          bigint generated always as identity primary key,
  date        date        not null,                  -- 게시 날짜(화면 표시용)
  title       text        not null check (char_length(title) between 1 and 200),
  summary     text        not null default '' check (char_length(summary) <= 500),
  body        text        not null default '' check (char_length(body) <= 20000),
  link        text        not null default '',        -- 원문 링크
  thumb       text        not null default '',        -- Storage 공개 URL 또는 assets/ 경로
  source      text        not null default '',        -- 매체명
  category    text        not null default '',
  score       int,                                     -- 자동 선별 시 CSO 관련도 점수
  src_key     text unique,                             -- 중복 방지 키(원문 링크). 같은 값은 재등록 불가
  auto        boolean     not null default false,      -- true = 자동 수집 글
  published   boolean     not null default true,       -- false = 검토 대기(자동 글의 기본값)
  created_at  timestamptz not null default now()
);
create index if not exists posts_list_idx on public.posts (published, date desc, id desc);

-- 관리자 목록 (user_id 는 Authentication > Users 의 UID)
create table if not exists public.admins (user_id uuid primary key references auth.users(id) on delete cascade);
alter table public.admins enable row level security;   -- 정책 없음 = 외부 접근 불가
create or replace function public.is_admin() returns boolean
  language sql stable security definer set search_path = public
  as $$ select exists(select 1 from public.admins where user_id = auth.uid()) $$;

alter table public.posts enable row level security;
drop policy if exists "방문자: 공개 글 읽기" on public.posts;
create policy "방문자: 공개 글 읽기"   on public.posts for select to anon, authenticated using (published or public.is_admin());
drop policy if exists "관리자: 등록" on public.posts;
create policy "관리자: 등록"           on public.posts for insert to authenticated with check (public.is_admin());
drop policy if exists "관리자: 수정" on public.posts;
create policy "관리자: 수정"           on public.posts for update to authenticated using (public.is_admin()) with check (public.is_admin());
drop policy if exists "관리자: 삭제" on public.posts;
create policy "관리자: 삭제"           on public.posts for delete to authenticated using (public.is_admin());

-- 테이블 노출 설정과 무관하게 동작하도록 권한을 명시(실제 접근 제한은 위 RLS 정책이 담당)
grant select on public.posts to anon;
grant select, insert, update, delete on public.posts to authenticated;
grant execute on function public.is_admin() to anon, authenticated;

-- 썸네일 저장소
insert into storage.buckets (id, name, public) values ('news-thumbs', 'news-thumbs', true) on conflict do nothing;
drop policy if exists "썸네일: 누구나 읽기" on storage.objects;
create policy "썸네일: 누구나 읽기" on storage.objects for select using (bucket_id = 'news-thumbs');
drop policy if exists "썸네일: 관리자 쓰기" on storage.objects;
create policy "썸네일: 관리자 쓰기" on storage.objects for insert to authenticated with check (bucket_id = 'news-thumbs' and public.is_admin());
drop policy if exists "썸네일: 관리자 수정" on storage.objects;
create policy "썸네일: 관리자 수정" on storage.objects for update to authenticated using (bucket_id = 'news-thumbs' and public.is_admin());
drop policy if exists "썸네일: 관리자 삭제" on storage.objects;
create policy "썸네일: 관리자 삭제" on storage.objects for delete to authenticated using (bucket_id = 'news-thumbs' and public.is_admin());

-- 관리자 등록: 아래 UID 를 본인 계정의 UID 로 바꿔서 실행
-- insert into public.admins (user_id) values ('여기에-관리자-UID');
