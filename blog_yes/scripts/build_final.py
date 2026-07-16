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

# Windows 콘솔 기본 코드페이지(cp949)는 em dash(—) 등 일부 유니코드 문자를
# 인코딩하지 못해 print()에서 UnicodeEncodeError로 죽는다. UTF-8로 강제 전환.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(__file__))
from markdown import md_to_html  # noqa: E402
from config import topic_dir     # noqa: E402

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "templates", "blog_post.html"
)


def validate_inputs(md_text: str, images_dir: str) -> None:
    """draft.md에서 참조하는 이미지 파일이 모두 존재하는지 확인한다.

    누락 파일이 있어도 assembler.md Phase 1 방침대로 중단하지 않고 경고만
    출력한다 (해당 이미지는 alt 텍스트만 표시됨). 파이프라인 전 단계가
    아직 안 끝난 것과 무관하게 지금까지 완성된 내용은 확인할 수 있어야 한다.
    images_dir: output/<주제>/images 절대 경로
    """
    import re as _re
    refs = _re.findall(r"!\[[^\]]*\]\(\./images/([^)]+)\)", md_text)
    missing = [f for f in refs if not os.path.exists(os.path.join(images_dir, f))]
    if missing:
        print("WARNING: 다음 이미지 파일이 없습니다 - alt 텍스트만 표시됩니다:")
        for f in missing:
            print(f"  x images/{f}")
    print(f"  이미지 확인: 총 {len(refs)}개 중 누락 {len(missing)}개")


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
