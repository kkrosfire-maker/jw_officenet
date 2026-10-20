"""이미지 파일 I/O 헬퍼 — 한글 경로 대응 + 덮어쓰기 방지. main.py / annotate_app.py 공용."""
from pathlib import Path

import cv2
import numpy as np


def read_image(path: str):
    buf = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def write_image(path: str, img) -> bool:
    ext = Path(path).suffix.lower() or ".png"
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(str(path))
    return bool(ok)


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    p = directory / (stem + suffix)
    n = 1
    while p.exists():
        p = directory / f"{stem}_{n}{suffix}"
        n += 1
    return p
