"""
본문 이미지 캡처기 — HTML 콘텐츠를 클립보드 PNG 프레임에 합성하여 1:1 PNG 저장

사용법:
  python scripts/capture_bodies.py <주제폴더명>

동작:
  - output/<주제>/tmp_html/body-N.html 을 순서대로 처리
  - 각 HTML에 CSS 오버라이드 주입 → Playwright 1080×1080 캡처
  - 클로드코드 교육용.png (프레임) 투명 오버레이 합성
  - output/<주제>/images/body-N.png 저장 (1:1, 1080×1080)
  - 마지막 이미지: 4.png 복사 → body-{last+1}.png

HTML 클래스명 규칙 (Convention B 단일 표준):
  .clipboard-frame / .clip-wrapper / .inner-card

예시:
  python scripts/capture_bodies.py 여름철식중독
  python scripts/capture_bodies.py 갑자기더워지는날씨
"""
import sys
import os
import re
import shutil
import tempfile
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(__file__))
from config import (  # noqa: E402
    OUTPUT_BASE, REF_DIR, FRAME_PNG,
    VIEWPORT_W, VIEWPORT_H,
    FRAME_LEFT, FRAME_TOP, FRAME_W, FRAME_H,
)

# ── CSS 오버라이드 ─────────────────────────────────────────────────
# Convention B 단일 표준: .clipboard-frame / .clip-wrapper / .inner-card
OVERRIDE_CSS = (
    "<style id='frame-override'>"

    # body 리셋
    "html,body{"
    "width:1080px!important;height:1080px!important;"
    "overflow:hidden!important;background:white!important;"
    "padding:0!important;margin:0!important;position:relative!important;}"

    # 클립보드 프레임 — PNG 흰 영역에 정확히 맞춤
    ".clipboard-frame{"
    "position:absolute!important;"
    f"left:{FRAME_LEFT}px!important;top:{FRAME_TOP}px!important;"
    f"width:{FRAME_W}px!important;height:{FRAME_H}px!important;"
    "background:white!important;border-radius:0!important;box-shadow:none!important;"
    "padding:55px 50px 40px!important;"
    "overflow:hidden!important;}"
    ".clip-wrapper{display:none!important;}"
    ".inner-card{background:transparent!important;border-radius:0!important;"
    "padding:0!important;overflow:visible!important;}"

    "</style>"
)


def build_transparent_frame() -> Image.Image:
    """FRAME_PNG 흰 픽셀을 투명으로 바꿔 오버레이용 Image를 반환한다."""
    frame = Image.open(FRAME_PNG).convert("RGBA")
    arr = np.array(frame, dtype=np.int32)
    is_light = (arr[:,:,0] > 225) & (arr[:,:,1] > 225) & (arr[:,:,2] > 225)
    arr_u8 = arr.astype(np.uint8)
    arr_u8[is_light, 3] = 0
    return Image.fromarray(arr_u8, "RGBA")


def inject_css_to_temp(html_path: str, css: str) -> str:
    """HTML에 css를 </head> 직전에 주입한 임시 파일을 만들고 경로를 반환한다."""
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    modified = html.replace("</head>", css + "</head>")
    tmp_path = os.path.join(tempfile.gettempdir(), f"cb_{os.path.basename(html_path)}")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(modified)
    return tmp_path


def screenshot_and_composite(tmp_html: str, transparent_frame: Image.Image, page, out_path: str):
    """임시 HTML을 Playwright로 캡처하고 transparent_frame을 합성해 out_path에 저장한다."""
    tmp_png = tmp_html + ".png"
    page.goto("file:///" + tmp_html.replace("\\", "/"))
    page.wait_for_load_state("networkidle")
    page.screenshot(path=tmp_png, full_page=False)
    base = Image.open(tmp_png).convert("RGBA")
    base.alpha_composite(transparent_frame)
    base.convert("RGB").save(out_path, "PNG")
    print(f"  Saved: {os.path.basename(out_path)}")


def run(topic: str):
    topic_dir = os.path.join(OUTPUT_BASE, topic)
    html_dir  = os.path.join(topic_dir, "tmp_html")
    img_dir   = os.path.join(topic_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    if not os.path.isdir(html_dir):
        print(f"ERROR: tmp_html/ 폴더가 없습니다 — {html_dir}")
        sys.exit(1)

    pattern = re.compile(r"^body-(\d+)\.html$")
    html_files = sorted(
        [f for f in os.listdir(html_dir) if pattern.match(f)],
        key=lambda f: int(pattern.match(f).group(1)),
    )

    if not html_files:
        print("ERROR: tmp_html/ 에 body-N.html 파일이 없습니다.")
        sys.exit(1)

    transparent_frame = build_transparent_frame()
    print(f"Frame loaded. Processing {len(html_files)} files for '{topic}'...")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": VIEWPORT_W, "height": VIEWPORT_H})

        for fname in html_files:
            n = pattern.match(fname).group(1)
            html_path = os.path.join(html_dir, fname)
            out_path  = os.path.join(img_dir, f"body-{n}.png")
            tmp       = inject_css_to_temp(html_path, OVERRIDE_CSS)
            screenshot_and_composite(tmp, transparent_frame, page, out_path)

        browser.close()

    # 마지막 클리닉 정보 카드 (4.png 복사)
    last_n = int(pattern.match(html_files[-1]).group(1)) + 1
    src = os.path.join(REF_DIR, "4.png")
    dst = os.path.join(img_dir, f"body-{last_n}.png")
    if os.path.exists(src):
        shutil.copy(src, dst)
        print(f"  Copied 4.png -> body-{last_n}.png")

    print(f"\nDone - {len(html_files)} images captured for '{topic}'")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    run(sys.argv[1])
