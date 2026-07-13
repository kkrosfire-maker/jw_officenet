"""
Tesseract 기반 처방약 이미지 분석기 (무료, API 불필요)

대상 문서: 제약회사별 소모 통계 [전체]
열 구조 (이미지 너비 대비 X 비율):
  제약사명   0 ~ 21%
  약품코드  24 ~ 36%  (보험코드 9자리 포함)
  약품명    30 ~ 52%
  총사용량  58 ~ 64%  ← 핵심 추출 열
"""
from __future__ import annotations

import os
import re

import pytesseract
from PIL import Image, ImageEnhance

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
os.environ['TESSDATA_PREFIX'] = os.path.expanduser('~/tessdata')

_CFG   = '--psm 6 --oem 3'
_SKIP  = frozenset(['소계', '총계', '소 계', '총 계', '검색기간', '출력일자', '비트',
                    '제약회사별', '소모통계', '소모 통계'])
_PHARM = ('제약', '재약', '바이오', '약품', '파마', '케어', '사이어스', '메디', '헬스')

# 단일 한글 문자 중 진료실 관련 문자
_CLINIC_SINGLE = frozenset('진료실검')


class TesseractImageAnalyzer:
    """Tesseract OCR 기반 ImageAnalyzer 구현체."""

    def analyze(self, path: str) -> dict | None:
        img = Image.open(path).convert('RGB')
        img = ImageEnhance.Contrast(img).enhance(1.4)

        w, h = img.size
        raw = pytesseract.image_to_data(img, lang='kor+eng', config=_CFG,
                                         output_type=pytesseract.Output.DICT)
        full_text = pytesseract.image_to_string(img, lang='kor+eng', config=_CFG)

        words = _filter_words(raw, w, h)
        rows  = _cluster_rows(words)

        items   = _extract_items(words, rows)
        company = _find_company(rows, full_text)

        if not items:
            return None

        # 회사명 미인식 시 이미지 파일명으로 대체 가능하도록 빈 문자열 허용
        return {'document_type': '소모현황', 'company': company or '미인식', 'items': items}


# ── 내부 함수 ──────────────────────────────────────────────────────────────────

def _filter_words(data: dict, img_w: int, img_h: int) -> list[dict]:
    out = []
    for i in range(len(data['text'])):
        txt  = data['text'][i].strip()
        conf = data['conf'][i]
        if conf > 10 and txt:
            out.append({
                'text':  txt,
                'x':     data['left'][i],
                'y':     data['top'][i],
                'rel_x': data['left'][i] / img_w,
                'rel_y': data['top'][i]  / img_h,
            })
    return out


def _cluster_rows(words: list[dict], gap: int = 12) -> list[list[dict]]:
    if not words:
        return []
    s = sorted(words, key=lambda w: w['y'])
    rows: list[list[dict]] = [[s[0]]]
    for w in s[1:]:
        avg_y = sum(x['y'] for x in rows[-1]) / len(rows[-1])
        if abs(w['y'] - avg_y) <= gap:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w['x']) for r in rows]


def _find_company(rows: list, full_text: str) -> str:
    """
    제약사명 추출 전략:
    1. 데이터 영역(rel_y 0.12~0.55) 좌측(rel_x<0.21) 한글 중 제약키워드 포함
    2. 제약키워드 없어도 '주' 포함 + 4자 이상이면 후보로 등록
    3. image_to_string에서 '(주)' 패턴 탐색
    """
    pharm_candidate = ''
    fallback_candidate = ''

    for row in rows:
        if not row:
            continue
        avg_rel_y = sum(w['rel_y'] for w in row) / len(row)
        if not (0.12 < avg_rel_y < 0.55):
            continue

        rt = ' '.join(w['text'] for w in row)
        if any(s in rt for s in _SKIP):
            continue
        if not re.search(r'\d', rt):       # 숫자 없는 행은 헤더
            continue

        # 좌측 열(0~21%)의 한글 단어 (단일 문자 진료실 문자 제외)
        left_kor = [w for w in row
                    if w['rel_x'] < 0.21
                    and re.search(r'[가-힣]', w['text'])
                    and w['text'] not in _CLINIC_SINGLE]
        if not left_kor:
            continue

        name = ''.join(w['text'] for w in left_kor)

        # 1순위: 제약 관련 키워드
        if any(kw in name for kw in _PHARM):
            return name

        # 2순위: '주' + 4자 이상 → 후보 등록
        if not fallback_candidate and '주' in name and len(name) >= 4:
            # 진료실 단어 제거
            fallback_candidate = re.sub(r'[진료실제]', '', name).strip()

    if pharm_candidate:
        return pharm_candidate
    if fallback_candidate:
        return fallback_candidate

    # image_to_string 에서 (주)패턴 탐색
    joined = re.sub(r'(?<=[가-힣])\s(?=[가-힣])', '', full_text)
    for line in joined.split('\n'):
        line = line.strip()
        if not line or any(s in line for s in _SKIP):
            continue
        # "(주)" 또는 "주)" 형식
        m = re.search(r'[(\(]주\s*\)?([가-힣]{2,15})', line)
        if m:
            return '(주)' + m.group(1)
        # 제약키워드 + 첫 번째 숫자 이전 텍스트
        if any(kw in line for kw in _PHARM):
            m = re.match(r'^([^\d]{3,25})', line)
            if m:
                cand = re.sub(r'[|_\-\s]+$', '', m.group(1)).strip()
                if any(kw in cand for kw in _PHARM) and len(cand) >= 3:
                    return cand
    return ''


def _parse_qty(text: str) -> int | None:
    """쉼표·점을 천단위 구분자로 처리해 정수 반환."""
    cleaned = re.sub(r'[,.]', '', text)
    if cleaned.isdigit():
        return int(cleaned)
    return None


def _extract_items(words: list[dict], rows: list) -> list[dict]:
    """
    약품코드(0.24~0.36) + 총사용량(0.58~0.64) 쌍을 추출해 코드별 합산.

    보완: 코드는 있지만 수량이 없는 행(code_only)과
          수량은 있지만 코드가 없는 행(qty_only)을 Y 근접도로 매칭한다.
    """
    totals: dict[str, dict] = {}

    # 데이터 행별로 코드/수량 파악
    complete   = []  # (code, qty, name, avg_y)
    code_only  = []  # (code, name, avg_y)  — qty 없음
    qty_only   = []  # (qty, avg_y)          — code 없음

    for row in rows:
        avg_rel_y = sum(w['rel_y'] for w in row) / len(row) if row else 0
        if not (0.12 < avg_rel_y < 0.62):
            continue

        rt = ' '.join(w['text'] for w in row)
        if any(p in rt for p in _SKIP):
            continue
        if not re.search(r'\d', rt):
            continue

        avg_y = sum(w['y'] for w in row) / len(row)

        # 약품코드: 24~36%, 2~10자리 숫자
        code_ws = [w for w in row
                   if 0.22 <= w['rel_x'] <= 0.38
                   and re.fullmatch(r'\d{2,10}', w['text'])]

        # 총사용량: 58~64%, 숫자(쉼표·점 허용)
        qty_ws = [w for w in row
                  if 0.58 <= w['rel_x'] <= 0.64
                  and re.fullmatch(r'[\d,.]+', w['text'])]

        # 약품명: 30~52%
        name_ws = [w for w in row if 0.30 <= w['rel_x'] <= 0.52]
        name = ''.join(w['text'] for w in name_ws).strip()

        if code_ws and qty_ws:
            qty = _parse_qty(qty_ws[0]['text'])
            if qty and 0 < qty <= 100_000:
                complete.append((code_ws[0]['text'], qty, name, avg_y))
        elif code_ws and not qty_ws:
            code_only.append((code_ws[0]['text'], name, avg_y))
        elif qty_ws and not code_ws:
            qty = _parse_qty(qty_ws[0]['text'])
            if qty and 0 < qty <= 100_000:
                qty_only.append((qty, avg_y))

    # 완전한 행 먼저 집계
    for code, qty, name, _ in complete:
        _add_item(totals, code, name, qty)

    # 코드만 있는 행과 수량만 있는 행을 Y 근접으로 매칭
    used_qty_idx = set()
    for code, name, cy in code_only:
        best_i, best_d = -1, float('inf')
        for i, (qty, qy) in enumerate(qty_only):
            if i in used_qty_idx:
                continue
            d = abs(qy - cy)
            if d < best_d and d <= 50:
                best_d, best_i = d, i
        if best_i >= 0:
            qty = qty_only[best_i][0]
            used_qty_idx.add(best_i)
            _add_item(totals, code, name, qty)

    return [{'name': v['name'], 'quantity': v['qty']} for v in totals.values()]


def _add_item(totals: dict, code: str, name: str, qty: int) -> None:
    if code in totals:
        totals[code]['qty'] += qty
        if len(name) > len(totals[code]['name']):
            totals[code]['name'] = name
    else:
        totals[code] = {'name': name or code, 'qty': qty}
