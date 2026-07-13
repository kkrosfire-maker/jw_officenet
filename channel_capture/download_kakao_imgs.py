import re
import urllib.request
import os
import subprocess

URL = "https://pf.kakao.com/_tMlMX/113566940"
DESKTOP = 'C:/Users/JW/Desktop'
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
HTML_FILE = os.path.join(os.path.dirname(__file__), 'kakao_page.html')

# 1. 페이지 렌더링
print("페이지 렌더링 중...")
result = subprocess.run(
    [CHROME, '--headless', '--dump-dom', '--virtual-time-budget=10000', URL],
    capture_output=True, text=True, encoding='utf-8', errors='replace'
)
with open(HTML_FILE, 'w', encoding='utf-8') as f:
    f.write(result.stdout)

with open(HTML_FILE, 'r', encoding='utf-8') as f:
    html = f.read()

# 2. 페이지 순서대로 img src 추출 (중복 제거, 순서 유지)
pattern = re.compile(r'(?:src|data-src)="(https?://[^"]+\.(?:jpg|jpeg|png|gif|webp)[^"]*)"', re.IGNORECASE)
seen = []
seen_set = set()
for m in pattern.finditer(html):
    url = m.group(1)
    if url not in seen_set:
        seen_set.add(url)
        seen.append(url)

print(f"발견된 이미지: {len(seen)}개")

# 3. 다운로드 (001, 002, 003 순서로 바탕화면에 저장)
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

for i, url in enumerate(seen, 1):
    ext = re.search(r'\.(jpg|jpeg|png|gif|webp)', url, re.IGNORECASE)
    ext = ext.group(0).lower() if ext else '.jpg'
    filename = os.path.join(DESKTOP, f'kakao_{i:03d}{ext}')
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        with open(filename, 'wb') as f:
            f.write(data)
        print(f"[{i:03d}] 저장 완료: {os.path.basename(filename)} ({len(data):,} bytes)")
    except Exception as e:
        print(f"[{i:03d}] 실패: {e}")

print("\n전체 완료")
