"""꼭짓점 학습 — 사용자가 직접 맞춘 영역을 기억해 두었다가 비슷한 사진에 다시 적용.

"학습"은 신경망 훈련이 아니라 "예시 저장 + 가장 닮은 예시 찾기" 방식이다.
  1) 학습: 사진의 특징(축소 썸네일 + ORB 특징점)과 사용자가 맞춘 4꼭짓점을 저장
  2) 적용: 새 사진과 썸네일이 닮은 학습 예시를 고른 뒤,
     - ORB 특징점 매칭으로 두 사진 사이 원근 관계(호모그래피)를 구해
       예시의 꼭짓점을 새 사진 좌표로 옮긴다 (구도가 조금 달라도 정확히 따라감)
     - 매칭이 안 되면, 썸네일이 아주 비슷할 때만 꼭짓점을 비율 그대로 옮긴다

저장 위치: %APPDATA%\\photo_converter\\learned\\ (exe 재빌드해도 유지)
  index.json  — 예시 목록 (원본 파일명, 크기, 정규화된 꼭짓점)
  <id>.npz    — 썸네일 + ORB 특징점 좌표/디스크립터
"""
import json
import os
import time
import uuid
from collections import namedtuple
from pathlib import Path

import cv2
import numpy as np

from converter import order_points

THUMB_SIZE       = 32      # 썸네일 한 변 (전체 구도 비교용)
FEAT_MAX_SIDE    = 1000    # ORB 계산 시 축소할 최대 변 길이
ORB_FEATURES     = 3000
RATIO_TEST       = 0.75
MIN_INLIERS      = 25      # 호모그래피 채택 최소 인라이어 수
CANDIDATE_NCC    = 0.3     # 이 이상 닮아야 특징점 매칭까지 시도
FALLBACK_NCC     = 0.92    # 특징점 매칭 실패 시, 이 이상 닮으면 비율대로 옮김
ASPECT_TOLERANCE = 0.15    # 가로세로 비율 차이 허용치
TOP_K            = 3

Match = namedtuple("Match", ["pts", "method", "source", "score"])
"""
pts    — float32 (4,2) 새 사진 좌표계 꼭짓점 (TL,TR,BR,BL)
method — "homography" | "similar"
source — 참고한 학습 예시의 원본 파일명
score  — homography: 인라이어 수 / similar: 썸네일 유사도(0~1)
"""


def default_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "photo_converter" / "learned"


# ── 특징 추출 ────────────────────────────────────────────────────────────

def _gray(image):
    return image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _thumb(gray):
    """구도 비교용 32×32 정규화 썸네일 (밝기·대비 차이 무시)."""
    t = cv2.resize(gray, (THUMB_SIZE, THUMB_SIZE), interpolation=cv2.INTER_AREA)
    t = cv2.GaussianBlur(t, (3, 3), 0).astype("float32").ravel()
    t -= t.mean()
    n = np.linalg.norm(t)
    return t / n if n > 1e-6 else t


def _orb(gray):
    """축소본에서 ORB 특징점 계산. 좌표는 원본 크기 기준으로 되돌려서 반환."""
    h, w = gray.shape[:2]
    s = min(1.0, FEAT_MAX_SIDE / max(h, w))
    small = cv2.resize(gray, (0, 0), fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else gray
    orb = cv2.ORB_create(nfeatures=ORB_FEATURES)
    kps, des = orb.detectAndCompute(small, None)
    if des is None or len(kps) == 0:
        return np.zeros((0, 2), "float32"), np.zeros((0, 32), "uint8")
    xy = np.array([k.pt for k in kps], dtype="float32") / s
    return xy, des


def _homography(q_xy, q_des, s_xy, s_des):
    """학습 예시 → 새 사진 호모그래피. 실패 시 (None, 0)."""
    if len(q_des) < MIN_INLIERS or len(s_des) < MIN_INLIERS:
        return None, 0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(s_des, q_des, k=2)
    good = [m for m, *rest in (p for p in pairs if p)
            if not rest or m.distance < RATIO_TEST * rest[0].distance]
    if len(good) < MIN_INLIERS:
        return None, 0
    src = np.float32([s_xy[m.queryIdx] for m in good])
    dst = np.float32([q_xy[m.trainIdx] for m in good])
    # 좌표가 원본 크기라 RANSAC 허용 오차도 원본 기준으로 키운다
    scale = max(np.ptp(dst[:, 0]), np.ptp(dst[:, 1]), 1.0) / FEAT_MAX_SIDE
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, max(3.0, 4.0 * scale))
    if H is None:
        return None, 0
    inliers = int(mask.sum())
    return (H, inliers) if inliers >= MIN_INLIERS else (None, inliers)


def _plausible(pts, w, h):
    """옮겨진 꼭짓점이 말이 되는 사각형인지 (볼록, 충분히 큼, 사진 근처)."""
    if not np.all(np.isfinite(pts)):
        return False
    poly = pts.reshape(-1, 1, 2).astype("float32")
    if not cv2.isContourConvex(poly):
        return False
    if cv2.contourArea(poly) < w * h * 0.03:
        return False
    margin = 0.1 * max(w, h)
    return bool(np.all(pts[:, 0] > -margin) and np.all(pts[:, 0] < w + margin)
                and np.all(pts[:, 1] > -margin) and np.all(pts[:, 1] < h + margin))


def _clip(pts, w, h):
    pts = pts.copy()
    pts[:, 0] = np.clip(pts[:, 0], 0, w)
    pts[:, 1] = np.clip(pts[:, 1], 0, h)
    return pts


# ── 저장소 ───────────────────────────────────────────────────────────────

class CornerMemory:
    def __init__(self, folder: Path | None = None):
        self._dir = Path(folder) if folder else default_dir()
        self._entries: list[dict] = []
        self._cache: dict[str, dict] = {}   # id → {"thumb","xy","des"}
        self._load_index()

    def __len__(self):
        return len(self._entries)

    # ── 인덱스 I/O ──

    def _index_path(self):
        return self._dir / "index.json"

    def _load_index(self):
        try:
            data = json.loads(self._index_path().read_text(encoding="utf-8"))
            self._entries = [e for e in data if (self._dir / f"{e['id']}.npz").exists()]
        except (OSError, ValueError, KeyError, TypeError):
            self._entries = []

    def _save_index(self):
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self._index_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(self._entries, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._index_path())

    def _features(self, entry):
        fid = entry["id"]
        if fid not in self._cache:
            with np.load(self._dir / f"{fid}.npz") as z:
                self._cache[fid] = {"thumb": z["thumb"], "xy": z["xy"], "des": z["des"]}
        return self._cache[fid]

    # ── 공개 API ──

    def add(self, image, pts, source: str = "") -> int:
        """현재 사진과 맞춘 꼭짓점을 학습. 같은 파일명으로 학습했던 예시는 새 것으로 교체.
        반환: 학습된 예시 총 개수."""
        h, w = image.shape[:2]
        rect = order_points(np.array(pts, dtype="float32"))
        gray = _gray(image)
        xy, des = _orb(gray)

        if source:
            for e in [e for e in self._entries if e.get("source") == source]:
                self._remove(e)

        fid = uuid.uuid4().hex[:12]
        self._dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(self._dir / f"{fid}.npz", thumb=_thumb(gray), xy=xy, des=des)
        self._entries.append({
            "id": fid,
            "source": source,
            "w": w,
            "h": h,
            "pts_norm": (rect / [w, h]).round(5).tolist(),
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self._save_index()
        return len(self._entries)

    def _remove(self, entry):
        self._entries.remove(entry)
        self._cache.pop(entry["id"], None)
        try:
            (self._dir / f"{entry['id']}.npz").unlink()
        except OSError:
            pass

    def clear(self):
        for e in list(self._entries):
            self._remove(e)
        self._save_index()

    def match(self, image) -> Match | None:
        """학습한 예시 중 이 사진과 닮은 것이 있으면 옮겨진 꼭짓점을, 없으면 None."""
        if not self._entries:
            return None
        h, w = image.shape[:2]
        gray = _gray(image)
        q_thumb = _thumb(gray)
        aspect = w / h

        scored = []
        for e in self._entries:
            if abs((e["w"] / e["h"]) / aspect - 1) > ASPECT_TOLERANCE:
                continue
            ncc = float(np.dot(q_thumb, self._features(e)["thumb"]))
            if ncc >= CANDIDATE_NCC:
                scored.append((ncc, e))
        if not scored:
            return None
        # 유사도 같으면 최근 학습분 우선
        scored.sort(key=lambda t: (t[0], t[1]["created"]), reverse=True)
        scored = scored[:TOP_K]

        q_xy, q_des = _orb(gray)
        best = None
        for ncc, e in scored:
            f = self._features(e)
            H, inliers = _homography(q_xy, q_des, f["xy"], f["des"])
            if H is None:
                continue
            src = (np.array(e["pts_norm"], "float32") * [e["w"], e["h"]]).reshape(-1, 1, 2)
            pts = cv2.perspectiveTransform(src.astype("float32"), H).reshape(4, 2)
            if not _plausible(pts, w, h):
                continue
            if best is None or inliers > best.score:
                best = Match(_clip(pts, w, h).astype("float32"), "homography",
                             e.get("source", ""), inliers)
        if best:
            return best

        ncc, e = scored[0]
        if ncc >= FALLBACK_NCC:
            pts = (np.array(e["pts_norm"], "float32") * [w, h]).astype("float32")
            return Match(pts, "similar", e.get("source", ""), ncc)
        return None
