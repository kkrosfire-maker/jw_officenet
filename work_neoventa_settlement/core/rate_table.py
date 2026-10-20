"""요율표 로딩, 버전 보관, 버전 간 비교.

요율표가 약가·요율·구분·제약사명·비고의 기준이다.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

import openpyxl

from .config import (
    PROMO_HEADER_ROW,
    PROMO_SHEET_NAME,
    RATE_HEADER_ROW,
    RATE_SHEET_NAME,
    RATE_TABLE_DIR,
    RATE_TABLE_INDEX_PATH,
    ensure_dirs,
)
from .utils import clean_str, code_key, to_number

RATE_COLUMNS = ["보험코드", "구분", "제약사명", "제품명", "약가", "요율", "비고"]
COMPARE_FIELDS = ["약가", "요율", "구분", "제약사명", "비고"]


class RateTableError(RuntimeError):
    pass


@dataclass(frozen=True)
class RateEntry:
    보험코드: str
    구분: object          # 3, 2, '유니' 등. 그대로 보관한다.
    제약사명: str
    제품명: str
    약가: Optional[float]
    요율: Optional[float]
    비고: str
    row: int = 0          # 요율표 엑셀 행 번호 (중복 코드 구분용)

    def value(self, field_name: str):
        return getattr(self, field_name)


@dataclass
class RateTable:
    path: Path
    entries: dict[str, list[RateEntry]] = field(default_factory=dict)
    promotions: dict[str, list[str]] = field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return sum(len(v) for v in self.entries.values())

    def get(self, code: str) -> list[RateEntry]:
        return self.entries.get(code_key(code), [])

    def first(self, code: str) -> Optional[RateEntry]:
        rows = self.get(code)
        return rows[0] if rows else None

    def duplicated_codes(self) -> list[str]:
        return [c for c, v in self.entries.items() if len(v) > 1]

    def promotion(self, code: str) -> list[str]:
        return self.promotions.get(code_key(code), [])


def _header_index(row: Iterable, wanted: list[str]) -> dict[str, int]:
    index: dict[str, int] = {}
    for i, value in enumerate(row):
        name = clean_str(value)
        if name in wanted and name not in index:
            index[name] = i
    return index


def load_rate_table(path: str | Path) -> RateTable:
    path = Path(path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if RATE_SHEET_NAME not in wb.sheetnames:
            raise RateTableError(
                f"[{RATE_SHEET_NAME}] 시트가 없습니다. 있는 시트: {wb.sheetnames}"
            )
        ws = wb[RATE_SHEET_NAME]
        rows = ws.iter_rows(min_row=RATE_HEADER_ROW, values_only=True)
        header = next(rows, None)
        if header is None:
            raise RateTableError("요율표가 비어 있습니다.")
        index = _header_index(header, RATE_COLUMNS)
        missing = [c for c in RATE_COLUMNS if c not in index]
        if missing:
            raise RateTableError(f"요율표에 없는 컬럼: {missing}")

        def cell(row, name):
            i = index[name]
            return row[i] if i < len(row) else None

        table = RateTable(path=path)
        for offset, row in enumerate(rows, start=RATE_HEADER_ROW + 1):
            code = code_key(cell(row, "보험코드"))
            if not code:
                continue
            entry = RateEntry(
                보험코드=code,
                구분=cell(row, "구분"),
                제약사명=clean_str(cell(row, "제약사명")),
                제품명=clean_str(cell(row, "제품명")),
                약가=to_number(cell(row, "약가")),
                요율=to_number(cell(row, "요율")),
                비고=clean_str(cell(row, "비고")),
                row=offset,
            )
            table.entries.setdefault(code, []).append(entry)

        if PROMO_SHEET_NAME in wb.sheetnames:
            pws = wb[PROMO_SHEET_NAME]
            prows = pws.iter_rows(min_row=PROMO_HEADER_ROW, values_only=True)
            pheader = next(prows, None) or ()
            pindex = _header_index(pheader, ["보험코드", "프로모션"])
            if "보험코드" in pindex and "프로모션" in pindex:
                ci, ti = pindex["보험코드"], pindex["프로모션"]
                for row in prows:
                    code = code_key(row[ci] if ci < len(row) else None)
                    text = clean_str(row[ti] if ti < len(row) else None)
                    if code and text:
                        table.promotions.setdefault(code, []).append(text)
        return table
    finally:
        wb.close()


# ---------------------------------------------------------------- 버전 관리

@dataclass
class RateVersion:
    file: str
    label: str
    added: str
    approved: bool
    source_name: str = ""   # 사용자가 올린 원본 파일 이름

    @property
    def path(self) -> Path:
        return RATE_TABLE_DIR / self.file

    @property
    def title(self) -> str:
        """화면에 보여줄 이름. 올린 파일 제목을 그대로 쓴다."""
        if self.source_name:
            return Path(self.source_name).stem
        return self.label or Path(self.file).stem


def _read_index() -> list[dict]:
    if not RATE_TABLE_INDEX_PATH.exists():
        return []
    return json.loads(RATE_TABLE_INDEX_PATH.read_text(encoding="utf-8"))


def _write_index(items: list[dict]) -> None:
    ensure_dirs()
    RATE_TABLE_INDEX_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_versions() -> list[RateVersion]:
    fields = {"file", "label", "added", "approved", "source_name"}
    return [RateVersion(**{k: v for k, v in item.items() if k in fields}) for item in _read_index()]


def current_version() -> Optional[RateVersion]:
    """가장 최근에 승인한 버전이 현재 요율표다."""
    approved = [v for v in list_versions() if v.approved]
    return approved[-1] if approved else None


def pending_version() -> Optional[RateVersion]:
    """승인 대기 중인(가장 마지막) 버전."""
    versions = list_versions()
    if versions and not versions[-1].approved:
        return versions[-1]
    return None


def load_current() -> Optional[RateTable]:
    version = current_version()
    return load_rate_table(version.path) if version else None


def add_version(src: str | Path, label: str = "", approved: bool = False) -> RateVersion:
    """새 요율표 파일을 data/rate_tables/ 에 복사해 버전으로 등록한다."""
    ensure_dirs()
    src = Path(src)
    load_rate_table(src)  # 형식 검증 먼저
    stamp = date.today().isoformat()
    target = RATE_TABLE_DIR / f"요율표_{stamp}.xlsx"
    suffix = 2
    while target.exists():
        target = RATE_TABLE_DIR / f"요율표_{stamp}_{suffix}.xlsx"
        suffix += 1
    shutil.copy2(src, target)
    version = RateVersion(
        file=target.name,
        label=label or src.stem,
        added=datetime.now().isoformat(timespec="seconds"),
        approved=approved,
        source_name=src.name,
    )
    items = _read_index()
    items.append(vars(version))
    _write_index(items)
    return version


def approve_version(file_name: str) -> None:
    items = _read_index()
    for item in items:
        if item["file"] == file_name:
            item["approved"] = True
    _write_index(items)


def drop_version(file_name: str) -> None:
    items = [i for i in _read_index() if i["file"] != file_name]
    _write_index(items)
    target = RATE_TABLE_DIR / file_name
    if target.exists():
        target.unlink()


# ---------------------------------------------------------------- 버전 비교

@dataclass
class RateDiff:
    보험코드: str
    제품명: str
    항목: str            # 약가 | 요율 | 구분 | 제약사명 | 비고 | 추가 | 삭제
    이전값: object
    새값: object

    @property
    def key(self) -> str:
        return f"{self.보험코드}|{self.항목}"


def compare(old: RateTable, new: RateTable, codes: Iterable[str]) -> list[RateDiff]:
    """우리 제품 코드만 비교한다(요율표 전체 11,000행이 아님)."""
    diffs: list[RateDiff] = []
    for code in sorted({code_key(c) for c in codes if code_key(c)}):
        old_entry = old.first(code)
        new_entry = new.first(code)
        if old_entry is None and new_entry is None:
            continue
        if new_entry is None:
            diffs.append(RateDiff(code, old_entry.제품명, "삭제", old_entry.제품명, None))
            continue
        if old_entry is None:
            diffs.append(RateDiff(code, new_entry.제품명, "추가", None, new_entry.제품명))
            continue
        for field_name in COMPARE_FIELDS:
            before, after = old_entry.value(field_name), new_entry.value(field_name)
            if before != after:
                diffs.append(RateDiff(code, new_entry.제품명, field_name, before, after))
    return diffs
