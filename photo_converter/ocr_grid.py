"""3단계: 그리드(사각형) 영역 OCR 인식. 프로토타입(ocr_prototype/)에서 검증된 로직만 정리."""
import os
import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance

from annotate import rect_corners

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
os.environ.setdefault("TESSDATA_PREFIX", os.path.expanduser("~/tessdata"))


def warp_rect(image, rect):
    """rect(회전 가능)를 4꼭짓점 기준으로 원근 변환해, 회전이 없는 반듯한 크롭으로 반환."""
    w = max(1, int(round(rect["hw"] * 2)))
    h = max(1, int(round(rect["hh"] * 2)))
    src = np.array(rect_corners(rect), dtype=np.float32)
    dst = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(image, m, (w, h))


def preprocess_for_ocr(img_bgr, enhance_contrast=True, scale=2.0):
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    if scale != 1.0:
        pil = pil.resize((max(1, int(pil.width * scale)), max(1, int(pil.height * scale))))
    if enhance_contrast:
        pil = ImageEnhance.Contrast(pil).enhance(1.4)
    return pil


def _ocr_words(pil_img, lang="kor+eng", psm=6, min_conf=10):
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
            words.append({"text": txt, "x": data["left"][i], "y": data["top"][i],
                          "rel_x": data["left"][i] / w})
    return words


def _cluster_rows(words, gap=12):
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


def recognize_lines(image_bgr, rect, lang="kor+eng", psm=6, scale=2.0, enhance_contrast=True):
    """rect 영역을 크롭·전처리해 OCR하고, 줄 단위 텍스트 리스트로 반환 (사람이 교정하는 초안용)."""
    crop = warp_rect(image_bgr, rect)
    pil = preprocess_for_ocr(crop, enhance_contrast=enhance_contrast, scale=scale)
    words = _ocr_words(pil, lang=lang, psm=psm)
    rows = _cluster_rows(words)
    return [" ".join(w["text"] for w in row) for row in rows]
