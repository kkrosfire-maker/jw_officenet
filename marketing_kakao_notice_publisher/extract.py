"""카카오톡 채널 공지(pf.kakao.com)에서 제목·발췌문·이미지를 가져온다.

2026-10 채널 화면 개편 이후, 화면(HTML)을 긁지 않고 채널 페이지가 내부적으로 쓰는
JSON API(rocket-web)를 직접 읽는다. 로그인·브라우저 없이 동작한다.
"""
import json
import os
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
API = "https://pf.kakao.com/rocket-web/web/profiles/{profile}/combined-posts/post/{post}"


def _parse_url(url: str) -> tuple[str, str]:
    m = re.search(r"pf\.kakao\.com/(_\w+)/(\d+)", url)
    if not m:
        raise ValueError("공지 URL 형식이 아닙니다. 예: https://pf.kakao.com/_tMlMX/114944401")
    return m.group(1), m.group(2)


def fetch_post(url: str) -> dict:
    """API에서 공지 글 데이터(payload)를 받아온다."""
    profile, post = _parse_url(url)
    req = urllib.request.Request(API.format(profile=profile, post=post), headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)["payload"]


def extract_text(post: dict) -> dict:
    """제목, MM/DD 날짜, 본문의 첫 ▶ 줄부터 끝까지(요약부)를 반환."""
    title = (post.get("title") or "").strip()
    text = "".join(c.get("v", "") for c in post.get("contents") or [])
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    s = next((i for i, ln in enumerate(lines) if ln.startswith("▶")), None)
    body = "\n".join(lines[s:]) if s is not None else ""

    m = re.search(r"(\d+)년\s*(\d+)월\s*(\d+)일", title) or re.search(r"\d{4}\.(\d+)\.(\d+)", text)
    md = f"{int(m.group(m.lastindex - 1)):02d}/{int(m.group(m.lastindex)):02d}" if m else ""
    return {"title": title, "date": md, "body": body}


def extract_images(post: dict) -> list[str]:
    """본문 이미지 URL(큰 사이즈)을 올린 순서대로, 중복 제거."""
    seen, out = set(), []
    for m in post.get("media") or []:
        if m.get("type") != "image":
            continue
        u = m.get("xlarge_url") or m.get("url")
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def download_images(urls: list[str], out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, u in enumerate(urls, 1):
        ext = re.search(r"\.(jpg|jpeg|png|gif|webp)(?:$|\?)", u, re.I)
        path = os.path.join(out_dir, f"{i:03d}{('.' + ext.group(1).lower()) if ext else '.jpg'}")
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=15) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        paths.append(path)
    return paths


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    p = fetch_post(sys.argv[1])
    info = extract_text(p)
    imgs = extract_images(p)
    print(info["title"], info["date"], "\n---\n" + info["body"], f"\n---\n이미지 {len(imgs)}장")
