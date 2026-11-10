"""sitemap.xml 생성: 홈 + 게시판 + 공개된 기사 상세 페이지.

사용: python -X utf8 news_auto/build_sitemap.py
  - 공개용 키로 공개된 글만 읽는다(비밀 키 불필요). 결과는 이 폴더의 상위(사이트 루트)에 sitemap.xml 로 저장.
  - 사이트 주소는 SITE 상수만 바꾸면 된다(도메인을 연결하면 여기와 robots.txt 의 Sitemap 줄, llms.txt 링크를 같이 바꾼다).
표준 라이브러리만 사용한다.
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

SITE = "https://jungwon-unius-homepage.vercel.app"
SUPABASE_URL = "https://mfbclctzkjdsrrsivlmg.supabase.co"
ANON_KEY = "sb_publishable_CKV18Z4BTPr0Z5huTM3d6A_xr07oeBc"  # 공개용 키(읽기 전용)
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sitemap.xml")
KST = timezone(timedelta(hours=9))


def published_posts():
    url = f"{SUPABASE_URL}/rest/v1/posts?select=id,date&published=eq.true&order=date.desc,id.desc&limit=5000"
    req = urllib.request.Request(url, headers={"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def entry(loc, lastmod, freq, prio):
    return (f"  <url>\n    <loc>{escape(loc)}</loc>\n    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>")


def main():
    posts = published_posts()
    today = datetime.now(KST).strftime("%Y-%m-%d")
    newest = posts[0]["date"] if posts else today
    rows = [entry(f"{SITE}/", today, "weekly", "1.0"),  # 홈은 사이트를 고친 날 기준이라 오늘로 둔다
            entry(f"{SITE}/news.html", newest, "daily", "0.8")]
    rows += [entry(f"{SITE}/news_view.html?id={p['id']}", p["date"], "monthly", "0.6") for p in posts]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)
    print(f"sitemap.xml 저장: URL {len(rows)}개 (공개 글 {len(posts)}건) -> {OUT}")


if __name__ == "__main__":
    main()
