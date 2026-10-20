"""모든 데이터 파일은 exe(개발 중에는 프로젝트) 폴더 안에 둔다."""
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_FILE = BASE_DIR / "config.json"
MASTER_FILE = BASE_DIR / "송하인마스터.xlsx"
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "output"
BACKUP_DIR = BASE_DIR / "backup"
LOG_DIR = BASE_DIR / "logs"


def ensure_dirs():
    for d in (DOWNLOAD_DIR, OUTPUT_DIR, BACKUP_DIR, LOG_DIR):
        d.mkdir(exist_ok=True)
