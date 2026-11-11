"""저장 모듈 — 월별 마감일정·별칭·설정을 %APPDATA%\\settlement_checker 에 JSON으로 보관한다.
(테스트는 환경변수 SETTLEMENT_CHECKER_DIR 로 폴더를 바꾼다.)
"""
import json
import os
import shutil
from pathlib import Path

from schedule import Deadline


def data_dir():
    d = Path(os.environ.get("SETTLEMENT_CHECKER_DIR") or Path(os.environ.get("APPDATA", ".")) / "settlement_checker")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(name, default):
    try:
        return json.loads((data_dir() / name).read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(name, obj):
    p = data_dir() / name
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _month_file(year, month):
    return f"deadlines_{year % 100:02d}{month:02d}.json"


def save_source_image(year, month, src):
    """불러온 마감표 이미지를 월별로 복사해 둔다(원본을 옮기거나 지워도 '마감표 이미지 내보내기'가 되도록). 복사본 경로를 돌려준다."""
    src = Path(src)
    dst = data_dir() / f"schedule_{year % 100:02d}{month:02d}{src.suffix.lower()}"
    for old in data_dir().glob(f"schedule_{year % 100:02d}{month:02d}.*"):
        if old != dst:
            old.unlink(missing_ok=True)
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)
    return str(dst)


def source_image(year, month):
    """그 달 마감표 이미지 경로(복사본 우선, 없으면 가져올 때 적어 둔 원래 경로). 없으면 None."""
    for p in sorted(data_dir().glob(f"schedule_{year % 100:02d}{month:02d}.*")):
        return str(p)
    d = _read(_month_file(year, month), None)
    s = d and d.get("source")
    return s if s and Path(s).exists() else None


def save_month(year, month, deadlines, source=""):
    _write(_month_file(year, month), dict(year=year, month=month, source=source,
                                          deadlines=[d.to_json() for d in deadlines]))


def load_month(year, month):
    o = _read(_month_file(year, month), None)
    return None if o is None else [Deadline.from_json(d) for d in o.get("deadlines", [])]


def saved_months():
    out = []
    for p in sorted(data_dir().glob("deadlines_*.json")):
        o = _read(p.name, {})
        if "year" in o:
            out.append((o["year"], o["month"]))
    return out


def load_aliases():
    return _read("aliases.json", {})


def save_alias(raw_norm, pharma):
    a = load_aliases()
    a[raw_norm] = pharma
    _write("aliases.json", a)


def load_config():
    return _read("config.json", {})


def save_config(cfg):
    _write("config.json", cfg)
