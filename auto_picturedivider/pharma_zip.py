import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


def extract_pharma(filename: str) -> str:
    """파일명 마지막 단어에서 제약사명 추출. (주), 기호, 끝 일련번호 제거."""
    stem = Path(filename).stem
    parts = stem.split()
    raw = parts[-1] if parts else stem
    cleaned = re.sub(r'\(주\)', '', raw)
    cleaned = re.sub(r'[^가-힣a-zA-Z0-9]', '', cleaned)
    cleaned = re.sub(r'\d+$', '', cleaned)  # 끝 일련번호 제거 (안국약품2 → 안국약품)
    return cleaned.strip() if cleaned.strip() else "기타"


@dataclass
class FolderEvent:
    """제약사별 폴더 빌드 진행 이벤트.

    kind: "start" | "convert_failed" | "folder_created" | "summary"
    각 kind에서 실제로 쓰는 필드만 채워지고 나머지는 기본값으로 남는다.
    """
    kind: str
    pharma_name: str = ""
    folder_name: str = ""
    filename: str = ""
    file_count: int = 0
    error: str = ""
    total_files: int = 0
    total_pharma: int = 0
    total_folders: int = 0
    out_dir: str = ""


# 예전 이름 호환
ZipEvent = FolderEvent


def build_pharma_folders(
    photo_dir: str,
    files: list[str],
    out_dir: Path,
    on_event=lambda e: None,
) -> list[FolderEvent]:
    """제약사별로 이미지를 그룹핑해 JPG로 변환 후 폴더로 저장한다.

    파일명 마지막 단어(extract_pharma)를 제약사명으로 보고 그룹핑하며,
    제약사명과 같은 이름의 폴더 하나에 변환된 JPG들을 넣는다.
    진행 단계마다 on_event(FolderEvent)를 호출하고, 전체 이벤트 목록을 반환한다.
    """
    events: list[FolderEvent] = []

    def emit(e: FolderEvent) -> None:
        events.append(e)
        on_event(e)

    out_dir.mkdir(exist_ok=True)

    pharma_groups: dict[str, list[str]] = {}
    for f in files:
        pharma = extract_pharma(f)
        pharma_groups.setdefault(pharma, []).append(f)

    emit(FolderEvent(
        kind="start",
        total_files=len(files),
        total_pharma=len(pharma_groups),
        out_dir=str(out_dir),
    ))

    total_folders = 0

    for pharma_name, part_files in sorted(pharma_groups.items()):
        folder_name = pharma_name
        part_dir = out_dir / folder_name

        if part_dir.exists():
            shutil.rmtree(part_dir)
        part_dir.mkdir()

        converted = 0
        for fname in part_files:
            src = os.path.join(photo_dir, fname)
            dst = part_dir / (Path(fname).stem + ".jpg")
            try:
                with Image.open(src) as img:
                    if img.mode in ("RGBA", "P", "LA"):
                        img = img.convert("RGB")
                    img.save(str(dst), "JPEG", quality=90)
                converted += 1
            except Exception as e:
                emit(FolderEvent(kind="convert_failed", filename=fname, error=str(e)))

        emit(FolderEvent(
            kind="folder_created",
            pharma_name=pharma_name,
            folder_name=folder_name,
            file_count=converted,
        ))
        total_folders += 1

    emit(FolderEvent(kind="summary", total_folders=total_folders, out_dir=str(out_dir)))

    return events


# 예전 이름 호환
build_pharma_zips = build_pharma_folders
