"""카카오톡 채널 공지 페이지(pf.kakao.com)에서 본문 발췌 + 이미지 다운로드."""
import html as htmllib
import os
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def render_html(url: str) -> str:
    """Playwright(설치된 Chrome)로 렌더링한 DOM을 반환."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        content = page.content()
        browser.close()
    return content


def _to_lines(fragment: str) -> list[str]:
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", fragment, flags=re.S)
    t = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", t)
    t = htmllib.unescape(re.sub(r"<[^>]+>", "", t))
    return [ln.strip() for ln in t.splitlines() if ln.strip()]


def _main_post(html: str) -> str:
    """첫 번째 포스트 영역만 자른다 ('15분 전' 같은 시간 표기 또는 '이 채널의 다른 소식' 앞까지)."""
    start = html.find("포스트 본문영역")
    end = html.find("이 채널의 다른 소식")
    return html[start if start >= 0 else 0 : end if end > 0 else len(html)]


def extract_text(html: str) -> dict:
    """제목과, 첫 ▶ 줄~마지막 ▶ 항목(첫 등장)까지의 발췌문을 반환."""
    lines = _to_lines(_main_post(html))
    title = next((ln for ln in lines if ln.startswith("📢")), "")
    # 제목 줄에 '안녕하세요'가 붙어 나오는 경우 분리
    title = title.split("안녕하세요")[0].strip()

    s = next((i for i, ln in enumerate(lines) if ln.startswith("▶")), 0)
    arrows = [i for i in range(s, len(lines)) if lines[i].startswith("▶")]
    last = lines[arrows[-1]]
    e = next(i for i in arrows if lines[i] == last)  # 요약부 끝 = 마지막 ▶ 줄의 첫 등장
    m = re.search(r"(\d+)년\s*(\d+)월\s*(\d+)일", title)
    md = f"{int(m.group(2)):02d}/{int(m.group(3)):02d}" if m else ""
    return {"title": title, "date": md, "body": "\n".join(lines[s : e + 1])}


def extract_images(html: str) -> list[str]:
    """본문 이미지(alt="이미지")만 순서대로, 중복 제거."""
    seen, out = set(), []
    for m in re.finditer(r'<img[^>]*alt="이미지"[^>]*>', _main_post(html)):
        src = re.search(r'src="(https?://[^"]+)"', m.group(0))
        if src and src.group(1) not in seen:
            seen.add(src.group(1))
            out.append(src.group(1))
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

    url = sys.argv[1]
    h = render_html(url)
    info = extract_text(h)
    imgs = extract_images(h)
    print(info["title"], "\n---\n" + info["body"], f"\n---\n이미지 {len(imgs)}장")
