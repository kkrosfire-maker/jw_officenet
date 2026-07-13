import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import openpyxl

from extractor import CompanyExtractor, CreditExhaustedError

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png"}


def _unique_path(dest: Path, name: str, suffix: str) -> Path:
    """name+suffix 파일이 dest에 이미 있으면 'name (2)suffix', 'name (3)suffix' ... 로 피함."""
    candidate = dest / (name + suffix)
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = dest / f"{name} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


@dataclass
class Result:
    original: str
    new_name: str | None
    error: str | None
    error_kind: Literal["mapping", "api"] | None = None

    @property
    def success(self) -> bool:
        return self.error is None


class ClinicMap:
    """엑셀 D열(변환전) → B열(병원명) 매핑. 병원 조회의 단일 진입점."""

    def __init__(self, mapping: dict[str, str], ambiguous: set[str]):
        self._mapping = mapping
        self._ambiguous = ambiguous

    @classmethod
    def from_excel(cls, excel_path: str) -> "ClinicMap":
        wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
        ws = wb.active
        mapping: dict[str, str] = {}
        ambiguous: set[str] = set()
        for row in ws.iter_rows(min_row=2, values_only=True):
            b_val = str(row[1]).strip() if row[1] is not None else ""
            d_val = str(row[3]).strip() if row[3] is not None else ""
            if b_val and d_val:
                if d_val in mapping and mapping[d_val] != b_val:
                    ambiguous.add(d_val)
                else:
                    mapping[d_val] = b_val
        return cls(mapping, ambiguous)

    def find(self, stem: str) -> tuple[str | None, str | None]:
        """파일명(확장자 제외) → (병원명, 에러메시지). 정확한 매칭 우선, 없으면 최장 prefix."""
        if stem in self._mapping:
            if stem in self._ambiguous:
                return None, f"엑셀 D열 중복: '{stem}' → 병원 특정 불가"
            return self._mapping[stem], None

        best_key = max(
            (k for k in self._mapping if stem.startswith(k)),
            key=len,
            default="",
        )
        if best_key:
            if best_key in self._ambiguous:
                return None, f"엑셀 D열 중복: '{best_key}' → 병원 특정 불가"
            return self._mapping[best_key], None

        return None, f"엑셀에 매핑 없음: '{stem}'"


class Renamer:
    def __init__(self, extractor: CompanyExtractor):
        self._extractor = extractor

    def rename(
        self,
        folder: Path,
        clinic_map: ClinicMap,
        month: str,
        output_folder: Path | None = None,
    ) -> list[Result]:
        dest = output_folder or folder
        files = sorted(
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS
        )
        results = []
        for photo in files:
            lookup_stem = re.sub(r'\s+\(\d+\)$', '', photo.stem)
            clinic, err = clinic_map.find(lookup_stem)
            if clinic is None:
                results.append(Result(photo.name, None, err, error_kind="mapping"))
                continue
            try:
                company = self._extractor.extract(photo)
                base_name = f"{clinic} {month} {company}"
                out_path = _unique_path(dest, base_name, photo.suffix)
                shutil.move(str(photo), str(out_path))
                results.append(Result(photo.name, out_path.name, None))
            except CreditExhaustedError:
                raise
            except Exception as e:
                results.append(Result(photo.name, None, str(e), error_kind="api"))
        return results
