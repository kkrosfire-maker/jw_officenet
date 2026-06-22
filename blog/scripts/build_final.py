"""
최종 파일 생성기 — draft.md → final.md + final.html

사용법:
  python scripts/build_final.py <주제폴더명>

예시:
  python scripts/build_final.py 갑자기더워지는날씨
  python scripts/build_final.py 여름철식중독
"""
import sys, os, shutil
import sys as _sys; _sys.path.insert(0, os.path.dirname(__file__))
from markdown import md_to_html  # noqa: E402
from config import OUTPUT_BASE   # noqa: E402


def run(topic):
    base     = os.path.join(OUTPUT_BASE, topic)
    src      = os.path.join(base, "draft.md")
    out_html = os.path.join(base, "final.html")
    out_md   = os.path.join(base, "final.md")

    if not os.path.exists(src):
        print(f"ERROR: {src} 가 없습니다.")
        sys.exit(1)

    with open(src, "r", encoding="utf-8") as f:
        md = f.read()

    shutil.copy(src, out_md)
    print(f"  final.md  저장: {out_md}")

    body_html = md_to_html(md, img_base=os.path.join(base, "images"))

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{topic} — 박원종내과 블로그 미리보기</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 40px 20px 80px;
    background: #f5f5f5;
    font-family: 'Noto Sans KR', '맑은 고딕', sans-serif;
    color: #1a1a1a;
    font-size: 17px;
    line-height: 1.85;
  }}
  .container {{
    max-width: 700px;
    margin: 0 auto;
    background: #ffffff;
    border-radius: 8px;
    padding: 48px 52px 64px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  }}
  h1 {{
    font-size: 28px;
    font-weight: 700;
    color: #111;
    margin: 0 0 28px;
    line-height: 1.4;
    border-bottom: 3px solid #1a2340;
    padding-bottom: 16px;
  }}
  h2 {{
    font-size: 22px;
    font-weight: 700;
    color: #1a2340;
    margin: 40px 0 14px;
    padding-left: 12px;
    border-left: 4px solid #F5A623;
  }}
  h3 {{
    font-size: 19px;
    font-weight: 700;
    color: #333;
    margin: 28px 0 10px;
  }}
  p {{
    margin: 0 0 14px;
    word-break: keep-all;
  }}
  strong {{ color: #1a2340; }}
  ul {{
    margin: 8px 0 16px 0;
    padding-left: 24px;
  }}
  li {{ margin-bottom: 6px; }}
  figure {{
    margin: 28px 0;
    text-align: center;
  }}
  figure img {{
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
  }}
  figcaption {{
    margin-top: 8px;
    font-size: 13px;
    color: #888;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0 24px;
    font-size: 15px;
  }}
  th {{
    background: #1a2340;
    color: white;
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
  }}
  td {{
    padding: 9px 14px;
    border-bottom: 1px solid #e8e8e8;
  }}
  tr:nth-child(even) td {{ background: #f9f9f9; }}
  code {{
    background: #f0f0f0;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: monospace;
    font-size: 14px;
  }}
  hr {{ border: none; border-top: 1px solid #eee; margin: 32px 0; }}
  blockquote {{
    margin: 24px 0;
    padding: 16px 20px;
    border-left: 4px solid #F5A623;
    background: #fffbf0;
    border-radius: 0 8px 8px 0;
    font-size: 17px;
    color: #333;
  }}
  .preview-badge {{
    display: inline-block;
    background: #F5A623;
    color: white;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 4px;
    margin-bottom: 24px;
    letter-spacing: 0.5px;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="preview-badge">미리보기 — 박원종내과 블로그</div>
  {body_html}
</div>
</body>
</html>"""

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  final.html 저장: {out_html}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    run(sys.argv[1])
