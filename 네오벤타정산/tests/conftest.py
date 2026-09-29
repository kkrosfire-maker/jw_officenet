"""테스트 공통 준비.

요율표는 samples/ 에 넣어두거나 환경변수 NV_RATE_TABLE 로 경로를 준다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SAMPLES = ROOT / "samples"
LAWDATA = SAMPLES / "lawdata.xlsx"
CONVERSION = SAMPLES / "변환엑셀.xlsx"
FINAL = SAMPLES / "최종엑셀.xlsx"

SETTLEMENT_MONTH = "2026-09"
SETTLEMENT_SHEET = "9월"


def find_rate_table() -> Path | None:
    env = os.environ.get("NV_RATE_TABLE")
    if env and Path(env).exists():
        return Path(env)
    for pattern in ("*요율표*.xlsx", "*요율*.xlsx"):
        hits = sorted(SAMPLES.glob(pattern))
        if hits:
            return hits[-1]
    return None


def require_sample(path: Path, what: str) -> Path:
    """샘플 파일이 없으면 테스트를 건너뛴다.

    samples/ 의 엑셀은 실제 거래 자료라 저장소에 올리지 않는다. 받아서 쓰려면
    samples/ 폴더에 직접 넣어야 한다.
    """
    if not path.exists():
        pytest.skip(
            f"{what} 가 없습니다: {path}\n"
            "samples/ 의 엑셀은 실제 거래 자료라 저장소에 포함되지 않습니다. "
            "직접 넣은 뒤 다시 실행하세요."
        )
    return path


@pytest.fixture(scope="session", autouse=True)
def _sample_files() -> None:
    require_sample(LAWDATA, "lawdata 샘플")
    require_sample(CONVERSION, "변환엑셀 샘플")
    require_sample(FINAL, "최종엑셀 샘플")


@pytest.fixture(scope="session")
def rate_table_path() -> Path:
    path = find_rate_table()
    if path is None:
        pytest.skip(
            "요율표 파일이 없습니다. samples/ 에 '정원유니어스 요율표 ...xlsx' 를 넣거나 "
            "환경변수 NV_RATE_TABLE 에 경로를 지정하세요."
        )
    return path


@pytest.fixture(scope="session")
def rate_table(rate_table_path):
    from core.rate_table import load_rate_table

    return load_rate_table(rate_table_path)


@pytest.fixture(scope="session")
def init_result(rate_table):
    """제품 마스터 초기화 결과. data/ 를 건드리지 않는다."""
    from core import master as master_mod

    return master_mod.initialize(
        conversion_path=CONVERSION, lawdata_path=LAWDATA, rate_table=rate_table
    )


@pytest.fixture(scope="session")
def final_db():
    from core.final_db import load_final_db

    return load_final_db(FINAL)


@pytest.fixture()
def ctx(init_result, rate_table, final_db):
    """테스트가 마스터·설정을 고쳐도 다른 테스트에 번지지 않게 사본을 준다."""
    import copy

    from core.converter import ConvertContext

    return ConvertContext(
        master=copy.deepcopy(init_result.master),
        settings=copy.deepcopy(init_result.settings),
        rate_table=rate_table,
        final_db=final_db,
    )


@pytest.fixture()
def law_rows_september():
    from core import lawdata

    return lawdata.load_settlement(LAWDATA, SETTLEMENT_SHEET, SETTLEMENT_MONTH)


@pytest.fixture()
def resolved_result(ctx, law_rows_september):
    """9월 정산분을 모두 검토 처리한 결과 (단가는 요율표, 제한 행은 포함)."""
    from core import converter as conv

    decisions = {conv.DUPLICATE_MONTH: {"action": "replace"}}
    first = conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH, decisions)
    for issue in first.issues:
        if issue.code == conv.PRICE_MISMATCH:
            decisions[issue.key] = {"choice": "rate"}
        elif issue.code == conv.NOTE_RESTRICTION:
            decisions[issue.key] = {"include": True}
        elif issue.code == conv.VALUE_CHANGED:
            decisions[issue.key] = {"confirmed": True}
    return conv.convert(law_rows_september, ctx, SETTLEMENT_MONTH, decisions)
