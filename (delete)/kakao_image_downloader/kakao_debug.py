"""DOM 구조 진단 스크립트 - 실제 셀렉터 파악용"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://pf.kakao.com/_tMlMX/113574741"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
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
        time.sleep(0.5)

    info = page.evaluate("""() => {
        const pageH = document.documentElement.scrollHeight;

        // 페이지 내 모든 고유 클래스 수집 (상위 컨테이너 파악용)
        const allClasses = new Set();
        document.querySelectorAll('[class]').forEach(el => {
            el.className.split(' ').forEach(c => { if (c) allClasses.add(c); });
        });

        // 이미지별 상세 정보
        const imgs = Array.from(document.querySelectorAll('img')).map(img => {
            const rect = img.getBoundingClientRect();
            const absTop = Math.round(rect.top + window.scrollY);

            // 부모 계층 클래스 (최대 5단계)
            const parents = [];
            let el = img.parentElement;
            for (let i = 0; i < 5 && el; i++, el = el.parentElement) {
                parents.push({
                    tag: el.tagName,
                    cls: el.className || '',
                    id: el.id || '',
                });
            }

            return {
                src: (img.src || '').substring(0, 100),
                w: img.naturalWidth,
                h: img.naturalHeight,
                absTop,
                pageH,
                parents,
            };
        });

        return { imgs, totalClasses: Array.from(allClasses).sort() };
    }""")
    browser.close()

print(f"\n=== 페이지 전체 높이: {info['imgs'][0]['pageH'] if info['imgs'] else '?'}px ===\n")
print(f"=== 이미지 목록 ({len(info['imgs'])}개) ===")
for i, img in enumerate(info["imgs"], 1):
    print(f"\n[{i:02d}] {img['src']}")
    print(f"     크기: {img['w']}x{img['h']}  |  absTop: {img['absTop']}px ({img['absTop']/img['pageH']*100:.0f}%)")
    print(f"     부모 계층:")
    for j, p in enumerate(img["parents"]):
        indent = "  " * (j + 1)
        print(f"     {indent}<{p['tag']}> class='{p['cls'][:80]}' id='{p['id']}'")

print("\n=== 페이지 내 모든 클래스명 ===")
for cls in info["totalClasses"]:
    if any(k in cls.lower() for k in ["article", "post", "content", "body", "relate", "other", "header", "wrap", "news", "img", "photo"]):
        print(f"  .{cls}")
