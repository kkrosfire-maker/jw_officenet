"""경로/설정 관리."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "genelis.db"
EXPORT_DIR = DATA_DIR / "exports"

SOURCE_MASTER_XLSX = Path(r"C:\Users\JW\Desktop\제너리스연신내점\01.제너리스_주문 최종.xlsx")
SOURCE_MASTER_SHEET = "품목별 단가"

# 매칭 후보 유사도 임계값
AUTO_MATCH_THRESHOLD = 0.92  # 1등 후보 점수가 이 이상이면 match_type을 "자동확인"으로 기록(후보 개수는 보지 않음)
CANDIDATE_THRESHOLD = 0.45   # 이 이상만 후보 리스트에 노출
MAX_CANDIDATES = 5

# 마스터 DB 가격 기준일자가 이만큼(일) 지나면 "가격 확인 필요" 경고
STALE_PRICE_DAYS = 60


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
