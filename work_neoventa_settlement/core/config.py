"""경로와 상수."""
from __future__ import annotations

import sys
from pathlib import Path


def _app_dir() -> Path:
    """기준정보(data/)를 둘 폴더.

    EXE 로 묶었을 때는 exe 가 있는 폴더를 쓴다. PyInstaller 는 번들 파일을
    `_internal/` 안에 풀어놓는데, 거기에 data/ 를 만들면 사용자가 찾기 어렵다.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_dir() -> Path:
    """app.py, pages/ 등 번들된 파일이 있는 폴더 (개발 중에는 프로젝트 폴더)."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else Path(__file__).resolve().parent.parent


APP_DIR = _app_dir()
DATA_DIR = APP_DIR / "data"
RATE_TABLE_DIR = DATA_DIR / "rate_tables"
BACKUP_DIR = DATA_DIR / "backup"
SAMPLES_DIR = APP_DIR / "samples"
UPLOAD_DIR = DATA_DIR / "uploads"

PRODUCT_MASTER_PATH = DATA_DIR / "product_master.xlsx"
SETTINGS_PATH = DATA_DIR / "settings.json"
CHANGE_LOG_PATH = DATA_DIR / "change_log.csv"
RATE_TABLE_INDEX_PATH = RATE_TABLE_DIR / "index.json"

# 최종 엑셀
FINAL_DETAIL_SHEET = "2026년 거래처별 세부내역"
FINAL_TABLE_NAME = "DB"
FINAL_HEADER_ROW = 7
FINAL_SUMMARY_SHEET = "종합"
FINAL_SUMMARY_ISSUE_CELL = "B18"
FINAL_PIVOT_SHEET = "제약사별 매출현황"

# 요율표
RATE_SHEET_NAME = "제품별 수수료"
RATE_HEADER_ROW = 2
PROMO_SHEET_NAME = "제약사별 프로모션"
PROMO_HEADER_ROW = 1

# lawdata
LAWDATA_HEADER_ROW = 1

VENDOR_NAME = "네오벤타㈜"
SETTLEMENT_FEE = 0.01  # 정산수수료 1%

# 최종 DB 표 컬럼 순서 (A~S)
DB_COLUMNS = [
    "수탁업체명", "처방월", "정산월", "사업자번호", "병원명", "제약사", "제약사\n구분",
    "제품명", "단가", "수량", "금액", "제약사\n수수료%", "제약사\n구간인센%",
    "제약사\n특별인센%", "최종요율", "확정금액", "비고(품절 및 공지사항)", "정책1", "정산내역확인",
]


def ensure_dirs() -> None:
    for d in (DATA_DIR, RATE_TABLE_DIR, BACKUP_DIR):
        d.mkdir(parents=True, exist_ok=True)
