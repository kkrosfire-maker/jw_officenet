"""마감표 이미지의 제목 글자를 바꿔 다시 그린다 — '지에스파마' → '정원유니어스(주)'.

원본 이미지(엑셀 화면 캡처)는 그대로 두고, 맨 위 제목 칸의 글자만 지운 뒤 같은 크기·위치(가운데 정렬)로 새 제목을 쓴다.
원본 제목의 글자 높이에 맞춰 글꼴 크기를 정하므로(맑은 고딕 굵게), 다른 해상도의 이미지도 비슷하게 나온다.
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import deadline_ocr

OLD = "지에스파마"
NEW = "정원유니어스(주)"
_FONTS = [r"C:\Windows\Fonts\malgunbd.ttf", r"C:\Windows\Fonts\NanumGothicBold.ttf", r"C:\Windows\Fonts\malgun.ttf"]


def _font(size):
    for f in _FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    raise OSError("맑은 고딕 글꼴을 찾지 못했습니다")


def title_text(year, month, who):
    return f"{year}년 {month}월 {who} 제약사 통계 마감일정"


def render(path, year, month, new=NEW, old=OLD):
    """이미지 파일 → 제목을 바꾼 PIL 이미지(RGB). 제목 칸을 못 찾으면 ValueError."""
    bgr = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("이미지를 열 수 없습니다")
    tb = deadline_ocr.title_box(bgr)
    if tb is None:
        raise ValueError("제목 줄을 찾지 못했습니다")
    im = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(im)
    x0, y0, x1, y1 = tb["x0"], tb["y0"], tb["x1"], tb["y1"]
    bg = (tb["bg"][2], tb["bg"][1], tb["bg"][0])

    old_text = title_text(year, month, old)                 # 원본 제목 글자 높이에 맞는 글꼴 크기를 찾는다
    want_h = y1 - y0
    size = max(10, round(want_h * 0.9))
    best = None
    for s in range(max(8, size - 12), size + 13):
        b = _font(s).getbbox(old_text)
        err = abs((b[3] - b[1]) - want_h)
        if best is None or err < best[0]:
            best = (err, s, b[1])
    _, size, top_off = best

    pad = 5                                                  # 글자 가장자리 찌꺼기까지 지운다
    draw.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], fill=bg)
    text = title_text(year, month, new)
    font = _font(size)
    while font.getlength(text) > im.width - 60 and size > 10:    # 너무 길면 줄인다
        size -= 1
        font = _font(size)
    w = font.getlength(text)
    cx = (x0 + x1) / 2
    draw.text((cx - w / 2, y0 - top_off), text, font=font, fill=(0, 0, 0))
    return im
