"""이미지 파일 I/O 헬퍼 — 한글 경로 대응 + 덮어쓰기 방지. main.py / annotate_app.py 공용."""
import re
import shutil
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


_COPY_TAIL = re.compile(r"\s*\(복사\d+\)$")


def make_copy(src, dest_dir, taken=()) -> str:
    """원본 사진을 dest_dir 에 '이름 (복사1).확장자' 로 복사하고 새 경로를 돌려준다. 이미 있는 번호는 건너뛴다.
    복사본을 다시 복사해도 '(복사2)'처럼 번호만 올라간다."""
    src = Path(src)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = _COPY_TAIL.sub("", src.stem)
    taken = {str(Path(t)) for t in taken}
    n = 1
    while True:
        p = dest_dir / f"{stem} (복사{n}){src.suffix}"
        if not p.exists() and str(p) not in taken:
            break
        n += 1
    shutil.copy2(src, p)
    return str(p)
