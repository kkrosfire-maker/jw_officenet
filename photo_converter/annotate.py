"""2단계: 하단 텍스트 라벨 삽입 + 빨간 사각 테두리 표시."""
import math
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# auto_photochanger 프로젝트와 동일한 파일명 관례: "병원명 mm월 제약사명.ext"
FILENAME_PATTERN = re.compile(r"^(?P<hospital>.+?)\s+(?P<month>\d{1,2}월)\s+(?P<pharma>.+)$")

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
]


def _load_font(size: int):
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def parse_filename(path):
    """
    '병원명 mm월 제약사명.ext' 형식의 파일명에서 필드를 추출.
    형식이 맞지 않으면 None 반환 (호출자가 수동 입력으로 폴백).
    """
    stem = Path(path).stem
    m = FILENAME_PATTERN.match(stem)
    if not m:
        return None
    return {
        "hospital": m.group("hospital").strip(),
        "month": m.group("month").strip(),
        "pharma": m.group("pharma").strip(),
    }


def build_label(hospital: str, month: str, pharma: str) -> str:
    return f"{hospital} {month} {pharma}"


def rect_corners(r):
    """
    rect: {"cx","cy","hw","hh","angle"} (중심점, 반너비/반높이, 회전각 — 도 단위, 시계방향).
    회전 반영한 4개 꼭짓점을 TL, TR, BR, BL 순서로 반환 (이미지 좌표).
    """
    cx, cy, hw, hh = r["cx"], r["cy"], r["hw"], r["hh"]
    a = math.radians(r.get("angle", 0.0))
    cos_a, sin_a = math.cos(a), math.sin(a)
    local = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    return [(cx + lx * cos_a - ly * sin_a, cy + lx * sin_a + ly * cos_a) for lx, ly in local]


def draw_rects(image, rects, color=(0, 0, 255)):
    """
    rects: [{"cx","cy","hw","hh","angle","thickness"}, ...] (이미지 좌표, 픽셀)
    하나 이상의 빨간 사각 테두리(실선, 회전 가능)를 그린 복사본 반환.
    """
    out = image.copy()
    for r in rects:
        pts = np.array(rect_corners(r), dtype=np.int32)
        thickness = max(1, int(r.get("thickness", 4)))
        cv2.polylines(out, [pts], isClosed=True, color=color, thickness=thickness)
    return out


def draw_label(image, text, fg=(0, 0, 0), bg=(255, 255, 255), pad_ratio=0.4):
    """
    이미지 하단에 라벨 밴드를 추가한 복사본 반환.
    사진 위에 겹쳐 그리는 대신 캔버스를 아래로 늘려서, 텍스트가 사진 내용을
    가리지 않게 한다.
    """
    h, w = image.shape[:2]
    font_size = max(16, int(min(h, w) * 0.045))
    font = _load_font(font_size)

    pad = int(font_size * pad_ratio)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    base = Image.fromarray(rgb)
    probe = ImageDraw.Draw(base)
    bbox = probe.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    band_h = text_h + pad * 2
    canvas = Image.new("RGB", (w, h + band_h), bg)
    canvas.paste(base, (0, 0))
    draw = ImageDraw.Draw(canvas)
    tx = max(0, (w - text_w) // 2 - bbox[0])
    ty = h + pad - bbox[1]
    draw.text((tx, ty), text, font=font, fill=fg)

    return cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR)


def annotate_image(image, label_text, rects=None):
    """
    하나 이상의 빨간 테두리(옵션) + 하단 라벨 밴드를 적용한 결과 반환.
    rects: draw_rects 참고. None/빈 리스트면 테두리 생략.
    """
    out = image.copy()
    if rects:
        out = draw_rects(out, rects)
    return draw_label(out, label_text)
