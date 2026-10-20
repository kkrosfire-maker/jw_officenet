"""
연세예스내과 신규 프레임 시스템(Template A/B) 본문 이미지 렌더링 — guide/image-guide-yonsei.md 참고.

사용법:
    python scripts/render_body_yonsei.py [주제]

입력:
    output/[yymmdd_주제]/variants.json   ← image-maker 에이전트가 draft.md를 분석해 작성

출력:
    output/[yymmdd_주제]/images/body-{n}.png

variants.json 스키마:
{
  "corner_label_text": "포스팅 시리즈 문구 (병원명 제외)",
  "variants": [
    {
      "frame": "fraim1.png",           // fraim1/2/3.png 중 하나, 순환 배정
      "template": "B",                  // "A"(리스트형) | "B"(본문형)
      "seq": 1,                         // 코너 라벨 원형 순번 (이미지 순서, 프레임 순환과 무관)
      "title": "제목<br>두 줄이면 br로 직접 줄바꿈",
      "body_html": "Template B 전용 — 문단 HTML (<strong> 등 인라인 태그 허용)",
      "items": ["Template A 전용 — 리스트 항목 문자열 배열"],
      "illustration_desc": "한글 장면 설명 (프레임 전용 미리보기의 placeholder 문구로도 쓰임)",
      "illustration_file": null          // null이면 placeholder, 파일명(문자열)이면 실제 합성
    }
  ]
}
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

TMP_DIR = os.path.dirname(os.path.abspath(__file__))

COMMON_CSS = f"""
* {{ margin:0; padding:0; box-sizing:border-box; font-family:{cfg.YONSEI_BODY_FONT_STACK}; }}
.title {{ font-size:{cfg.YONSEI_TITLE_PX}px; font-weight:bold; color:#1A2340; line-height:1.25;
          font-family:{cfg.YONSEI_TITLE_FONT_STACK}; text-align:center; }}
.para {{ font-size:{cfg.YONSEI_BODY_PX}px; font-weight:400; color:#333; line-height:1.65; text-align:center; }}
.para strong {{ color:#1A2340; }}

.list {{ list-style:none; display:flex; flex-direction:column; }}
.list li {{ font-size:{cfg.YONSEI_BODY_PX}px; color:#333; line-height:1.4; word-break:keep-all; overflow-wrap:normal; }}
.list .num {{ font-family:{cfg.YONSEI_TITLE_FONT_STACK}; font-weight:800; margin-right:18px; flex-shrink:0; }}
"""


def render_png(page, html, w, h, transparent=False):
    tmp_path = os.path.join(TMP_DIR, "_tmp_stage_yonsei.html")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(html)
    page.set_viewport_size({"width": w, "height": h})
    page.goto("file:///" + tmp_path.replace("\\", "/"))
    page.wait_for_load_state("networkidle")
    png_path = os.path.join(TMP_DIR, "_tmp_stage_yonsei.png")
    page.screenshot(path=png_path, full_page=False, omit_background=transparent)
    os.unlink(tmp_path)
    return Image.open(png_path).convert("RGBA" if transparent else "RGB")


def measure_height(page, html, w):
    tmp_path = os.path.join(TMP_DIR, "_tmp_measure_yonsei.html")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(html)
    page.set_viewport_size({"width": w, "height": 100})
    page.goto("file:///" + tmp_path.replace("\\", "/"))
    page.wait_for_load_state("networkidle")
    height = page.evaluate("document.querySelector('#m').scrollHeight")
    os.unlink(tmp_path)
    return height


def title_html_block(title, w):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{COMMON_CSS}
html,body{{width:{w}px;background:transparent;}}
#m{{width:{w}px;}}
</style></head><body><div id="m" class="title">{title}</div></body></html>"""


def render_title(page, title, w):
    """제목을 전체 폭 기준 정중앙 정렬로 렌더링. 실제 필요한 높이만큼만 캡처한다."""
    measure_doc = title_html_block(title, w)
    th = measure_height(page, measure_doc, w)
    img = render_png(page, measure_doc, w, th, transparent=True)
    return img, th


def draw_corner_label(frame, seq, corner_label_text):
    draw = ImageDraw.Draw(frame, "RGBA")
    font = ImageFont.truetype(cfg.YONSEI_FONT_SEMIBOLD, cfg.YONSEI_LABEL_FONT_PX)
    circle_font = ImageFont.truetype(cfg.YONSEI_FONT_SEMIBOLD, cfg.YONSEI_LABEL_CIRCLE_FONT_PX)
    label_color = cfg.YONSEI_LABEL_COLOR
    circle_d = cfg.YONSEI_LABEL_CIRCLE_D
    cy = cfg.YONSEI_LABEL_CY

    circle_cx = cfg.YONSEI_CARD_RIGHT - cfg.YONSEI_LABEL_RIGHT_MARGIN - circle_d // 2
    draw.ellipse((circle_cx - circle_d // 2, cy - circle_d // 2,
                  circle_cx + circle_d // 2, cy + circle_d // 2), outline=label_color, width=4)
    plain_num = str(seq)
    nb = draw.textbbox((0, 0), plain_num, font=circle_font)
    nw, nh = nb[2] - nb[0], nb[3] - nb[1]
    draw.text((circle_cx - nw / 2 - nb[0], cy - nh / 2 - nb[1] - 2), plain_num,
               font=circle_font, fill=label_color)
    text_right = circle_cx - circle_d // 2 - cfg.YONSEI_LABEL_GAP
    tb = draw.textbbox((0, 0), corner_label_text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    draw.text((text_right - tw, cy - th / 2 - tb[1]), corner_label_text,
               font=font, fill=label_color)


def draw_illust_placeholder(frame, box, desc):
    import textwrap
    left, top, right, bottom = box
    draw = ImageDraw.Draw(frame)
    draw.rounded_rectangle(box, radius=24, outline=(201, 205, 210), width=4)
    font_desc = ImageFont.truetype(cfg.YONSEI_FONT_SEMIBOLD, 32)
    wrapped = textwrap.fill(desc, width=14)
    draw.multiline_text((left + 40, top + 40), wrapped, font=font_desc,
                         fill=(154, 160, 166), spacing=10)


def composite_illustration(frame, box, illust_path):
    left, top, right, bottom = box
    box_w, box_h = right - left, bottom - top
    illust_img = Image.open(illust_path).convert("RGBA")
    iw, ih = illust_img.size
    scale = min(box_w / iw, box_h / ih)
    new_w, new_h = int(iw * scale), int(ih * scale)
    illust_resized = illust_img.resize((new_w, new_h), Image.LANCZOS)
    paste_x = left + (box_w - new_w) // 2
    paste_y = top + box_h - new_h  # 바닥 정렬 (인물 발이 카드 하단 쪽)
    frame.alpha_composite(illust_resized, (paste_x, paste_y))


def render_topic(topic):
    topic_dir = cfg.topic_dir(topic)
    out_dir = os.path.join(topic_dir, "images")
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(topic_dir, "variants.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
    corner_label_text = data["corner_label_text"]
    variants = data["variants"]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        template_a_seen = 0
        for i, v in enumerate(variants, start=1):
            frame = Image.open(os.path.join(cfg.YONSEI_BASE, v["frame"])).convert("RGBA")

            title_img, title_h = render_title(page, v["title"], cfg.YONSEI_FULL_W)
            frame.alpha_composite(title_img, (cfg.YONSEI_TEXT_LEFT, cfg.YONSEI_CONTENT_TOP))
            body_top = cfg.YONSEI_CONTENT_TOP + title_h + cfg.YONSEI_TITLE_GAP

            illust_file = v.get("illustration_file")
            illust_path = os.path.join(topic_dir, illust_file) if illust_file else None

            if v["template"] == "B":
                avail_h = cfg.YONSEI_CONTENT_BOTTOM - body_top

                def build_B(img_w, img_h, w):
                    if img_h <= 0:
                        ph = ""
                    elif illust_path:
                        ph = (f'<img src="file:///{illust_path.replace(chr(92), "/")}" '
                              f'style="width:{img_w}px;height:{img_h}px;object-fit:contain;">')
                    else:
                        ph = (f'<div style="width:{img_w}px;height:{img_h}px;'
                              'border:4px dashed #C9CDD2;border-radius:24px;display:flex;'
                              'align-items:center;justify-content:center;color:#9AA0A6;'
                              f'font-size:36px;text-align:center;padding:20px;">{v["illustration_desc"]}</div>')
                    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
{COMMON_CSS}
html,body{{width:{w}px;background:#ffffff;}}
#m{{width:{w}px;display:flex;flex-direction:column;align-items:center;}}
#img-wrap{{flex:0 0 auto;margin-bottom:40px;}}
#para-wrap{{width:100%;}}
</style></head><body><div id="m">
<div id="img-wrap">{ph}</div>
<div id="para-wrap" class="para">{v["body_html"]}</div>
</div></body></html>"""

                base_html = build_B(0, 0, cfg.YONSEI_FULL_W)
                non_image_h = measure_height(page, base_html, cfg.YONSEI_FULL_W)
                img_h = max(280, min(950, avail_h - non_image_h - 10))
                img_w = int(img_h * 0.95)

                final_html = build_B(img_w, img_h, cfg.YONSEI_FULL_W)
                body_img = render_png(page, final_html, cfg.YONSEI_FULL_W, avail_h, transparent=False).convert("RGBA")
                frame.alpha_composite(body_img, (cfg.YONSEI_TEXT_LEFT, body_top))
            else:
                template_a_seen += 1
                side = "right" if template_a_seen % 2 == 1 else "left"  # 이미지 순서로 좌우 자동 교대

                illust_h = min(cfg.YONSEI_ILLUST_H_MAX, cfg.YONSEI_CONTENT_BOTTOM - body_top - 20)
                right_col_right = cfg.YONSEI_CARD_RIGHT - cfg.YONSEI_RIGHT_MARGIN
                text_w = (right_col_right - cfg.YONSEI_LIST_LEFT) - cfg.YONSEI_GAP_COL - cfg.YONSEI_ILLUST_W

                if side == "right":
                    illust_left = right_col_right - cfg.YONSEI_ILLUST_W
                    text_x = cfg.YONSEI_LIST_LEFT
                else:
                    illust_left = cfg.YONSEI_LIST_LEFT
                    text_x = right_col_right - text_w

                # 리스트/일러스트 모두 body_top~CONTENT_BOTTOM(로고 상단) 구간의 중앙에 세로로 정렬
                center_y = (body_top + cfg.YONSEI_CONTENT_BOTTOM) / 2

                accent = cfg.YONSEI_TAB_COLOR[v["frame"]]
                items_html = "".join(
                    f'<li style="display:flex;"><span class="num" style="color:{accent}">{idx+1}.</span>'
                    f'<span style="min-width:0;">{item}</span></li>'
                    for idx, item in enumerate(v["items"])
                )
                gap = 46 if len(v["items"]) <= 5 else 30
                list_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
{COMMON_CSS}
html,body{{width:{text_w}px;background:transparent;}}
#m{{width:{text_w}px;}}
.list{{gap:{gap}px;}}
</style></head><body><div id="m"><ul class="list">{items_html}</ul></div></body></html>"""
                actual_list_h = measure_height(page, list_html, text_w)
                list_top = int(center_y - actual_list_h / 2)
                list_top = max(body_top, min(list_top, cfg.YONSEI_CONTENT_BOTTOM - actual_list_h))
                list_img = render_png(page, list_html, text_w, actual_list_h, transparent=True)
                frame.alpha_composite(list_img, (text_x, list_top))

                illust_top = int(center_y - illust_h / 2)
                illust_top = max(body_top, min(illust_top, cfg.YONSEI_CONTENT_BOTTOM - illust_h))
                box = (illust_left, illust_top, illust_left + cfg.YONSEI_ILLUST_W, illust_top + illust_h)
                if illust_path:
                    composite_illustration(frame, box, illust_path)
                else:
                    draw_illust_placeholder(frame, box, v["illustration_desc"])

            draw_corner_label(frame, v["seq"], corner_label_text)

            out_path = os.path.join(out_dir, f"body-{i}.png")
            frame.convert("RGB").save(out_path, "PNG")
            print(f"Saved {out_path}  template={v['template']}  illust={'real' if illust_path else 'placeholder'}")

        browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python render_body_yonsei.py [주제]")
        sys.exit(1)
    render_topic(sys.argv[1])
