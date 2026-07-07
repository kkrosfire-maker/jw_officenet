"""Core image processing: perspective correction."""
from collections import namedtuple

import cv2
import numpy as np

ProcessResult = namedtuple("ProcessResult", ["image", "pts", "strategy"])
"""
image    — 처리된 결과 이미지 (BGR ndarray)
pts      — 사용된 코너 좌표 (float32 (4,2)) 또는 None (감지 실패 시)
strategy — "auto" | "manual" | "fallback"
           auto    : auto_detect_corners 성공
           manual  : 호출자가 pts 제공
           fallback: 감지 실패 → 원본 그대로 반환
"""


def order_points(pts):
    """TL, TR, BR, BL 순으로 4개 좌표 정렬."""
    pts = np.array(pts, dtype="float32")
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # TL: 합 최소
    rect[2] = pts[np.argmax(s)]   # BR: 합 최대
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # TR: 차 최소
    rect[3] = pts[np.argmax(diff)]  # BL: 차 최대
    return rect


def four_point_transform(image, pts):
    """4점 원근 변환 → 직사각형 이미지 반환."""
    rect = order_points(pts)
    tl, tr, br, bl = rect

    w1 = np.linalg.norm(br - bl)
    w2 = np.linalg.norm(tr - tl)
    max_w = max(int(w1), int(w2))

    h1 = np.linalg.norm(tr - br)
    h2 = np.linalg.norm(tl - bl)
    max_h = max(int(h1), int(h2))

    dst = np.array([
        [0, 0],
        [max_w - 1, 0],
        [max_w - 1, max_h - 1],
        [0, max_h - 1],
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (max_w, max_h))


def auto_detect_corners(image):
    """
    자동 코너 감지. 성공 시 float32 ndarray (4,2) 반환, 실패 시 None.

    전략 1: 엣지 기반 사각형 탐색 (일반적인 경우)
    전략 2: 밝은 영역(흰 종이·화면) 탐색 (모니터 사진에서 화면 안의 흰 문서 감지)
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    img_area = image.shape[0] * image.shape[1]

    # ── 전략 1: 엣지 기반 ───────────────────────────────────────────────
    for blur_k, c_lo, c_hi, dilate_iter in [
        (5, 30, 100, 2),
        (5, 50, 150, 1),
        (3, 10,  80, 3),
        (7, 20, 120, 2),
    ]:
        blurred = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)
        edged   = cv2.Canny(blurred, c_lo, c_hi)
        kernel  = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edged   = cv2.dilate(edged, kernel, iterations=dilate_iter)

        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
            peri   = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and cv2.contourArea(approx) > img_area * 0.05:
                return approx.reshape(4, 2).astype("float32")

    # ── 전략 2: 밝은 사각형 탐색 (흰 문서·화면이 회색 배경 안에 있는 경우) ──
    # 이미 균일한 이미지(보정 완료 문서 등)는 S2 가정이 성립하지 않으므로 스킵
    gray_uniformity = gray.std() / (gray.mean() + 1e-6)
    if gray_uniformity < 0.15:
        return None

    scale    = min(1.0, 1200 / max(image.shape[:2]))
    small    = cv2.resize(gray, (0, 0), fx=scale, fy=scale)
    blurred  = cv2.GaussianBlur(small, (15, 15), 0)

    threshold = np.percentile(blurred, 85)
    threshold = max(threshold, 180)
    _, bright = cv2.threshold(blurred, int(threshold), 255, cv2.THRESH_BINARY)

    k      = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, k, iterations=3)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN,  k, iterations=2)

    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        area = cv2.contourArea(c) / (scale * scale)
        if area < img_area * 0.05:
            continue
        peri   = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.04 * peri, True)
        pts    = (approx.reshape(-1, 2) / scale).astype("float32")
        if len(pts) == 4:
            return pts
        if len(pts) >= 4:
            rect = cv2.minAreaRect(pts)
            box  = cv2.boxPoints(rect).astype("float32")
            return box

    return None


def process_image(image, pts=None):
    """
    이미지 처리 파이프라인.
    pts=None 이면 자동 감지, 제공하면 해당 점으로 원근 변환.
    반환: ProcessResult(image, pts, strategy)
    """
    if pts is None:
        pts = auto_detect_corners(image)
        if pts is None:
            return ProcessResult(image, None, "fallback")
        strategy = "auto"
    else:
        strategy = "manual"

    result = four_point_transform(image, pts)
    return ProcessResult(result, pts, strategy)
