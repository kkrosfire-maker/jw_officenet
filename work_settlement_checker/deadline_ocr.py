"""마감일정 이미지(월~금 달력표)를 읽어 (날짜, 글자) 목록으로 바꾼다.

표 모양: 맨 위 제목, 요일 줄, 그 아래 [날짜 숫자 줄 + 그날 마감 제약사 줄들] 이 주마다 반복.
격자선 위치로 칸을 나누고 칸 안의 한 줄(약 30px)씩 Tesseract(kor)로 읽는다.
"""
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
TESSDATA_CANDIDATES = [_BASE / "tessdata", _BASE.parent / "work_photo_rename" / "tessdata"]

_TIME = re.compile(r"\(\s*(\d{1,2})\s*시\s*\)")
_AMPM = re.compile(r"\(\s*(오전|오후)[^)]*\)")


@dataclass
class Entry:
    day: int
    text: str            # 읽은 글자 그대로(시각 괄호 포함)
    crop: object = field(default=None, repr=False, compare=False)   # 다시 읽기용 원본 조각

    @property
    def is_notice(self):
        return self.text.lstrip().startswith(("-", "·", "※", "*"))

    @property
    def name(self):
        t = _TIME.sub("", self.text)
        t = _AMPM.sub("", t)
        return t.lstrip("-·※* ").strip()

    @property
    def hour(self):
        m = _TIME.search(self.text)
        if m:
            return int(m.group(1))
        m = _AMPM.search(self.text)
        if m:
            return 12 if m.group(1) == "오전" else 17
        return None


def _tess():
    import pytesseract
    if Path(TESS).exists():
        pytesseract.pytesseract.tesseract_cmd = TESS
    for d in TESSDATA_CANDIDATES:
        if (d / "kor.traineddata").exists():
            os.environ["TESSDATA_PREFIX"] = str(d)
            break
    return pytesseract


def _ocr(pt, gray, digits=False):
    c = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    c = cv2.copyMakeBorder(c, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
    if digits:
        cfg = "--psm 7 -c tessedit_char_whitelist=0123456789"
        return pt.image_to_string(c, lang="eng", config=cfg).strip()
    return pt.image_to_string(c, lang="kor+eng", config="--psm 7").strip()


def _runs(flags, min_len=1):
    out, s = [], None
    for i, f in enumerate(list(flags) + [False]):
        if f and s is None:
            s = i
        elif not f and s is not None:
            if i - s >= min_len:
                out.append((s, i))
            s = None
    return out


def _layout(img):
    """칸 경계(세로선 x 좌표 8개)와 요일·날짜 줄 구간들을 찾는다. 못 찾으면 ValueError."""
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dark = g < 120
    # 세로 격자선(긴 검은 선) → 칸 경계
    xs = [x for x in range(w) if dark[:, x].sum() > h * 0.5]
    xs = [x for i, x in enumerate(xs) if i == 0 or x - xs[i - 1] > 3]
    bounds = [0] + [x for x in xs if 20 < x < w - 20] + [w - 1]
    if len(bounds) != 8:
        raise ValueError(f"요일 칸 7개를 찾지 못했습니다(찾은 경계 {len(bounds)}개)")
    # 날짜 줄·요일 줄: 가운데 월요일 칸이 연한 노란색(채움)인 구간
    px = img[:, bounds[1] + 6].astype(int)          # 글자가 없는 칸 왼쪽 가장자리
    fill = (px[:, 2] > 240) & (abs(px[:, 1] - 242) < 8) & (px[:, 0] < 225) & (px[:, 0] > 180)
    bands = _runs(fill, 20)          # 요일 줄·날짜 줄들은 격자선(검은 선)으로 서로 갈라져 있다
    if len(bands) < 2:
        raise ValueError("날짜 줄을 찾지 못했습니다")
    return g, bounds, bands


def _without_lines(c, frac=0.8):
    """칸 조각에 걸친 긴 세로·가로 선(표 테두리)을 지운다. 글자로 오인하지 않도록."""
    c = c.copy()
    d = c < 140
    c[:, d.mean(axis=0) > frac] = 255
    c[d.mean(axis=1) > frac, :] = 255
    return c


def read_image(path):
    """이미지 → [Entry]. 날짜 줄을 못 찾으면 ValueError."""
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("이미지를 열 수 없습니다")
    h, w = img.shape[:2]
    g, bounds, bands = _layout(img)
    day_rows = bands[1:]
    pt = _tess()
    from concurrent.futures import ThreadPoolExecutor
    jobs = []                        # (day, order, gray)
    for wi, (y0, y1) in enumerate(day_rows):
        end = day_rows[wi + 1][0] if wi + 1 < len(day_rows) else h - 2
        pitch = y1 - y0 + 1
        for ci in range(7):
            cell = g[y0 + 3:y1 - 3, bounds[ci] + 8:bounds[ci + 1] - 8]
            t = _ocr(pt, cell, digits=True)
            if not t.isdigit():
                continue
            for k, y in enumerate(range(y1, end - 4, pitch)):
                c = g[y + 2:y + pitch - 2, bounds[ci] + 4:bounds[ci + 1] - 4]
                if c.size:
                    c = _without_lines(c)               # 표 바깥 굵은 테두리가 일·토 칸 글자로 읽히지 않게
                if c.size and (c < 140).sum() >= 15:
                    jobs.append((int(t), len(jobs), c))
    with ThreadPoolExecutor(6) as ex:
        texts = list(ex.map(lambda j: _ocr(pt, j[2]), jobs))
    return [Entry(j[0], t, j[2]) for j, t in zip(jobs, texts) if t]


def reread_variants(entry):
    """못 알아본 칸을 다른 전처리·읽기 방식으로 다시 읽은 후보 글자들."""
    if entry.crop is None:
        return []
    pt = _tess()
    out = []
    g = entry.crop
    # 한글 전용(kor)을 먼저: kor+eng 는 흐린 한글을 영문 조각으로 읽는 일이 있다(예: '대한뉴팜' → 'eta')
    for lang in ("kor", "kor+eng"):
        for scale in (4, 2, 3):
            c = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            _, b = cv2.threshold(c, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            for img in (c, b):
                img = cv2.copyMakeBorder(img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
                for psm in (7, 8, 13):
                    try:
                        t = pt.image_to_string(img, lang=lang, config=f"--psm {psm}").strip()
                    except Exception:
                        continue
                    t = re.sub(r"^[^가-힣A-Za-z0-9(]+|[^가-힣A-Za-z0-9)]+$", "", t)     # 앞뒤에 붙은 점·잡기호 제거
                    if t:
                        out.append(t)
    return out


_TITLE = re.compile(r"(20\d{2})\s*년\s*(\d{1,2})\s*월")


def title_box(img):
    """제목 글자(표 맨 위 굵은 글씨)의 위치 → dict(x0, y0, x1, y1, bg). 테두리선은 글자로 치지 않는다. 못 찾으면 None.
    bg = 제목 칸 배경색(BGR), 글자를 지울 때 쓴다."""
    try:
        g, _, bands = _layout(img)
    except ValueError:
        return None
    top = bands[0][0]                                   # 요일 줄 시작 = 제목 영역의 끝
    reg = g[: max(top - 2, 1)]
    d = reg < 140
    lines = [int(y) for y in np.where(d.mean(axis=1) > 0.5)[0]]     # 가로 테두리선
    edges = [-1] + lines + [reg.shape[0]]
    y_lo, y_hi = max(zip(edges, edges[1:]), key=lambda p: p[1] - p[0])    # 선과 선 사이 가장 넓은 구간이 제목 칸 안쪽
    y_lo, y_hi = y_lo + 2, y_hi - 2
    if y_hi - y_lo < 12:
        return None
    inner = d[y_lo:y_hi]
    inner[:, inner.mean(axis=0) > 0.8] = False                       # 세로 테두리선
    ys, xs = np.where(inner)
    if len(xs) < 30:
        return None
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()) + y_lo, int(ys.max()) + 1 + y_lo
    mask = np.ones(inner.shape, bool)
    mask[:, max(x0 - 6, 0): x1 + 6] = False
    bg = np.median(img[y_lo:y_hi][mask & ~inner.astype(bool)], axis=0) if mask.any() else np.array([255, 255, 255])
    return dict(x0=x0, y0=y0, x1=x1, y1=y1, bg=tuple(int(v) for v in bg))


def read_title(path):
    """제목 줄('2026년 11월 ...')에서 (연, 월)을 읽는다. 못 읽으면 None."""
    full = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    pt = _tess()
    band = img[: min(60, img.shape[0])]
    crops = [band, band[:, : band.shape[1] * 3 // 4]]
    tb = title_box(full) if full is not None else None
    if tb:                                              # 제목 글자 자리만 잘라 읽는다. '2026년 11월'이 있는 왼쪽 부분이 가장 정확하다
        ys = slice(max(tb["y0"] - 8, 0), tb["y1"] + 8)
        left_w = int((tb["x1"] - tb["x0"]) * 0.36)
        crops[:0] = [img[ys, max(tb["x0"] - 6, 0): tb["x0"] + left_w], img[ys, 20: img.shape[1] - 20],
                     img[ys, max(tb["x0"] - 6, 0): tb["x1"] + 6]]
    for crop in crops:
        try:
            t = _ocr(pt, crop)
        except Exception:
            continue
        m = _TITLE.search(t.replace(" ", ""))
        if m and 1 <= int(m.group(2)) <= 12:
            return int(m.group(1)), int(m.group(2))
    return None
