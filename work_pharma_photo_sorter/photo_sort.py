import json
import os
import re
import shutil
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from filename_parser import parse_filename
from review import FUZZY, UNMATCHED, ReviewItem

FUZZY_THRESHOLD = 0.85

_PAREN_RE = re.compile(r"\(.*?\)")


def _strip_parenthetical(name: str) -> str:
    """'병원명(내용)' 형태에서 괄호와 그 안의 내용을 제거해 병원명만 남긴다."""
    stripped = _PAREN_RE.sub("", name).strip()
    return stripped or name


@dataclass
class MatchResult:
    filename: str
    hospital: str       # 파일명에서 추출한 거래처명
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


def _group_by_base(lookup: dict[str, str]) -> dict[str, dict[str, str]]:
    """괄호를 뗀 병원명 → {원래 거래처명: 담당자}. 괄호만 다른 같은 병원을 한 묶음으로 본다."""
    groups: dict[str, dict[str, str]] = {}
    for key, manager in lookup.items():
        groups.setdefault(_strip_parenthetical(key), {})[key] = manager
    return groups


def _single_manager_key(group: dict[str, str] | None) -> str | None:
    """묶음의 담당자가 한 명뿐일 때만 대표 거래처명을 돌려준다.

    담당자가 갈리는 동명 지점(연세산부인과의원(김포)/(계양구) 등)은 괄호 없이는
    어디로 보낼지 알 수 없으므로 None — 임의로 섞지 않고 미분류로 남긴다.
    """
    if group and len(set(group.values())) == 1:
        return next(iter(group))
    return None


def classify(files: list[str], lookup: dict[str, str]) -> list[MatchResult]:
    """파일 목록을 거래처명 lookup으로 분류. 파일 이동 등 부수효과 없음.

    괄호 안 내용은 동명 지점 구분에만 쓴다: 괄호 포함 전체 이름이 엑셀에 있으면 그것을 쓰고,
    없으면 괄호를 무시한 병원명으로 찾되 담당자가 한 명으로 정해질 때만 매칭한다.
    """
    groups = _group_by_base(lookup)
    results = []
    for filename in sorted(files):
        candidates = parse_filename(filename).hospital_candidates

        # 1) 괄호 포함 전체 이름 정확 매칭 (동명 지점 구분)
        hit = next(((c, c) for c in candidates if c in lookup), None)
        # 2) 괄호를 뗀 이름 매칭 (엑셀 쪽 괄호와 파일명 쪽 괄호가 달라도 같은 병원으로)
        if not hit:
            hit = next(((c, k) for c in candidates
                        if (k := _single_manager_key(groups.get(_strip_parenthetical(c))))), None)
        if hit:
            candidate, key = hit
            results.append(MatchResult(
                filename=filename, hospital=candidate,
                match_type="exact", manager=lookup[key],
                matched_key=key, ratio=1.0,
            ))
            continue

        # 3) 모든 후보 중 유사도가 가장 높은 것 (괄호를 뗀 이름끼리 비교, 담당자 하나로 정해질 때만)
        best_candidate, best_key, best_ratio = candidates[0], None, 0.0
        for c in candidates:
            base, ratio = _best_fuzzy_match(_strip_parenthetical(c), groups)
            key = _single_manager_key(groups.get(base)) if base else None
            if key and ratio > best_ratio:
                best_candidate, best_key, best_ratio = c, key, ratio
        if best_key:
            results.append(MatchResult(
                filename=filename, hospital=best_candidate,
                match_type="fuzzy", manager=lookup[best_key],
                matched_key=best_key, ratio=best_ratio,
            ))
        else:
            results.append(MatchResult(
                filename=filename, hospital=candidates[0],
                match_type="none", ratio=best_ratio,
            ))
    return results


def _unique_path(directory: str, filename: str) -> str:
    """directory 안에서 겹치지 않는 경로를 돌려준다. (겹치면 _1, _2 …)"""
    dst = os.path.join(directory, filename)
    base, ext = Path(filename).stem, Path(filename).suffix
    counter = 1
    while os.path.exists(dst):
        dst = os.path.join(directory, f"{base}_{counter}{ext}")
        counter += 1
    return dst


def _move_file(photo_dir: str, filename: str, manager: str) -> str:
    """파일을 담당자 폴더로 옮기고, 실제로 저장된 파일명을 돌려준다."""
    target_dir = os.path.join(photo_dir, manager)
    os.makedirs(target_dir, exist_ok=True)
    src = os.path.join(photo_dir, filename)
    dst = _unique_path(target_dir, filename)
    shutil.move(src, dst)
    return os.path.basename(dst)


# ── 되돌리기 ─────────────────────────────────────────────────────────────────

UNDO_FILE = ".분류되돌리기.json"


def _undo_path(photo_dir: str) -> str:
    return os.path.join(photo_dir, UNDO_FILE)


def has_undo(photo_dir: str) -> bool:
    return os.path.isfile(_undo_path(photo_dir))


def _save_undo_log(photo_dir: str, moves: list[dict]) -> None:
    if not moves:
        return
    with open(_undo_path(photo_dir), "w", encoding="utf-8") as f:
        json.dump(moves, f, ensure_ascii=False, indent=1)


def undo_last_sort(photo_dir: str) -> tuple[int, list[str]]:
    """마지막 병원별 분류를 되돌린다. (되돌린 개수, 실패 메시지 목록)을 반환.

    이동 기록의 역순으로 파일을 사진 폴더로 되돌리고, 비게 된 담당자 폴더는 지운다.
    되돌린 뒤에는 기록 파일을 삭제한다.
    """
    with open(_undo_path(photo_dir), encoding="utf-8") as f:
        moves = json.load(f)

    restored = 0
    errors: list[str] = []
    folders: set[str] = set()
    for m in reversed(moves):
        folder = os.path.join(photo_dir, m["folder"])
        folders.add(folder)
        src = os.path.join(folder, m["stored"])
        if not os.path.isfile(src):
            errors.append(f"{m['folder']}\\{m['stored']} 파일을 찾을 수 없음")
            continue
        try:
            shutil.move(src, _unique_path(photo_dir, m["file"]))
            restored += 1
        except Exception as e:
            errors.append(f"{m['stored']}: {e}")

    for folder in folders:
        try:
            os.rmdir(folder)  # 비어 있을 때만 삭제됨
        except OSError:
            pass

    if not errors:
        os.remove(_undo_path(photo_dir))
    return restored, errors


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
    review: list[ReviewItem] = field(default_factory=list)  # summary 에서만 채워짐


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
    undo_moves: list[dict] = []
    review: list[ReviewItem] = []

    for r in results:
        if r.match_type == "none":
            skipped_count += 1
            review.append(ReviewItem(UNMATCHED, r.filename, f"추출된 거래처명: '{r.hospital}'"))
            emit(SortEvent(kind="skipped", filename=r.filename, hospital=r.hospital))
            continue

        stored = _move_file(photo_dir, r.filename, r.manager)
        undo_moves.append({"file": r.filename, "folder": r.manager, "stored": stored})
        if r.match_type == "exact":
            moved_exact += 1
        else:
            moved_fuzzy += 1
            review.append(ReviewItem(
                FUZZY, r.filename,
                f"'{r.hospital}' ≈ '{r.matched_key}' {int(r.ratio * 100)}% → [{r.manager}]"))
        emit(SortEvent(
            kind="moved",
            filename=r.filename, manager=r.manager, match_type=r.match_type,
            hospital=r.hospital, matched_key=r.matched_key, ratio=r.ratio,
        ))

    _save_undo_log(photo_dir, undo_moves)

    emit(SortEvent(
        kind="summary",
        moved_exact=moved_exact, moved_fuzzy=moved_fuzzy, skipped_count=skipped_count,
        review=review,
    ))

    return events
