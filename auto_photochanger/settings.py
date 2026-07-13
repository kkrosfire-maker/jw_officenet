import json
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

_PATH = BASE_DIR / "settings.json"


def load() -> dict:
    if _PATH.exists():
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"api_key": ""}


def save(data: dict) -> None:
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
