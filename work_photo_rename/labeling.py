"""사진 처리 순수 로직: 가로 2500px 리사이즈 + 빨간 박스 + 하단 문구 띠 + JPG 저장.

문구 규격(샘플 '365제이에스JS연합의원 10월 이든파마.png' 실측, 가로 2498px 기준):
- 하단 흰 띠 높이 ≈ 244px (가로의 약 9.8%), 글자 굵게(Bold), 검정, 가로 중앙 정렬, 띠 안 세로 중앙
- 글자 높이 ≈ 89px → Noto Sans KR Bold 약 94px (가로 2500px 기준)
"""
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from annotate import rect_corners
from names import clean_pharma   # noqa: F401  (끝 번호 제거 규칙은 names 모듈)

TARGET_W = 2500
BAND_H = 245
FONT_SIZE = 94
MAX_TEXT_RATIO = 0.94          # 문구가 너무 길면 가로의 이 비율까지만 쓰도록 글자를 줄인다
JPG_QUALITY = 95

_FONTS = [
    ("C:/Windows/Fonts/NotoSansKR-VF.ttf", True),   # 가변폰트 → 700(Bold) 축 지정
    ("C:/Windows/Fonts/malgunbd.ttf", False),
]


def load_font(size: int):
    for path, variable in _FONTS:
        if Path(path).exists():
            f = ImageFont.truetype(path, size)
            if variable:
                try:
                    f.set_variation_by_axes([700])
                except Exception:
                    pass
            return f
    return ImageFont.load_default()


def build_label(hospital: str, month: str, pharma: str) -> str:
    return f"{hospital.strip()} {month.strip()} {pharma.strip()}"


def resize_to_width(img, width=TARGET_W):
    h, w = img.shape[:2]
    if w == width:
        return img.copy(), 1.0
    s = width / w
    interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
    return cv2.resize(img, (width, max(1, round(h * s))), interpolation=interp), s


def draw_boxes(img, rects, scale=1.0, color=(0, 0, 255)):
    """rects는 원본 이미지 좌표. scale을 곱해 리사이즈된 이미지 위에 그린다.
    두께는 2500px 기준값(사용자가 보는 값)을 그대로 쓴다."""
    out = img
    for r in rects:
        pts = np.array([(x * scale, y * scale) for x, y in rect_corners(r)], dtype=np.int32)
        cv2.polylines(out, [pts], True, color, max(1, int(r.get("thickness", 4))), cv2.LINE_AA)
    return out


def add_label_band(img, text):
    h, w = img.shape[:2]
    size = FONT_SIZE
    font = load_font(size)
    while size > 20:
        box = font.getbbox(text)
        if box[2] - box[0] <= w * MAX_TEXT_RATIO:
            break
        size -= 2
        font = load_font(size)
    box = font.getbbox(text)
    tw, th = box[2] - box[0], box[3] - box[1]

    canvas = Image.new("RGB", (w, h + BAND_H), (255, 255, 255))
    canvas.paste(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), (0, 0))
    ImageDraw.Draw(canvas).text(((w - tw) // 2 - box[0], h + (BAND_H - th) // 2 - box[1]),
                                text, font=font, fill=(0, 0, 0))
    return cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR)


def add_center_stamp(img, text, size=FONT_SIZE * 2, color=(255, 0, 0)):
    """사진 한가운데에 빨간 글씨를 찍는다 (기본 크기 = 하단 문구의 2배). color는 RGB."""
    h, w = img.shape[:2]
    font = load_font(size)
    box = font.getbbox(text)
    tw, th = box[2] - box[0], box[3] - box[1]
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    ImageDraw.Draw(pil).text(((w - tw) // 2 - box[0], (h - th) // 2 - box[1]), text, font=font, fill=color)
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def render(img, text, rects=None, stamp=None):
    """원본 BGR 이미지 → 최종 결과(가로 2500px, 박스 + 가운데 도장(선택) + 문구 띠)."""
    out, s = resize_to_width(img)
    if rects:
        draw_boxes(out, rects, s)
    if stamp:
        out = add_center_stamp(out, stamp)
    return add_label_band(out, text)


def save_jpg(img, path) -> bool:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPG_QUALITY])
    if ok:
        buf.tofile(str(path))
    return bool(ok)


_FORBIDDEN = re.compile(r'[\\/:*?"<>|]')


def safe_filename(text: str) -> str:
    return _FORBIDDEN.sub("", text).strip()


def numbered_path(directory, stem: str, suffix: str = ".jpg"):
    """같은 이름이 있으면 맨 뒤에 ' 2', ' 3', ' 4' ... 를 붙인 경로를 돌려준다."""
    p = Path(directory) / (stem + suffix)
    n = 2
    while p.exists():
        p = Path(directory) / f"{stem} {n}{suffix}"
        n += 1
    return p
