"""
easyocr 기반 처방약 이미지 분석기 (API 불필요)

지원 문서:
  소모현황     — 제약회사별 소모 통계, "수 량" 컬럼 사용
  제약사별통계  — 제약사별 통계, "총사용량" 컬럼 사용
"""
from __future__ import annotations

import re
from pathlib import Path


class EasyOCRImageAnalyzer:
    """easyocr로 처방약 문서를 분석하는 ImageAnalyzer 구현체."""

    _SKIP_WORDS = frozenset([
        '소계', '총계', '합계', '소 계', '총 계', '합 계',
        '약품명', '품목명', '코드', '제조사', '보험코드', '규격',
        '검색기간', '검색', '수량', '수 량', '총사용량', '단가',
        '구분', '처방전', '변경', '단순', '교부', '제약사',
    ])

    _COMPANY_KEYWORDS = ('제약', '바이오', '약품', '파마', '케어', '헬스', '메디', '사이언스')

    def __init__(self) -> None:
        try:
            import easyocr
        except ImportError:
            import subprocess, sys
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'easyocr'])
            import easyocr
        print("  [OCR] 모델 로딩 중...", flush=True)
        self._reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
        print("  [OCR] 모델 로드 완료", flush=True)

    def analyze(self, path: str) -> dict | None:
        # OpenCV가 한글 경로를 못 읽으므로 PIL → numpy 경유
        import numpy as np
        from PIL import Image
        img = Image.open(path).convert('RGB')
        img_np = np.array(img)
        results = self._reader.readtext(img_np)
        return self._parse(results) if results else None

    # ── OCR 결과 → 블록 ────────────────────────────────────────────────

    @staticmethod
    def _to_blocks(results: list) -> list[dict]:
        blocks = []
        for bbox, text, conf in results:
            text = text.strip()
            if conf < 0.2 or not text:
                continue
            ys = [p[1] for p in bbox]
            xs = [p[0] for p in bbox]
            blocks.append({
                'text':  text,
                'cy':    (min(ys) + max(ys)) / 2,
                'cx':    (min(xs) + max(xs)) / 2,
                'x_min': min(xs),
                'x_max': max(xs),
                'h':     max(ys) - min(ys),
            })
        return blocks

    # ── 행 클러스터링 ──────────────────────────────────────────────────

    @staticmethod
    def _cluster_rows(blocks: list[dict]) -> list[list[dict]]:
        if not blocks:
            return []
        sorted_b = sorted(blocks, key=lambda b: b['cy'])
        heights = sorted([b['h'] for b in sorted_b if b['h'] > 2])
        thresh = (heights[len(heights) // 2] * 0.75) if heights else 10

        rows: list[list[dict]] = [[sorted_b[0]]]
        for b in sorted_b[1:]:
            row_cy = sum(x['cy'] for x in rows[-1]) / len(rows[-1])
            if abs(b['cy'] - row_cy) <= thresh:
                rows[-1].append(b)
            else:
                rows.append([b])
        return [sorted(row, key=lambda b: b['cx']) for row in rows]

    # ── 문서 유형 감지 ─────────────────────────────────────────────────

    @staticmethod
    def _detect_doc_type(rows: list, full_text: str) -> str:
        for row in rows[:8]:
            rt = ' '.join(b['text'] for b in row)
            if '제약사별통계' in rt or '제약사별 통계' in rt:
                return '제약사별통계'
            if any(kw in rt for kw in ('소모 통계', '소모현황', '소모 현황', '약품 소모')):
                return '소모현황'
        if '총사용량' in full_text:
            return '제약사별통계'
        return '소모현황'

    # ── 회사명 감지 ────────────────────────────────────────────────────

    def _detect_company(self, rows: list, full_text: str, doc_type: str) -> str:
        # 제약사별통계: "[제약사 : ...]" 패턴
        m = re.search(r'제약사\s*[:\s]+([^\]\n]{2,25})', full_text)
        if m:
            return m.group(1).strip().rstrip(']').strip()

        # 단독 행에 회사명만 있는 경우 (숫자 없이 회사 키워드 포함)
        for row in rows:
            rt = ' '.join(b['text'] for b in row)
            rt_clean = rt.strip()
            if (any(kw in rt_clean for kw in self._COMPANY_KEYWORDS)
                    and not re.search(r'\d{4,}', rt_clean)
                    and 3 < len(rt_clean) < 35):
                return rt_clean
        return ''

    # ── 약품 항목 추출 ─────────────────────────────────────────────────

    def _extract_items(self, rows: list, doc_type: str) -> list[dict]:
        qty_kw       = '총사용량' if doc_type == '제약사별통계' else '수 량'
        qty_fallback = '총사용량' if doc_type == '제약사별통계' else '수량'

        # 헤더 행 → 수량 열 X 위치
        qty_col_x: float | None = None
        header_idx = 0
        for i, row in enumerate(rows):
            for b in row:
                if qty_kw in b['text'] or qty_fallback in b['text']:
                    qty_col_x = b['cx']
                    header_idx = i
                    break
            if qty_col_x is not None:
                break

        items = []
        for row in rows[header_idx + 1:]:
            rt = ' '.join(b['text'] for b in row)

            # 합계/헤더 행 건너뜀
            if any(kw in rt for kw in self._SKIP_WORDS):
                continue

            name = self._find_drug_name(row)
            qty  = self._find_qty(row, qty_col_x)

            if name and qty and qty < 100_000:
                items.append({'name': name, 'quantity': qty})

        return items

    @staticmethod
    def _find_drug_name(row: list[dict]) -> str:
        """왼쪽 65% 영역에서 가장 긴 한글 텍스트 블록."""
        if not row:
            return ''
        x_max = row[-1]['cx']
        candidates = [
            b for b in row
            if not re.fullmatch(r'[\d,.\-\s]+', b['text'])
            and b['cx'] < x_max * 0.65
            and len(b['text']) > 2
            and re.search(r'[가-힣a-zA-Z]', b['text'])
        ]
        if not candidates:
            return ''
        return max(candidates, key=lambda b: len(b['text']))['text']

    @staticmethod
    def _find_qty(row: list[dict], qty_col_x: float | None) -> int | None:
        """수량 열에 가장 가까운 정수. qty_col_x 없으면 가장 오른쪽 숫자."""
        nums = []
        for b in row:
            cleaned = b['text'].replace(',', '').replace(' ', '')
            if cleaned.isdigit() and int(cleaned) > 0:
                nums.append((b, int(cleaned)))

        if not nums:
            return None

        if qty_col_x is not None:
            nums.sort(key=lambda x: abs(x[0]['cx'] - qty_col_x))
        else:
            nums.sort(key=lambda x: x[0]['cx'], reverse=True)

        return nums[0][1]

    # ── 진입점 ─────────────────────────────────────────────────────────

    def _parse(self, results: list) -> dict | None:
        blocks = self._to_blocks(results)
        if not blocks:
            return None

        rows     = self._cluster_rows(blocks)
        full_text = ' '.join(b['text'] for row in rows for b in row)

        doc_type = self._detect_doc_type(rows, full_text)
        company  = self._detect_company(rows, full_text, doc_type)
        items    = self._extract_items(rows, doc_type)

        if not company:
            return None
        return {'document_type': doc_type, 'company': company, 'items': items}
