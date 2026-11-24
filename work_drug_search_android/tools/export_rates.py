"""요율표 엑셀 -> 앱 내장용 rates.json 변환.

사용법 (새 요율표를 받을 때마다 PC에서 한 번):
    python -X utf8 tools/export_rates.py "C:/.../지에스파마 요율표(26.12).xlsx"

결과: app/src/main/assets/rates.json  (그 다음 gradlew assembleDebug 로 APK 다시 빌드)
엑셀 읽기는 PC 검색기(work_drug_search/app/excel_utils.py)와 같은 코드를 쓴다.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PC_APP = os.path.normpath(os.path.join(HERE, "..", "..", "work_drug_search", "app"))
sys.path.insert(0, PC_APP)

from excel_utils import load_rate_sheet  # noqa: E402

OUT = os.path.normpath(
    os.path.join(HERE, "..", "app", "src", "main", "assets", "rates.json")
)

NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")


def num_or_text(v):
    """숫자(또는 숫자 문자열)는 숫자로, 그 외('-', '미정' 등)는 문자열 그대로, 없으면 None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 6) if not float(v).is_integer() else int(v)
    s = str(v).strip()
    if not s:
        return None
    if NUM_RE.match(s):
        f = float(s)
        return int(f) if f.is_integer() else f
    return s


def text(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    rows, _field_map, sheet = load_rate_sheet(path)

    m = re.search(r"\((\d{2}\.\d{2})", os.path.basename(path))
    version = m.group(1) if m else ""

    out_rows = []
    for r in rows:
        item = {
            "g": text(r.get("성분")),
            "k": text(r.get("보험코드")),
            "m": text(r.get("제약사명")),
            "p": text(r.get("제품명")),
            "r": text(r.get("대조의약품")),
            "a": num_or_text(r.get("약가")),
            "t": num_or_text(r.get("요율")),
            "n": text(r.get("비고")),
        }
        if r.get("_row_color"):
            item["x"] = 1  # 엑셀에서 빨간 글씨였던 행(정산불가 등)
        out_rows.append({k: v for k, v in item.items() if v is not None})

    data = {"version": version, "sheet": sheet, "rows": out_rows}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(out_rows)}행, 버전 {version!r} -> {OUT} ({os.path.getsize(OUT):,} bytes)")


if __name__ == "__main__":
    main()
