"""한 장의 사진에 쓸 꼭짓점을 정하는 단일 규칙.

우선순위: 저장된 수정값 → 학습값 → 자동 감지 → 5% 여백 기본값.
화면(_redetect)과 일괄 저장(_run_batch)이 모두 이 함수를 쓴다.
"""
from collections import namedtuple

import numpy as np

from converter import auto_detect_corners, four_point_transform

SAVED, LEARNED, AUTO, FALLBACK = "saved", "learned", "auto", "fallback"
FALLBACK_MARGIN = 0.05

Resolved = namedtuple("Resolved", ["pts", "source", "detail"])
"""
pts    — [[x, y] * 4] 꼭짓점
source — "saved" | "learned" | "auto" | "fallback"
detail — learned일 때 참고한 학습 예시의 원본 파일명, 그 외 ""
"""


def margin_corners(width, height, ratio=FALLBACK_MARGIN):
    m = min(width, height) * ratio
    return [[m, m], [width - m, m], [width - m, height - m], [m, height - m]]


def resolve_corners(image, saved_pts=None, memory=None,
                    detect=auto_detect_corners, on_error=None) -> Resolved:
    """image: BGR ndarray(이미 회전 적용된 상태).
    saved_pts: 이 회전 상태에서 사용자가 맞춰둔 꼭짓점(없으면 None).
    memory: CornerMemory(없으면 학습 단계 생략).
    on_error(where, exc): 학습 매칭이 예외를 내도 자동 감지로 계속 진행하고, 여기로만 알린다."""
    if saved_pts and len(saved_pts) == 4:
        return Resolved([list(p) for p in saved_pts], SAVED, "")

    if memory is not None:
        try:
            learned = memory.match(image)
        except Exception as e:
            if on_error:
                on_error("memory.match", e)
            learned = None
        if learned is not None:
            return Resolved(np.asarray(learned.pts).tolist(), LEARNED, learned.source or "")

    pts = detect(image)
    if pts is not None:
        return Resolved(np.asarray(pts).tolist(), AUTO, "")

    h, w = image.shape[:2]
    return Resolved(margin_corners(w, h), FALLBACK, "")


def render_resolved(image, resolved: Resolved):
    """일괄 저장용: 감지 실패(fallback)면 원본 그대로, 아니면 원근 변환."""
    if resolved.source == FALLBACK:
        return image
    return four_point_transform(image, np.array(resolved.pts, dtype="float32"))
