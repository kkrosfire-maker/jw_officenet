"""하루 1편 CSO 뉴스 자동 등록 (검토 대기로 저장)

흐름: 참고 사이트 API(medicalnews-tau) 후보 수집 -> 이미 올린 글과 중복 제거 -> 관련도 최고 1건을
      Supabase posts 에 published=false, auto=true 로 저장 -> 관리자가 admin.html 에서 검토 후 공개.

환경변수
  SUPABASE_SECRET_KEY  (필수, 쓰기용 비밀 키. 절대 코드/채팅에 넣지 말 것 - GitHub Secrets 로만 보관)
  SUPABASE_URL         (선택, 기본값은 이 프로젝트 주소)
옵션
  --dry-run  저장하지 않고 어떤 글을 고를지만 출력(공개용 키로 읽기만 하므로 SECRET 키 불필요)
표준 라이브러리만 사용한다.
"""
import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mfbclctzkjdsrrsivlmg.supabase.co").rstrip("/")
ANON_KEY = "sb_publishable_CKV18Z4BTPr0Z5huTM3d6A_xr07oeBc"  # 공개용 키(읽기 전용)
SOURCE_API = "https://medicalnews-tau.vercel.app/api/news"
MIN_SCORE = 80          # CSO 관련도 최소 점수
MAX_AGE_DAYS = 3        # 발행 후 며칠 이내 기사만
SIM_THRESHOLD = 0.55    # 제목 유사도(이 이상이면 같은 이슈로 보고 건너뜀)
RECENT_COMPARE = 300    # 비교할 기존 글 수
DEFAULT_THUMB = "assets/news_thumbnail_default.webp"
KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "jungwon-news-auto/1.0"}


def http(method, url, headers=None, body=None, timeout=30):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={**UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"message": raw[:200]}


def norm(t):
    return re.sub(r"[^0-9a-z가-힣]", "", (t or "").lower())


def bigrams(t):
    n = norm(t)
    return {n[i:i + 2] for i in range(len(n) - 1)}


def similar(a, b):
    ra = difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()
    ba, bb = bigrams(a), bigrams(b)
    jac = len(ba & bb) / len(ba | bb) if ba and bb else 0
    return max(ra, jac)


def fetch_candidates():
    qs = urllib.parse.urlencode({"view": "inbox", "minScore": MIN_SCORE, "category": "ALL", "search": "", "page": 1})
    code, d = http("GET", f"{SOURCE_API}?{qs}")
    if code != 200 or not d or not d.get("success"):
        raise SystemExit(f"참고 사이트 API 오류: {code} {str(d)[:120]}")
    cut = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    out = []
    for n in d.get("news", []):
        try:
            pub = datetime.fromisoformat(n["pub_date"].replace("Z", "+00:00"))
        except Exception:
            continue
        if pub >= cut and n.get("title") and n.get("link") and (n.get("score") or 0) >= MIN_SCORE:
            n["_pub"] = pub
            out.append(n)
    out.sort(key=lambda n: (-(n.get("score") or 0), -n["_pub"].timestamp()))
    return out


def existing_posts(key):
    qs = f"select=src_key,title&order=id.desc&limit={RECENT_COMPARE}"
    code, rows = http("GET", f"{SUPABASE_URL}/rest/v1/posts?{qs}", {"apikey": key, "Authorization": f"Bearer {key}"})
    if code != 200:
        raise SystemExit(f"기존 글 조회 실패: {code} {rows}")
    return rows


def to_post(n):
    src = (n.get("source") or "").strip()
    summary = (n.get("summary") or "").strip()[:500]
    body = summary + (f"\n\n출처: {src}" if src else "")
    return {
        "date": datetime.now(KST).strftime("%Y-%m-%d"),
        "title": n["title"].strip()[:200],
        "summary": summary,
        "body": body[:20000],
        "link": n["link"],
        "src_key": n["link"],
        "source": src,
        "category": (n.get("category") or "").strip(),
        "score": int(n["score"]),
        "thumb": DEFAULT_THUMB,
        "auto": True,
        "published": False,  # 관리자 검토 후 공개
    }


def main():
    dry = "--dry-run" in sys.argv
    secret = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not dry and not secret:
        raise SystemExit("SUPABASE_SECRET_KEY 환경변수가 없습니다.")
    key = ANON_KEY if dry else secret

    cands = fetch_candidates()
    print(f"후보 {len(cands)}건 (점수 {MIN_SCORE}+ · 최근 {MAX_AGE_DAYS}일)")
    have = existing_posts(key) if not dry else _anon_existing()
    keys = {r.get("src_key") for r in have if r.get("src_key")}
    titles = [r["title"] for r in have]

    for n in cands:
        if n["link"] in keys:
            continue
        dup = max((similar(n["title"], t) for t in titles), default=0)
        if dup >= SIM_THRESHOLD:
            print(f"  건너뜀(유사 {dup:.2f}): {n['title'][:40]}")
            continue
        post = to_post(n)
        print(f"선택: [{post['score']}점/{post['source']}] {post['title']}")
        if dry:
            print("  (dry-run: 저장하지 않음)")
            return
        code, res = http("POST", f"{SUPABASE_URL}/rest/v1/posts",
                         {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=minimal"}, post)
        if code in (200, 201, 204):
            print("검토 대기로 저장했습니다.")
            return
        if code == 409:  # src_key 중복 -> 다음 후보
            print("  이미 있는 기사, 다음 후보 확인")
            keys.add(n["link"])
            continue
        raise SystemExit(f"저장 실패: {code} {res}")
    print("오늘 올릴 새 기사가 없습니다(조건 충족 후보 없음).")


def _anon_existing():
    # dry-run: 공개된 글만 읽을 수 있음(검토 대기 글은 못 봄) - 시험용
    return existing_posts(ANON_KEY)


if __name__ == "__main__":
    main()
