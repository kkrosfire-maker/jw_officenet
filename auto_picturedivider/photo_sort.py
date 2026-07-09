import os
import shutil
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

FUZZY_THRESHOLD = 0.8


@dataclass
class MatchResult:
    filename: str
    hospital: str       # 파일명 첫 단어 (추출된 거래처명)
    match_type: str     # "exact" | "fuzzy" | "none"
    manager: str = ""
    matched_key: str = ""
    ratio: float = 0.0


def _best_fuzzy_match(hospital: str, lookup: dict) -> tuple[str | None, float]:
    best_key, best_ratio = None, 0.0
    for key in lookup:
        ratio = SequenceMatcher(None, hospital, key).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_key = key
    if best_ratio >= FUZZY_THRESHOLD:
        return best_key, best_ratio
    return None, best_ratio


def classify(files: list[str], lookup: dict[str, str]) -> list[MatchResult]:
    """파일 목록을 거래처명 lookup으로 분류. 파일 이동 등 부수효과 없음."""
    results = []
    for filename in sorted(files):
        stem = Path(filename).stem
        parts = stem.split()
        hospital = parts[0] if parts else stem

        if hospital in lookup:
            results.append(MatchResult(
                filename=filename, hospital=hospital,
                match_type="exact", manager=lookup[hospital],
                matched_key=hospital, ratio=1.0,
            ))
        else:
            matched_key, ratio = _best_fuzzy_match(hospital, lookup)
            if matched_key:
                results.append(MatchResult(
                    filename=filename, hospital=hospital,
                    match_type="fuzzy", manager=lookup[matched_key],
                    matched_key=matched_key, ratio=ratio,
                ))
            else:
                results.append(MatchResult(
                    filename=filename, hospital=hospital,
                    match_type="none", ratio=ratio,
                ))
    return results


def _move_file(photo_dir: str, filename: str, manager: str) -> None:
    target_dir = os.path.join(photo_dir, manager)
    os.makedirs(target_dir, exist_ok=True)
    src = os.path.join(photo_dir, filename)
    dst = os.path.join(target_dir, filename)
    if os.path.exists(dst):
        base, ext = Path(filename).stem, Path(filename).suffix
        counter = 1
        while os.path.exists(dst):
            dst = os.path.join(target_dir, f"{base}_{counter}{ext}")
            counter += 1
    shutil.move(src, dst)


@dataclass
class SortEvent:
    """병원별 분류 실행 이벤트.

    kind: "moved" | "skipped" | "summary"
    각 kind에서 실제로 쓰는 필드만 채워지고 나머지는 기본값으로 남는다.
    """
    kind: str
    filename: str = ""
    manager: str = ""
    match_type: str = ""   # "exact" | "fuzzy"
    hospital: str = ""
    matched_key: str = ""
    ratio: float = 0.0
    moved_exact: int = 0
    moved_fuzzy: int = 0
    skipped_count: int = 0


def execute_moves(
    photo_dir: str,
    results: list[MatchResult],
    on_event=lambda e: None,
) -> list[SortEvent]:
    """classify() 결과에 따라 실제로 파일을 이동시킨다.

    match_type이 "none"인 항목은 이동하지 않고 건너뛴다.
    단계마다 on_event(SortEvent)를 호출하고, 전체 이벤트 목록을 반환한다.
    """
    events: list[SortEvent] = []

    def emit(e: SortEvent) -> None:
        events.append(e)
        on_event(e)

    moved_exact = moved_fuzzy = 0
    skipped_count = 0

    for r in results:
        if r.match_type == "none":
            skipped_count += 1
            emit(SortEvent(kind="skipped", filename=r.filename, hospital=r.hospital))
            continue

        _move_file(photo_dir, r.filename, r.manager)
        if r.match_type == "exact":
            moved_exact += 1
        else:
            moved_fuzzy += 1
        emit(SortEvent(
            kind="moved",
            filename=r.filename, manager=r.manager, match_type=r.match_type,
            hospital=r.hospital, matched_key=r.matched_key, ratio=r.ratio,
        ))

    emit(SortEvent(
        kind="summary",
        moved_exact=moved_exact, moved_fuzzy=moved_fuzzy, skipped_count=skipped_count,
    ))

    return events
