"""변경 이력 (data/change_log.csv).

앱에서 일어난 모든 변경을 남긴다: 요율표 승인, 마스터 편집, 검토 중 선택.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterable, Optional

from .config import CHANGE_LOG_PATH, ensure_dirs

FIELDS = ["일시", "구분", "보험코드", "제품명", "항목", "이전값", "새값", "사유", "적용EDI월"]


@dataclass
class LogEntry:
    구분: str                     # '요율표승인' | '마스터편집' | '검토선택' | '설정변경' | '초기화'
    항목: str
    보험코드: str = ""
    제품명: str = ""
    이전값: str = ""
    새값: str = ""
    사유: str = ""
    적용EDI월: str = ""           # 처방월 기준
    일시: str = ""

    def with_time(self) -> "LogEntry":
        if not self.일시:
            self.일시 = datetime.now().isoformat(timespec="seconds")
        return self


def append(entries: Iterable[LogEntry] | LogEntry) -> None:
    if isinstance(entries, LogEntry):
        entries = [entries]
    entries = [e.with_time() for e in entries]
    if not entries:
        return
    ensure_dirs()
    is_new = not CHANGE_LOG_PATH.exists()
    with CHANGE_LOG_PATH.open("a", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        for entry in entries:
            row = {k: ("" if v is None else str(v)) for k, v in asdict(entry).items()}
            writer.writerow({k: row.get(k, "") for k in FIELDS})


def read_all() -> list[dict]:
    if not CHANGE_LOG_PATH.exists():
        return []
    with CHANGE_LOG_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def log(
    구분: str,
    항목: str,
    *,
    보험코드: str = "",
    제품명: str = "",
    이전값=None,
    새값=None,
    사유: str = "",
    적용EDI월: str = "",
) -> None:
    append(
        LogEntry(
            구분=구분,
            항목=항목,
            보험코드=보험코드,
            제품명=제품명,
            이전값="" if 이전값 is None else str(이전값),
            새값="" if 새값 is None else str(새값),
            사유=사유,
            적용EDI월=적용EDI월,
        )
    )
