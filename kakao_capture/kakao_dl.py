"""카카오 채널 게시물에서 이미지를 다운로드한다.

사용법:
    python kakao_dl.py <URL> [저장_폴더]

예:
    python kakao_dl.py https://pf.kakao.com/_tMlMX/113574741
    python kakao_dl.py https://pf.kakao.com/_tMlMX/113574741 C:\\Users\\JW\\Desktop\\출력
"""
import argparse
import os
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def _ext(src: str) -> str:
    for e in (".png", ".gif", ".webp"):
        if e in src:
            return e
    return ".jpg"


def _download(url: str, path: Path) -> None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://pf.kakao.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        path.write_bytes(resp.read())


def download(url: str, save_dir: Path, min_size: int = 200) -> int:
    """URL의 이미지를 save_dir에 저장하고 저장 수를 반환한다."""
    save_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        print(f"페이지 로딩: {url}")
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(3)

        for _ in range(10):
            page.evaluate("window.scrollBy(0, 500)")
            time.sleep(0.8)

        imgs = page.evaluate("""() => {
            // 1순위: 카카오 채널 본문 이미지 컨테이너
            let bodyImgs = Array.from(document.querySelectorAll('.item_archive_image img'));

            // 2순위: 래퍼 컨테이너
            if (bodyImgs.length === 0) {
                bodyImgs = Array.from(document.querySelectorAll('.wrap_archive_content img'));
            }

            // 폴백: 헤더·다른소식 영역을 명시적으로 제외
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

    visible = [i for i in imgs if i["src"].startswith("http") and i["w"] >= min_size and i["h"] >= min_size]
    lazy    = [i for i in imgs if i["src"].startswith("http") and i["w"] == 0 and i["h"] == 0
               and "kakaocdn.net" in i["src"]]
    targets = visible + lazy

    print(f"다운로드 대상: {len(targets)}개 ({len(visible)} visible + {len(lazy)} lazy)")

    saved = 0
    for idx, img in enumerate(targets, 1):
        src  = img["src"]
        dest = save_dir / f"{idx:03d}{_ext(src)}"
        try:
            _download(src, dest)
            print(f"  [{idx}/{len(targets)}] {dest.name}")
            saved += 1
        except Exception as e:
            print(f"  [{idx}] 실패: {e}")

    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="카카오 채널 이미지 다운로더")
    parser.add_argument("url", help="카카오 채널 게시물 URL")
    parser.add_argument(
        "save_dir",
        nargs="?",
        help="저장 폴더 (기본: 바탕화면/kakao_<포스트번호>)",
    )
    args = parser.parse_args()

    if args.save_dir:
        save_dir = Path(args.save_dir)
    else:
        post_id = args.url.rstrip("/").split("/")[-1]
        save_dir = Path.home() / "Desktop" / f"kakao_{post_id}"

    count = download(args.url, save_dir)
    print(f"\n완료: {count}개 → {save_dir}")


if __name__ == "__main__":
    main()
