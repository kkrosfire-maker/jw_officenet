"""
연세예스내과 신규 프레임 시스템 — 썸네일(thumb nail.png) 렌더링. guide/image-guide-yonsei.md §5 참고.

사용법:
    python scripts/make_thumbnail_yonsei.py [주제]

입력:
    output/[yymmdd_주제]/thumbnail.json   ← image-maker 에이전트가 작성

thumbnail.json 스키마:
{
  "title_lines": ["축약 제목 1줄" ] 또는 ["1줄", "2줄"],   // §5-1: 반드시 사용자 확인받은 문구
  "illustration_file": null   // null이면 카드 정중앙에 placeholder, 파일명이면 실제 이미지 합성
}

출력:
    output/[yymmdd_주제]/images/thumbnail.png
"""
import json
import os
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg


def best_font_size(draw, lines, font_path, max_width, start=110):
    for size in range(start, 40, -2):
        font = ImageFont.truetype(font_path, size)
        widths = [draw.textbbox((0, 0), l, font=font)[2] - draw.textbbox((0, 0), l, font=font)[0] for l in lines]
        if all(w <= max_width for w in widths):
            return font
    return ImageFont.truetype(font_path, 44)


def composite_illustration(thumb, box, illust_path):
    left, top, right, bottom = box
    box_w, box_h = right - left, bottom - top
    illust_img = Image.open(illust_path).convert("RGBA")
    iw, ih = illust_img.size
    scale = min(box_w / iw, box_h / ih)
    new_w, new_h = int(iw * scale), int(ih * scale)
    illust_resized = illust_img.resize((new_w, new_h), Image.LANCZOS)
    paste_x = left + (box_w - new_w) // 2
    paste_y = top + (box_h - new_h) // 2   # 썸네일은 상단 2/3 공간에서 정중앙 배치 (본문과 달리 바닥 정렬 아님)
    thumb.alpha_composite(illust_resized, (paste_x, paste_y))


def draw_placeholder(thumb, box, desc):
    draw = ImageDraw.Draw(thumb)
    draw.rounded_rectangle(box, radius=24, outline=(201, 205, 210), width=4)
    font_desc = ImageFont.truetype(cfg.YONSEI_FONT_SEMIBOLD, 28)
    wrapped = textwrap.fill(desc or "일러스트 자리", width=16)
    left, top, right, bottom = box
    draw.multiline_text((left + 30, top + 30), wrapped, font=font_desc,
                         fill=(154, 160, 166), spacing=8)


def render_thumbnail(topic):
    topic_dir = cfg.topic_dir(topic)
    out_dir = os.path.join(topic_dir, "images")
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(topic_dir, "thumbnail.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
    title_lines = data["title_lines"]
    illust_file = data.get("illustration_file")
    illust_desc = data.get("illustration_desc", "")

    thumb_path = os.path.join(cfg.YONSEI_BASE, cfg.YONSEI_THUMB_FILE)
    thumb = Image.open(thumb_path).convert("RGBA")

    if illust_file:
        composite_illustration(thumb, cfg.YONSEI_THUMB_IMAGE_BOX, os.path.join(topic_dir, illust_file))
    else:
        draw_placeholder(thumb, cfg.YONSEI_THUMB_IMAGE_BOX, illust_desc)

    draw = ImageDraw.Draw(thumb)
    font = best_font_size(draw, title_lines, cfg.YONSEI_FONT_EXTRABOLD, cfg.YONSEI_THUMB_MAX_WIDTH)
    y = cfg.YONSEI_THUMB_LINE_Y_START
    for line in title_lines:
        bb = draw.textbbox((0, 0), line, font=font)
        tw = bb[2] - bb[0]
        x = cfg.YONSEI_THUMB_CARD_CENTER_X - tw // 2
        draw.text((x, y), line, fill=cfg.YONSEI_THUMB_TEXT_COLOR, font=font)
        y += cfg.YONSEI_THUMB_LINE_SPACING

    out_path = os.path.join(out_dir, "thumbnail.png")
    thumb.convert("RGB").save(out_path, "PNG")
    print(f"Saved {out_path}  illust={'real' if illust_file else 'placeholder'}  font_size={font.size}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python make_thumbnail_yonsei.py [주제]")
        sys.exit(1)
    render_thumbnail(sys.argv[1])
