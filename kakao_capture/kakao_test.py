"""현재 GUI와 동일한 JS로 실제 이미지 목록 확인"""
import sys
import time
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://pf.kakao.com/_tMlMX/113574741"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    )
    page = context.new_page()
    print(f"로딩: {URL}")
    page.goto(URL, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    for _ in range(10):
        page.evaluate("window.scrollBy(0, 500)")
        time.sleep(0.8)

    imgs = page.evaluate("""() => {
        let bodyImgs = Array.from(document.querySelectorAll('.item_archive_image img'));
        if (bodyImgs.length === 0) {
            bodyImgs = Array.from(document.querySelectorAll('.wrap_archive_content img'));
        }
        if (bodyImgs.length === 0) {
            const EXCL = '.head_channel, .wrap_qr, .box_qr, .wrap_fit_thumb, .box_list_board, .item_thumb';
            const excludedEls = Array.from(document.querySelectorAll(EXCL));
            bodyImgs = Array.from(document.querySelectorAll('img'))
                .filter(img => !excludedEls.some(el => el.contains(img)));
        }
        return bodyImgs.map(img => ({
            src: img.src || img.dataset.src || img.dataset.lazySrc || '',
            w: img.naturalWidth,
            h: img.naturalHeight,
        }));
    }""")
    browser.close()

print(f"\nJS 반환 이미지: {len(imgs)}개")
for i, img in enumerate(imgs, 1):
    print(f"  [{i:02d}] {img['w']}x{img['h']}  {img['src'][:80]}")

# Python 필터 결과
visible = [i for i in imgs if i["src"].startswith("http") and i["w"] >= 200 and i["h"] >= 200]
lazy    = [i for i in imgs if i["src"].startswith("http") and i["w"] == 0 and i["h"] == 0
           and "kakaocdn.net" in i["src"]]
targets = visible + lazy

print(f"\n최종 다운로드 대상: {len(targets)}개 (visible={len(visible)}, lazy={len(lazy)})")
for i, img in enumerate(targets, 1):
    print(f"  [{i:02d}] {img['w']}x{img['h']}  {img['src'][:80]}")
