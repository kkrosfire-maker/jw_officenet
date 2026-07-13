"""
최종 파일 생성기 — draft.md → final.md + final.html

사용법:
  python scripts/build_final.py <주제폴더명>

예시:
  python scripts/build_final.py 갑자기더워지는날씨
  python scripts/build_final.py 여름철식중독
"""
import sys
import os
import shutil
sys.path.insert(0, os.path.dirname(__file__))
from markdown import md_to_html  # noqa: E402
from config import topic_dir     # noqa: E402

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "templates", "blog_post.html"
)


def validate_inputs(md_text: str, images_dir: str) -> None:
    """draft.md에서 참조하는 이미지 파일이 모두 존재하는지 확인한다.

    누락 파일이 있으면 목록을 출력하고 sys.exit(1).
    images_dir: output/<주제>/images 절대 경로
    """
    import re as _re
    refs = _re.findall(r"!\[[^\]]*\]\(\./images/([^)]+)\)", md_text)
    missing = [f for f in refs if not os.path.exists(os.path.join(images_dir, f))]
    if missing:
        print("ERROR: 다음 이미지 파일이 없습니다 — Step 3(이미지 생성)을 먼저 실행하세요.")
        for f in missing:
            print(f"  ✗ images/{f}")
        sys.exit(1)
    print(f"  이미지 확인 OK ({len(refs)}개)")


def run(topic):
    base     = topic_dir(topic)
    src      = os.path.join(base, "draft.md")
    out_html = os.path.join(base, "final.html")
    out_md   = os.path.join(base, "final.md")

    if not os.path.exists(src):
        print(f"ERROR: {src} 가 없습니다.")
        sys.exit(1)

    with open(src, "r", encoding="utf-8") as f:
        md = f.read()

    validate_inputs(md, os.path.join(base, "images"))

    shutil.copy(src, out_md)
    print(f"  final.md  저장: {out_md}")

    body_html = md_to_html(md, img_base=os.path.join(base, "images"))

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read().replace("{title}", topic).replace("{body_html}", body_html)

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  final.html 저장: {out_html}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    run(sys.argv[1])
