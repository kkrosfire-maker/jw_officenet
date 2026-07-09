import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

MAX_ZIP_BYTES = 300 * 1024 * 1024  # 300 MB


def extract_pharma(filename: str) -> str:
    """파일명 마지막 단어에서 제약사명 추출. (주), 기호, 끝 일련번호 제거."""
    stem = Path(filename).stem
    parts = stem.split()
    raw = parts[-1] if parts else stem
    cleaned = re.sub(r'\(주\)', '', raw)
    cleaned = re.sub(r'[^가-힣a-zA-Z0-9]', '', cleaned)
    cleaned = re.sub(r'\d+$', '', cleaned)  # 끝 일련번호 제거 (안국약품2 → 안국약품)
    return cleaned.strip() if cleaned.strip() else "기타"


def split_into_parts(
    files_with_sizes: list[tuple[str, int]], max_bytes: int
) -> list[list[str]]:
    """파일 목록을 각 묶음 합계가 max_bytes 이하가 되도록 분할."""
    parts: list[list[str]] = []
    current: list[str] = []
    current_size = 0
    for fname, size in files_with_sizes:
        if current and current_size + size > max_bytes:
            parts.append(current)
            current = [fname]
            current_size = size
        else:
            current.append(fname)
            current_size += size
    if current:
        parts.append(current)
    return parts


@dataclass
class ZipEvent:
    """제약사 ZIP 빌드 진행 이벤트.

    kind: "start" | "convert_failed" | "zip_created" | "summary"
    각 kind에서 실제로 쓰는 필드만 채워지고 나머지는 기본값으로 남는다.
    """
    kind: str
    pharma_name: str = ""
    folder_name: str = ""
    filename: str = ""
    file_count: int = 0
    zip_mb: float = 0.0
    over_limit: bool = False
    error: str = ""
    total_files: int = 0
    total_pharma: int = 0
    total_zips: int = 0
    out_dir: str = ""


def build_pharma_zips(
    photo_dir: str,
    files: list[str],
    out_dir: Path,
    on_event=lambda e: None,
) -> list[ZipEvent]:
    """제약사별로 이미지를 그룹핑해 JPG로 변환 후 zip으로 묶는다.

    파일명 마지막 단어(extract_pharma)를 제약사명으로 보고 그룹핑하며,
    한 제약사의 용량 합계가 MAX_ZIP_BYTES를 넘으면 여러 zip으로 분할한다.
    진행 단계마다 on_event(ZipEvent)를 호출하고, 전체 이벤트 목록을 반환한다.
    """
    events: list[ZipEvent] = []

    def emit(e: ZipEvent) -> None:
        events.append(e)
        on_event(e)

    out_dir.mkdir(exist_ok=True)

    pharma_groups: dict[str, list[tuple[str, int]]] = {}
    for f in files:
        pharma = extract_pharma(f)
        size = os.path.getsize(os.path.join(photo_dir, f))
        pharma_groups.setdefault(pharma, []).append((f, size))

    emit(ZipEvent(
        kind="start",
        total_files=len(files),
        total_pharma=len(pharma_groups),
        out_dir=str(out_dir),
    ))

    total_zips = 0

    for pharma_name, files_with_sizes in sorted(pharma_groups.items()):
        parts = split_into_parts(files_with_sizes, MAX_ZIP_BYTES)
        use_suffix = len(parts) > 1

        for i, part_files in enumerate(parts, 1):
            suffix = f"_{i}" if use_suffix else ""
            folder_name = f"{pharma_name}{suffix}"
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
                    emit(ZipEvent(kind="convert_failed", filename=fname, error=str(e)))

            zip_path = out_dir / f"{folder_name}.zip"
            with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_STORED) as zf:
                for jpg_file in sorted(part_dir.iterdir()):
                    zf.write(str(jpg_file), jpg_file.name)

            shutil.rmtree(part_dir)

            zip_bytes = zip_path.stat().st_size
            emit(ZipEvent(
                kind="zip_created",
                pharma_name=pharma_name,
                folder_name=folder_name,
                file_count=converted,
                zip_mb=zip_bytes / (1024 * 1024),
                over_limit=zip_bytes > MAX_ZIP_BYTES,
            ))
            total_zips += 1

    emit(ZipEvent(kind="summary", total_zips=total_zips, out_dir=str(out_dir)))

    return events
