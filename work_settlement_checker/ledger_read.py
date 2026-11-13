"""작업 엑셀(1.통계입력_yymm.xlsx)에서 이번 달 입력 대상 줄을 읽는다. 읽기 전용.

열 위치는 work_photo_rename과 같다: 연도·담당자명·상태·거래처명·처방월·입력월·제약사명.
상태가 입력완료·통계없음·정산불가면 처리된 줄, 빈칸이면 미처리.
"""
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import openpyxl

CARRIED = "통계이월"                   # 이번 달에 통계를 내지 않고 다음 달로 넘긴 줄
NO_STATS = "통계없음"                 # 이번 달 통계 자료가 없는 줄
DONE = ("입력완료", NO_STATS, "정산불가", CARRIED)
_COLS = dict(year=0, manager=1, status=2, hospital=3, rx_month=4, input_month=5, pharma=6, mark=8, note=9)
_HEAD = {"연도": "year", "담당자명": "manager", "거래처명": "hospital", "처방월": "rx_month", "입력월": "input_month", "제약사명": "pharma", "특이사항": "note"}


@dataclass
class Row:
    manager: str
    hospital: str
    pharma: str
    status: str
    rx_month: str = ""

    @property
    def done(self):
        return self.status in DONE


def find_work_file(year, month, extra_dirs=()):
    """`1.통계입력_yymm.xlsx` 를 사진 프로그램 저장 폴더 등에서 찾는다. 없으면 None."""
    fname = f"1.통계입력_{year % 100:02d}{month:02d}.xlsx"
    dirs = list(extra_dirs)
    cfg = Path(os.environ.get("APPDATA", "")) / "photo_rename" / "config.json"
    try:
        d = json.loads(cfg.read_text(encoding="utf-8")).get("out_dir")
        if d:
            dirs.append(d)
    except Exception:
        pass
    for d in dirs:
        p = Path(d) / fname
        if p.exists():
            return p
    return None


def read_rows(path, month):
    """입력월이 `month`월인 줄들. 엑셀이 열려 있어도 읽히도록 임시 복사본을 읽는다."""
    tmp = Path(tempfile.mkdtemp()) / "w.xlsx"
    shutil.copy2(path, tmp)
    try:
        wb = openpyxl.load_workbook(tmp, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        it = ws.iter_rows(values_only=True)
        head = next(it, ())
        cols = dict(_COLS)
        for i, h in enumerate(head):
            k = _HEAD.get(str(h).strip()) if h is not None else None
            if k:
                cols[k] = i
        want = f"{month}월"
        out = []
        for r in it:
            def g(k):
                i = cols[k]
                v = r[i] if i < len(r) else None
                return "" if v is None else str(v).strip()
            if g("input_month") != want or not g("pharma"):
                continue
            out.append(Row(g("manager"), g("hospital"), g("pharma"), g("status"), g("rx_month")))
        wb.close()
        return out
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
