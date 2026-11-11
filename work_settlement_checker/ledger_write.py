"""작업 엑셀(1.통계입력_yymm.xlsx)에 '통계이월'을 쓴다. 이 프로그램이 엑셀에 쓰는 유일한 곳.

규칙(work_photo_rename 의 입력완료 기록과 같은 방식):
  - 상태열(C)을 '통계이월'로, I열(입력완료·정산불가 때 1을 넣는 표시열)에 1.
  - 특이사항열(J)에 'mm월 통계 다음달로 이월' (mm = 그 줄의 처방월). 이미 적힌 메모는 지우지 않고 뒤에 덧붙인다.
  - 저장은 임시 파일에 먼저 쓰고 열리는지 확인한 뒤 원본과 바꾼다(저장 도중 실패해도 원본이 비지 않게).
  - 엑셀이 열려 있으면 파일을 바꿀 수 없으므로 아무것도 쓰지 않고 이유를 돌려준다.
"""
import re
from pathlib import Path

import openpyxl

import names
from ledger_read import CARRIED, DONE, _COLS, _HEAD

SHEET = "통계입력확인"


def month_label(rx_month, input_month):
    """특이사항에 적을 'mm월'. 처방월(예: '10월', '08월')을 쓰고, 비어 있으면 입력월의 지난달."""
    m = re.search(r"\d+", rx_month or "")
    if m:
        return f"{int(m.group())}월"
    m = re.search(r"\d+", input_month or "")
    if m:
        n = int(m.group())
        return f"{12 if n == 1 else n - 1}월"
    return ""


def note_text(old, label):
    new = f"{label} 통계 다음달로 이월" if label else "통계 다음달로 이월"
    old = (old or "").strip()
    if not old:
        return new
    return old if new in old else f"{old} / {new}"


def _save_safely(wb, path):
    path = Path(path)
    tmp = path.with_name(f"{path.stem}.저장중.tmp{path.suffix}")
    try:
        wb.save(tmp)
        if not tmp.stat().st_size > 1000:
            raise OSError("저장된 임시 파일이 비정상입니다")
        openpyxl.load_workbook(tmp, read_only=True).close()
        tmp.replace(path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def carry_over(path, month, manager, hospital, pharma):
    """입력월이 month월이고 (담당자·병원·제약사)가 같은 줄 중 아직 처리 안 된 줄을 통계이월로 바꾼다.
    반환: 바꾼 줄 수. 못 찾으면 0. 엑셀이 열려 있어 못 쓰면 PermissionError."""
    wb = openpyxl.load_workbook(path)                     # 수식·데이터검증 유지를 위해 read_only 아님
    try:
        ws = wb[SHEET] if SHEET in wb.sheetnames else wb.active
        col = {k: v + 1 for k, v in _COLS.items()}
        for i, h in enumerate([c.value for c in ws[1]], start=1):
            k = _HEAD.get(str(h).strip()) if h is not None else None
            if k:
                col[k] = i

        def text(r, k):
            v = ws.cell(r, col[k]).value
            return "" if v is None else str(v).strip()

        want, n = f"{month}월", 0
        for r in range(2, ws.max_row + 1):
            if (text(r, "input_month") != want or text(r, "manager") != manager or text(r, "hospital") != hospital
                    or names.norm(text(r, "pharma")) != names.norm(pharma) or text(r, "status") in DONE):
                continue
            ws.cell(r, col["status"]).value = CARRIED
            ws.cell(r, col["mark"]).value = 1
            ws.cell(r, col["note"]).value = note_text(text(r, "note"), month_label(text(r, "rx_month"), text(r, "input_month")))
            n += 1
        if n:
            wb.calculation.fullCalcOnLoad = True
            _save_safely(wb, path)
        return n
    finally:
        wb.close()
