"""
PROTOTYPE — throwaway. 질문: 3단계(그리드 OCR) 방향을 정하기 전에, 실제 사진
(다양한 variation)에서 Tesseract가 어떤 결과를 내는지 확인하고, 빨간 테두리
영역을 "줄 단위 텍스트"로 볼지 "컬럼 위치 기반 표"로 파싱할지 판단한다.

순수 함수만 (I/O는 파일 경로를 받는 정도). tui.py가 이 모듈을 감싸는 얇은 셸.
답이 나오면 검증된 함수만 photo_converter/ocr_grid.py 등으로 옮기고 이 폴더는 삭제.
"""
import os
import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
os.environ.setdefault("TESSDATA_PREFIX", os.path.expanduser("~/tessdata"))


def find_red_rects(img_bgr, min_area_ratio=0.001):
    """annotate.py draw_rects()가 그리는 순수 빨강(BGR 0,0,255) 테두리를 색상 마스크로 감지.
    선이 닫히도록 dilate 후 외곽 contour의 bounding box를 반환 (y 기준 정렬)."""
    b, g, r = (img_bgr[:, :, i].astype(int) for i in range(3))
    mask = ((r - g > 80) & (r - b > 80)).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((15, 15), np.uint8), iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = img_bgr.shape[:2]
    min_area = w * h * min_area_ratio
    boxes = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        if cw * ch >= min_area:
            boxes.append((x, y, x + cw, y + ch))
    boxes.sort(key=lambda bx: bx[1])
    return boxes


def crop(img_bgr, box, inset=6):
    """box 안쪽으로 inset만큼 파고들어 크롭 (빨간 테두리 선 자체가 텍스트로 인식되는 것 방지)."""
    x0, y0, x1, y1 = box
    h, w = img_bgr.shape[:2]
    x0, y0 = max(0, x0 + inset), max(0, y0 + inset)
    x1, y1 = min(w, x1 - inset), min(h, y1 - inset)
    return img_bgr[y0:y1, x0:x1]


def preprocess(img_bgr, enhance_contrast=True, scale=1.0):
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    if scale != 1.0:
        pil = pil.resize((max(1, int(pil.width * scale)), max(1, int(pil.height * scale))))
    if enhance_contrast:
        pil = ImageEnhance.Contrast(pil).enhance(1.4)
    return pil


def ocr_raw_text(pil_img, lang="kor+eng", psm=6):
    return pytesseract.image_to_string(pil_img, lang=lang, config=f"--psm {psm} --oem 3")


def ocr_words(pil_img, lang="kor+eng", psm=6, min_conf=10):
    w, h = pil_img.size
    data = pytesseract.image_to_data(
        pil_img, lang=lang, config=f"--psm {psm} --oem 3", output_type=pytesseract.Output.DICT
    )
    words = []
    for i in range(len(data["text"])):
        txt = data["text"][i].strip()
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1
        if conf > min_conf and txt:
            words.append({
                "text": txt,
                "x": data["left"][i], "y": data["top"][i],
                "w": data["width"][i], "h": data["height"][i],
                "rel_x": data["left"][i] / w, "rel_y": data["top"][i] / h,
                "conf": conf,
            })
    return words


def cluster_rows(words, gap=12):
    if not words:
        return []
    s = sorted(words, key=lambda x: x["y"])
    rows = [[s[0]]]
    for wd in s[1:]:
        avg_y = sum(x["y"] for x in rows[-1]) / len(rows[-1])
        if abs(wd["y"] - avg_y) <= gap:
            rows[-1].append(wd)
        else:
            rows.append([wd])
    return [sorted(r, key=lambda x: x["x"]) for r in rows]


def rows_to_lines(rows):
    return [" ".join(w["text"] for w in r) for r in rows]


def extract_columns(rows, col_ranges):
    """col_ranges: {'name': (lo, hi), ...} rel_x(0~1) 기준. 행마다 컬럼별 텍스트를 합쳐 dict로 반환."""
    out = []
    for row in rows:
        rec = {}
        for col, (lo, hi) in col_ranges.items():
            ws = [w for w in row if lo <= w["rel_x"] < hi]
            rec[col] = "".join(w["text"] for w in ws).strip()
        if any(rec.values()):
            out.append(rec)
    return out
