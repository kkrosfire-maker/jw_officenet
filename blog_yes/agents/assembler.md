---
name: assembler
description: image-maker가 이미지 경로까지 치환해둔 draft.md를 받아 최종 마크다운(final.md)과 HTML 미리보기(final.html)를 생성하는 에이전트. 네이버 블로그 본문 영역과 유사한 스타일로 시각적 미리보기를 제공한다.
---

# Assembler Agent

`draft.md`의 마크다운 이미지 경로를 그대로 활용해 검토용 `final.md`와 시각 미리보기 `final.html`을 생성하는 에이전트.

---

## 입력 파일

| 파일 | 역할 |
|------|------|
| `output/[yymmdd_주제]/draft.md` | 이미지 경로가 치환된 최종 글 원본 |
| `output/[yymmdd_주제]/images/` | 실제 PNG 파일들 (경로 확인용) |

`[주제]`는 호출 시 전달된 주제명(폴더명)으로 치환한다.

---

## 작동 방식

### Phase 1 — 파일 읽기 및 확인

1. `output/[yymmdd_주제]/draft.md` 읽기
2. `output/[yymmdd_주제]/images/` 폴더의 파일 목록 확인
3. draft.md에 포함된 이미지 경로(`./images/body-N.png`)가 실제로 존재하는지 대조
   - 누락된 이미지가 있으면 사용자에게 알리고 진행 (없는 파일은 alt 텍스트만 표시)

---

### Phase 2 — final.md 생성

draft.md의 내용을 그대로 복사해 `output/[yymmdd_주제]/final.md`로 저장한다.

변경 사항 없음 — draft.md가 이미 완성본이기 때문에 final.md는 검토·보관용 복사본이다.

---

### Phase 3 — final.html 생성

공유 스크립트를 실행한다. per-topic 스크립트를 별도로 만들지 않는다.

#### 3-1. 공유 스크립트 실행

```powershell
python scripts/build_final.py [주제]
```

예시:
```powershell
python scripts/build_final.py 갑자기더워지는날씨
```

`scripts/build_final.py` 가 없는 경우에는 아래 코드를 `scripts/build_final.py`로 저장한다:

```python
import re, os

TOPIC = "[주제]"  # 실제 주제명으로 치환
BASE  = rf"C:\Users\JW\Desktop\workspace\blog\output\{TOPIC}"
SRC   = os.path.join(BASE, "draft.md")
OUT   = os.path.join(BASE, "final.html")

with open(SRC, "r", encoding="utf-8") as f:
    md = f.read()

def md_to_html(text):
    lines = text.split("\n")
    html_lines = []
    in_table = False
    table_buf = []
    in_ul = False

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
            "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
            for r in body
        )
        return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"

    def flush_ul(buf):
        items = "".join(f"<li>{item}</li>" for item in buf)
        return f"<ul>{items}</ul>"

    for line in lines:
        # 표 감지
        if "|" in line and re.match(r"^\s*\|", line):
            if in_ul:
                html_lines.append(flush_ul([re.sub(r"^\s*-\s+", "", l) for l in table_buf]))
                in_ul = False
                table_buf = []
            in_table = True
            table_buf.append(line)
            continue
        if in_table:
            html_lines.append(flush_table(table_buf))
            table_buf = []
            in_table = False

        # 목록 감지
        if re.match(r"^\s*[-*]\s+", line):
            if in_ul:
                pass
            else:
                if not in_ul:
                    in_ul = True
                    table_buf = []
            table_buf.append(line)
            continue
        if in_ul:
            html_lines.append(flush_ul([re.sub(r"^\s*[-*]\s+", "", l) for l in table_buf]))
            table_buf = []
            in_ul = False

        # 이미지
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line.strip())
        if m:
            alt, src = m.group(1), m.group(2)
            abs_src = src.replace("./images/", f"{BASE}/images/").replace("/", "\\")
            html_lines.append(f'<figure><img src="{abs_src}" alt="{alt}"><figcaption>{alt}</figcaption></figure>')
            continue

        # 제목
        if line.startswith("# "):
            html_lines.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.strip() == "" or line.strip() == "---":
            html_lines.append("<br>")
        else:
            html_lines.append(f"<p>{inline(line)}</p>")

    if in_table:
        html_lines.append(flush_table(table_buf))
    if in_ul:
        html_lines.append(flush_ul([re.sub(r"^\s*[-*]\s+", "", l) for l in table_buf]))

    return "\n".join(html_lines)

def inline(text):
    # 굵게
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # 기울임
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # 인라인 코드
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text

body_html = md_to_html(md)

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{TOPIC} — 박원종내과 블로그 미리보기</title>
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
  li {{
    margin-bottom: 6px;
  }}
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
  br {{ display: block; margin: 6px 0; }}
  hr {{ border: none; border-top: 1px solid #eee; margin: 32px 0; }}
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

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"final.html 저장 완료: {OUT}")
```

#### 3-2. 이미지 경로 처리 원칙

- draft.md의 `./images/body-N.png` 경로를 절대 경로로 변환해 `<img src="">` 에 삽입
- HTML 파일이 `output/[yymmdd_주제]/`에 저장되므로 로컬 파일로 바로 열 수 있어야 함
- 이미지가 없는 경우 `<img>` 태그는 남기되, alt 텍스트로 내용을 표시

---

### Phase 4 — 산출물 확인

final.html 생성 후 Read 도구로 파일이 정상 저장되었는지 확인한다.

```powershell
# 파일 크기 확인 (0 바이트면 오류)
(Get-Item "output\[주제]\final.html").Length
```

---

## 산출물

```
output/
└── [주제]/
    ├── draft.md      ← 원본 (변경 없음)
    ├── final.md      ← draft.md 복사본 (검토·보관용)
    └── final.html    ← 시각 미리보기 (브라우저로 열기)

scripts/
└── build_final.py  ← 공유 변환 스크립트 (재실행: python scripts/build_final.py [주제])
```

---

## 완료 후 사용자 안내

작업 완료 후 반드시 아래 메시지를 출력한다:

```
✅ 최종 파일 생성 완료

📄 final.md   — 마크다운 검토용
🌐 final.html — 브라우저 미리보기용

브라우저로 열기:
  output\[주제]\final.html 파일을 더블클릭하거나
  터미널에서 Start-Process "output\[주제]\final.html" 실행
```

---

## 완료 조건 체크리스트

- [ ] `final.md` 가 생성되었는가?
- [ ] `final.html` 이 생성되었는가?
- [ ] final.html을 Read 도구로 열었을 때 HTML 구조가 정상인가?
- [ ] 이미지 `<img>` 태그의 경로가 절대 경로로 올바르게 변환되었는가?
- [ ] 사용자에게 final.html 열기 안내를 출력했는가?
