"""순수 퍼지 매칭 엔진. tkinter와 완전히 분리되어 단독 테스트·CLI 사용 가능."""
import re
import threading
from collections import defaultdict
from typing import Callable

import numpy as np
from rapidfuzz import fuzz
from rapidfuzz.process import cdist
from scipy.optimize import linear_sum_assignment

CHUNK = 500

_UNIT_PATTERNS = [
    (r'[미밀]리그[람램]',   'mg'),
    (r'[미밀]리리터',       'ml'),
    (r'마이크로그[람램]',   'mcg'),
    (r'[μµ]g',             'mcg'),
    (r'그[람램]',           'g'),
    (r'리터',               'l'),
    (r'국제단위',           'iu'),
    (r'밀리당량',           'meq'),
]


def _normalize(s: str) -> str:
    for pattern, repl in _UNIT_PATTERNS:
        s = re.sub(pattern, repl, s, flags=re.IGNORECASE)
    return s


def _group_key(s: str) -> tuple:
    norm = _normalize(s)
    first = s[0].lower() if s else ""
    nums = tuple(re.findall(r'\d+(?:\.\d+)?', norm))
    return (first, nums)


def _korean_core(s: str) -> str:
    return re.sub(r'[^가-힣]', '', _normalize(s))


def match(
    list_a: list[str],
    list_b: list[str],
    threshold: int = 80,
    cancel_event: threading.Event | None = None,
    progress_cb: Callable[[float], None] | None = None,
) -> list[dict]:
    """list_a × list_b 최적 1:1 매칭 결과를 반환한다.

    Args:
        list_a: 기준 목록 (중복 없어야 함).
        list_b: 비교 목록 (중복 없어야 함).
        threshold: 이 값 미만의 유사도는 결과에서 제외.
        cancel_event: set()되면 즉시 빈 리스트 반환.
        progress_cb: 진행률(0–100)을 받는 콜백.

    Returns:
        [{"a": str, "b": str, "score": float}, ...] — threshold 이상만.
    """
    n, m = len(list_a), len(list_b)
    kor_a = [_korean_core(a) for a in list_a]
    kor_b = [_korean_core(b) for b in list_b]

    groups_a: dict[tuple, list[int]] = defaultdict(list)
    groups_b: dict[tuple, list[int]] = defaultdict(list)
    for i, a in enumerate(list_a):
        groups_a[_group_key(a)].append(i)
    for j, b in enumerate(list_b):
        groups_b[_group_key(b)].append(j)

    sim = np.zeros((n, m), dtype=np.float32)
    processed = 0

    for key, idx_a in groups_a.items():
        if cancel_event and cancel_event.is_set():
            return []

        if key not in groups_b:
            processed += len(idx_a)
            if progress_cb:
                progress_cb(processed / n * 90)
            continue

        idx_b = groups_b[key]
        sub_b = [list_b[j] for j in idx_b]

        for start in range(0, len(idx_a), CHUNK):
            if cancel_event and cancel_event.is_set():
                return []
            chunk_ia = idx_a[start:start + CHUNK]
            sub_sim = cdist([list_a[i] for i in chunk_ia], sub_b,
                            scorer=fuzz.WRatio, workers=-1)
            for ii, i in enumerate(chunk_ia):
                ka = kor_a[i]
                for jj, j in enumerate(idx_b):
                    kb = kor_b[j]
                    if ka in kb or kb in ka:
                        sim[i, j] = sub_sim[ii, jj]
            processed += len(chunk_ia)
            if progress_cb:
                progress_cb(processed / n * 90)

    if cancel_event and cancel_event.is_set():
        return []

    row_idx, col_idx = linear_sum_assignment(100 - sim)
    if progress_cb:
        progress_cb(100)

    results = []
    for r, c in zip(row_idx, col_idx):
        score = round(float(sim[r, c]), 1)
        if score >= threshold:
            results.append({"a": list_a[r], "b": list_b[c], "score": score})
    return results
