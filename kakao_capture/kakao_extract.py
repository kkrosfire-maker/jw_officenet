import asyncio
import os
import re
import urllib.request
from playwright.async_api import async_playwright

URL = "https://pf.kakao.com/_tMlMX/113415892"
SAVE_DIR = r"C:\Users\JW\Desktop\두견"
os.makedirs(SAVE_DIR, exist_ok=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # 텍스트 추출
        text = await page.evaluate("""() => {
            return document.body.innerText;
        }""")

        txt_path = os.path.join(SAVE_DIR, "내용.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[텍스트 저장] {txt_path}")

        # 이미지 URL 추출
        img_urls = await page.evaluate("""() => {
            const imgs = Array.from(document.querySelectorAll('img'));
            return imgs.map(img => img.src || img.dataset.src).filter(src => src && src.startsWith('http'));
        }""")

        print(f"[이미지 발견] {len(img_urls)}개")

        for i, url in enumerate(img_urls):
            ext = url.split("?")[0].split(".")[-1]
            if ext.lower() not in ["jpg", "jpeg", "png", "gif", "webp"]:
                ext = "jpg"
            fname = os.path.join(SAVE_DIR, f"image_{i+1:02d}.{ext}")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    with open(fname, "wb") as f:
                        f.write(resp.read())
                print(f"  [저장] {fname}")
            except Exception as e:
                print(f"  [실패] {url} — {e}")

        await browser.close()
        print("\n완료!")

asyncio.run(main())
