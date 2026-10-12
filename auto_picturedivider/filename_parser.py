"""사진 파일명 해석: '병원명 N월 제약사명[번호]' 규칙을 이 모듈 한 곳에서만 안다.

photo_sort(병원별 분류)와 pharma_zip(제약사별 폴더)는 파일명을 직접 쪼개지 않고
parse_filename() 결과만 사용한다.
"""
import re
from dataclasses import dataclass
from pathlib import Path

_MONTH_RE = re.compile(r"\d{1,2}월")
FALLBACK_PHARMA = "기타"


@dataclass(frozen=True)
class ParsedName:
    hospital_candidates: tuple[str, ...]  # 병원명 후보. 앞쪽일수록 우선 (괄호 포함 원문)
    pharma: str                           # (주)·기호·끝 번호가 제거된 제약사명, 없으면 "기타"

    @property
    def hospital(self) -> str:
        return self.hospital_candidates[0]


def _clean_pharma(raw: str) -> str:
    cleaned = re.sub(r"\(주\)", "", raw)
    cleaned = re.sub(r"[^가-힣a-zA-Z0-9]", "", cleaned)
    cleaned = re.sub(r"\d+$", "", cleaned)  # 끝 일련번호 제거 (안국약품2 → 안국약품)
    return cleaned.strip() or FALLBACK_PHARMA


def _unique(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(i for i in items if i))


def parse_filename(filename: str) -> ParsedName:
    stem = Path(filename).stem
    tokens = stem.split() or [stem]

    # 병원명 후보: 'N월' 앞부분 전체 → 첫 단어 → (공백 없는 '병원_제약사'면) _ 앞부분
    candidates: list[str] = []
    month_idx = next((i for i, t in enumerate(tokens) if i > 0 and _MONTH_RE.fullmatch(t)), None)
    if month_idx is not None:
        prefix = tokens[:month_idx]
        candidates += [" ".join(prefix), "".join(prefix)]
    first = tokens[0]
    candidates.append(first)
    if "_" in first:
        candidates.append(first.split("_")[0])

    # 제약사명: 마지막 단어. 공백 없이 '병원_제약사'로 붙은 경우만 _ 뒤를 쓴다
    # (공백이 있는 '코오롱제약_1' 같은 번호 접미사는 그대로 둔다)
    raw = tokens[-1]
    if len(tokens) == 1 and "_" in raw:
        raw = raw.rsplit("_", 1)[-1] or raw

    return ParsedName(hospital_candidates=_unique(candidates), pharma=_clean_pharma(raw))
