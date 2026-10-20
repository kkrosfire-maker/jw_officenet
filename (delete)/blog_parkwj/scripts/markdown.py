"""
Markdown → HTML 변환기

지원 구문:
  # h1  ## h2  ### h3
  **bold**  *italic*  `code`
  - 또는 * 으로 시작하는 unordered list
  > blockquote
  | 표 | (GFM 스타일, 구분행 포함)
  --- (hr)
  ![alt](./images/filename.png)  → <figure> 태그로 변환

사용법:
  from scripts.markdown import inline, md_to_html

  html_fragment = md_to_html(markdown_text, img_base="/abs/path/to/images")
"""
import re
import os


def inline(text):
    """인라인 마크업을 HTML 태그로 변환한다."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",         text)
    text = re.sub(r"`(.+?)`",       r"<code>\1</code>",      text)
    return text


def md_to_html(text, img_base=""):
    """
    Markdown 텍스트를 HTML 조각(fragment)으로 변환한다.

    img_base: ./images/ 경로를 치환할 절대 경로 (빈 문자열이면 치환 안 함)
    """
    lines = text.split("\n")
    html_lines = []
    in_table = False
    table_buf = []
    in_ul = False
    ul_buf = []
    in_ol = False
    ol_buf = []

    # 경로 구분자를 / 로 통일
    img_prefix = img_base.replace("\\", "/") if img_base else ""

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
        items = "".join(
            f"<li>{inline(re.sub(r'^\s*[-*]\s+', '', l))}</li>"
            for l in buf
        )
        return f"<ul>{items}</ul>"

    def flush_ol(buf):
        items = "".join(
            f"<li>{inline(re.sub(r'^\s*\d+\.\s+', '', l))}</li>"
            for l in buf
        )
        return f"<ol>{items}</ol>"

    for line in lines:
        # 이미지 — 버퍼 중단 후 <figure> 출력
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)\s*$", line.strip())
        if m:
            if in_table: html_lines.append(flush_table(table_buf)); table_buf = []; in_table = False
            if in_ul:    html_lines.append(flush_ul(ul_buf));    ul_buf = [];    in_ul = False
            alt, src = m.group(1), m.group(2)
            if img_prefix:
                src = src.replace("./images/", img_prefix + "/")
            html_lines.append(
                f'<figure><img src="{src}" alt="{alt}"><figcaption>{alt}</figcaption></figure>'
            )
            continue

        # 표 행
        if re.match(r"^\s*\|", line):
            if in_ul: html_lines.append(flush_ul(ul_buf)); ul_buf = []; in_ul = False
            if in_ol: html_lines.append(flush_ol(ol_buf)); ol_buf = []; in_ol = False
            in_table = True
            table_buf.append(line)
            continue
        if in_table:
            html_lines.append(flush_table(table_buf)); table_buf = []; in_table = False

        # 순서 없는 리스트
        if re.match(r"^\s*[-*]\s+", line):
            if in_ol: html_lines.append(flush_ol(ol_buf)); ol_buf = []; in_ol = False
            if not in_ul:
                in_ul = True; ul_buf = []
            ul_buf.append(line)
            continue
        if in_ul:
            html_lines.append(flush_ul(ul_buf)); ul_buf = []; in_ul = False

        # 순서 있는 리스트 (1. 2. 3. ...)
        if re.match(r"^\s*\d+\.\s+", line):
            if not in_ol:
                in_ol = True; ol_buf = []
            ol_buf.append(line)
            continue
        if in_ol:
            html_lines.append(flush_ol(ol_buf)); ol_buf = []; in_ol = False

        # 수평선
        if re.match(r"^-{3,}$", line.strip()):
            html_lines.append("<hr>")
            continue

        # 제목 · blockquote · 빈 줄 · 문단
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

    # 파일 끝에 미처 닫히지 않은 버퍼 처리
    if in_table: html_lines.append(flush_table(table_buf))
    if in_ul:    html_lines.append(flush_ul(ul_buf))
    if in_ol:    html_lines.append(flush_ol(ol_buf))

    return "\n".join(html_lines)
