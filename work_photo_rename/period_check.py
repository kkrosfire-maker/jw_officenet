"""사진 상단의 '[조 회 일] 2026-10-01~2026-10-31' 을 OCR로 읽어 선택한 연/월과 비교한다.

Tesseract(영문 데이터만 있어도 숫자는 읽힘)를 쓴다. 사진이 비스듬/흐려 한 번에 못 읽는 경우가
있어서 상단 영역을 몇 가지 전처리로 여러 번 시도한다.
"""
import calendar
import re
from pathlib import Path

import cv2
import numpy as np

TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_DATE = re.compile(r"(20\d{2})\s*[-.\u2013/]\s*(\d{1,2})\s*[-.\u2013/]\s*(\d{1,2})")


TESSDATA = Path(getattr(__import__("sys"), "_MEIPASS", Path(__file__).resolve().parent)) / "tessdata"      # kor.traineddata 를 여기에 둔다
_PHARMA = re.compile(r"제\s*약\s*(?:회\s*)?사\s*[:;,.]?\s*([^\n\[\]|]{2,30})")


def _tess():
    import os
    import pytesseract
    if Path(TESS).exists():
        pytesseract.pytesseract.tesseract_cmd = TESS
    if (TESSDATA / "kor.traineddata").exists():
        os.environ["TESSDATA_PREFIX"] = str(TESSDATA)
    return pytesseract


def read_pharma(img):
    """사진 상단의 '제약사 : OOO' / '제약회사 : OOO' 글자를 읽어 OOO를 돌려준다. 못 읽으면 None.
    한글 인식 데이터(tessdata/kor.traineddata)가 없으면 None."""
    if not (TESSDATA / "kor.traineddata").exists():
        return None
    try:
        pt = _tess()
    except Exception:
        return None
    for i, g in enumerate(_variants(img)):
        if i > 1:
            break
        for psm in (11, 6):
            try:
                txt = pt.image_to_string(g, lang="kor+eng", config=f"--psm {psm}")
            except Exception:
                return None
            for m in _PHARMA.finditer(txt):
                name = re.sub(r"[^0-9A-Za-z가-힣()㈜ ]", "", m.group(1)).strip()
                if len(name) >= 2:
                    return name
    return None


def _variants(img):
    """OCR을 시도할 (상단 영역 × 전처리) 후보들."""
    h, w = img.shape[:2]
    top = img[: int(h * 0.38)]
    scale = 2000 / w if w < 2000 else 1.0
    if scale != 1.0:
        top = cv2.resize(top, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(top, cv2.COLOR_BGR2GRAY)
    yield gray
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
    yield clahe
    yield cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 15)
    # 가로줄(모아레) 노이즈가 심한 사진용
    yield cv2.GaussianBlur(clahe, (3, 3), 0)


def read_period(img):
    """(시작일, 종료일) 각각 (년, 월, 일) 튜플. 못 읽으면 None."""
    try:
        pt = _tess()
    except Exception:
        return None
    for g in _variants(img):
        for psm in (6, 11):
            try:
                txt = pt.image_to_string(g, lang="eng", config=f"--psm {psm}")
            except Exception:
                return None
            found = [(int(a), int(b), int(c)) for a, b, c in _DATE.findall(txt)]
            found = [d for d in found if 1 <= d[1] <= 12 and 1 <= d[2] <= 31]
            if len(found) >= 2:
                return found[0], found[1]
    return None


def check_period(period, year: int, month: int):
    """(ok, 사유). 시작·종료 모두 선택한 연/월이어야 하고, 1일~말일이 아니면 경고한다."""
    if period is None:
        return False, "날짜를 읽지 못함"
    (sy, sm, sd), (ey, em, ed) = period
    if (sy, sm) != (year, month) or (ey, em) != (year, month):
        return False, f"{sy}-{sm:02d}-{sd:02d}~{ey}-{em:02d}-{ed:02d} ≠ {year}-{month:02d}"
    last = calendar.monthrange(year, month)[1]
    if sd != 1 or ed != last:
        return False, f"기간이 1일~{last}일이 아님 ({sd}일~{ed}일)"
    return True, f"{sy}-{sm:02d}-{sd:02d}~{ey}-{em:02d}-{ed:02d}"
