"""
썸네일 생성기 — 1.png 베이스에서 제목 텍스트만 교체

사용법:
  python scripts/make_thumbnail.py <주제폴더명> <줄1> [줄2] [줄3]

예시:
  python scripts/make_thumbnail.py 여름철식중독 "여름철 식중독" "원인·증상·예방"
  python scripts/make_thumbnail.py 갑자기더워지는날씨 "갑자기 더워지는" "날씨 건강" "주의사항 5가지"
"""
import sys
import os
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
from config import (  # noqa: E402
    topic_dir,
    THUMB_REF_IMAGE as REF_IMAGE,
    THUMB_COVER as COVER,
    TEXT_COLOR, RIGHT_EDGE, LINE_Y_START, LINE_SPACING,
    FONT_PATHS,
)


def find_font():
    for path in FONT_PATHS:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("한글 폰트를 찾을 수 없습니다.")


def best_font_size(draw, lines, font_path, max_width=545, start=95):
    for size in range(start, 50, -2):
        font = ImageFont.truetype(font_path, size)
        if all((draw.textbbox((0, 0), l, font=font)[2] - draw.textbbox((0, 0), l, font=font)[0]) <= max_width
               for l in lines):
            return font
    return ImageFont.truetype(font_path, 52)


def make_thumbnail(topic: str, title_lines: list[str]):
    if not os.path.exists(REF_IMAGE):
        print(f"ERROR: 썸네일 참조 이미지가 없습니다 — {REF_IMAGE}")
        sys.exit(1)

    out_path = os.path.join(topic_dir(topic), "images", "thumbnail.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    img = Image.open(REF_IMAGE).convert("RGBA")
    draw = ImageDraw.Draw(img)

    draw.rectangle(list(COVER), fill=(255, 255, 255, 255))

    font_path = find_font()
    font = best_font_size(draw, title_lines, font_path)

    y = LINE_Y_START
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = RIGHT_EDGE - (bbox[2] - bbox[0])
        draw.text((x, y), line, fill=TEXT_COLOR, font=font)
        print(f"  '{line}': x={x}, y={y}")
        y += LINE_SPACING

    img.convert("RGB").save(out_path, "PNG")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    topic = sys.argv[1]
    lines = sys.argv[2:]
    make_thumbnail(topic, lines)
