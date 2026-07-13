import os
import time
import urllib.request
from playwright.sync_api import sync_playwright

URL = "https://pf.kakao.com/_tMlMX/113574741"
SAVE_DIR = r"C:\Users\JW\Desktop\kakao_113574741"

os.makedirs(SAVE_DIR, exist_ok=True)

def download_image(url, filepath):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://pf.kakao.com/",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        with open(filepath, "wb") as f:
            f.write(resp.read())

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()

    print(f"페이지 로딩 중: {URL}")
    page.goto(URL, wait_until="networkidle", timeout=30000)
    time.sleep(3)

    # 스크롤해서 이미지 모두 로드
    for _ in range(10):
        page.evaluate("window.scrollBy(0, 500)")
        time.sleep(0.8)

    # 모든 img 태그 src 수집 (lazy-load 포함)
    img_urls = page.evaluate("""
        () => {
            const imgs = document.querySelectorAll('img');
            return Array.from(imgs).map(img => ({
                src: img.src || img.dataset.src || img.dataset.lazySrc || '',
                naturalW: img.naturalWidth,
                naturalH: img.naturalHeight,
            }));
        }
    """)

    print(f"발견된 img 태그 수: {len(img_urls)}")
    for i in img_urls:
        print(f"  {i['naturalW']}x{i['naturalH']} {i['src'][:100]}")

    # kakaocdn 이미지 + 충분히 큰 것만
    valid_imgs = [
        i for i in img_urls
        if i['src'].startswith('http')
        and i['naturalW'] >= 200
        and i['naturalH'] >= 200
    ]

    print(f"\n다운로드 대상 이미지: {len(valid_imgs)}개")

    downloaded = 0
    for idx, img in enumerate(valid_imgs, 1):
        src = img['src']
        ext = ".jpg"
        if ".png" in src:
            ext = ".png"
        elif ".gif" in src:
            ext = ".gif"
        elif ".webp" in src:
            ext = ".webp"

        filepath = os.path.join(SAVE_DIR, f"{idx:03d}{ext}")
        try:
            download_image(src, filepath)
            print(f"[{idx}/{len(valid_imgs)}] 저장: {filepath}")
            downloaded += 1
        except Exception as e:
            print(f"[{idx}] 실패 ({src[:60]}): {e}")

    browser.close()
    print(f"\n완료: {downloaded}개 이미지 저장됨 → {SAVE_DIR}")
