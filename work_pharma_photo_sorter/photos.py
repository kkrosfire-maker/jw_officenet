"""분류 대상 이미지 파일 목록. 지원 확장자는 이 모듈 한 곳에서만 정의한다."""
import os
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".jfif"}


def list_images(photo_dir: str) -> list[str]:
    return [
        f for f in os.listdir(photo_dir)
        if os.path.isfile(os.path.join(photo_dir, f))
        and Path(f).suffix.lower() in IMAGE_EXTS
    ]
