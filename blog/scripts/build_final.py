"""
최종 파일 생성기 — draft.md → final.md + final.html

사용법:
  python scripts/build_final.py <주제폴더명>

예시:
  python scripts/build_final.py 갑자기더워지는날씨
  python scripts/build_final.py 여름철식중독
"""
import sys, re, os, shutil

OUTPUT_BASE = r"C:\Users\JW\Desktop\workspace\blog\output"


def inline(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def md_to_html(text, base):
    lines = text.split("\n")
    html_lines = []
    in_table = False
    table_buf = []
    in_ul = False
    ul_buf = []

    def flush_table(buf):
        rows = []
        for row in buf:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            rows.append(cells)
        if not rows:
            return ""
        head = rows[0]
        body = rows[2:] if len(rows) > 2 else []
        th = "".join(f"<th>{c}</th>" for c in head)
        trs = "".join(
            "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
            for r in body
        )
        return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"

    def flush_ul(buf):
        items = "".join(f"<li>{inline(re.sub(r'^\s*[-*]\s+', '', l))}</li>" for l in buf)
        return f"<ul>{items}</ul>"

    img_base = os.path.join(base, "images").replace("\\", "/")

    for line in lines:
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)\s*$", line.strip())
        if m:
            if in_table:
                html_lines.append(flush_table(table_buf)); table_buf = []; in_table = False
            if in_ul:
                html_lines.append(flush_ul(ul_buf)); ul_buf = []; in_ul = False
            alt, src = m.group(1), m.group(2)
            abs_src = src.replace("./images/", img_base + "/")
            html_lines.append(f'<figure><img src="{abs_src}" alt="{alt}"><figcaption>{alt}</figcaption></figure>')
            continue

        if re.match(r"^\s*\|", line):
            if in_ul:
                html_lines.append(flush_ul(ul_buf)); ul_buf = []; in_ul = False
            in_table = True
            table_buf.append(line)
            continue
        if in_table:
            html_lines.append(flush_table(table_buf)); table_buf = []; in_table = False

        if re.match(r"^\s*[-*]\s+", line):
            if not in_ul:
                in_ul = True; ul_buf = []
            ul_buf.append(line)
            continue
        if in_ul:
            html_lines.append(flush_ul(ul_buf)); ul_buf = []; in_ul = False

        if re.match(r"^-{3,}$", line.strip()):
            html_lines.append("<hr>")
            continue

        if line.startswith("# "):
            html_lines.append(f"<h1>{inline(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{inline(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{inline(line[4:].strip())}</h3>")
        elif re.match(r"^>\s+", line):
            html_lines.append(f"<blockquote>{inline(line[1:].strip())}</blockquote>")
        elif line.strip() == "":
            html_lines.append("")
        else:
            html_lines.append(f"<p>{inline(line)}</p>")

    if in_table: html_lines.append(flush_table(table_buf))
    if in_ul:    html_lines.append(flush_ul(ul_buf))

    return "\n".join(html_lines)


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

    body_html = md_to_html(md, base)

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
