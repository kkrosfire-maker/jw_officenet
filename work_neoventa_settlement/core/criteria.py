"""제약사·제품 기준 엑셀 (data/제약사_기준.xlsx) 과 바탕화면 복사본.

사람이 엑셀로 고치는 기준을 한 파일에 모은다.
- `제약사별 기준` 시트: 제약사별 최소 인정금액과 특성(제출 인정기간, 신규소액 정산기간, 조건)
- `제품마스터` 시트: 제품별 구간인센%·특별인센%·별칭·제외여부

앱은 data/ 의 파일을 쓰고, 바탕화면에 같은 파일을 복사해 둔다.
어느 쪽을 고쳐도 더 최근에 저장한 파일이 이긴다 (sync).
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

from .config import BACKUP_DIR, CRITERIA_DESKTOP_NAME, CRITERIA_PATH, ensure_dirs
from .utils import clean_str, desktop_dir, parse_threshold, to_number

SHEET_GUIDE = "안내"
SHEET_COMPANY = "제약사별 기준"
SHEET_PRODUCT = "제품마스터"
SHEET_ORDER = [SHEET_GUIDE, SHEET_COMPANY, SHEET_PRODUCT]

COMPANY_COLUMNS = [
    "제약사명",
    "최소 인정금액",
    "제출 인정기간",
    "신규소액 정산기간",
    "코드삭제·기타 조건",
    "마지막 수정 날짜",
    "확인 필요",
    "요율표 다른 표기",
]
LIST_SEP = " | "

# 인센티브(구간·특별)가 이 값을 넘으면 단위 실수로 본다 (0.3 = 30%).
MAX_INCENTIVE = 0.30

GUIDE_LINES = [
    "네오벤타 정산 기준 파일",
    "",
    "이 파일을 고치면 프로그램이 다음에 열 때 자동으로 읽어 갑니다. (프로그램의 '기준정보 관리' 탭에서 고쳐도 이 파일에 반영됩니다)",
    "",
    "[제약사별 기준]",
    "  - 최소 인정금액: '10만원', '25만원', '없음'처럼 적습니다. 숫자(100000)도 됩니다. 비워 두면 '모름'으로 보고 정산 때 물어봅니다.",
    "  - (병원 × 제약사) 금액 합계가 최소 인정금액보다 작으면 소액처로 처리합니다. '없음'이면 판정하지 않습니다.",
    "  - 제출 인정기간 / 신규소액 정산기간 / 코드삭제·기타 조건: 참고용 메모입니다. 계산에는 쓰지 않습니다.",
    "  - 확인 필요: Y 로 적으면 정산 때마다 금액을 다시 확인하게 합니다.",
    "  - 요율표 다른 표기: 요율표에 이 제약사가 다른 이름으로 나올 때 ' | ' 로 구분해 적습니다. (예: 대웅바이오(CNE) | 대웅바이오(CNS))",
    "",
    "[제품마스터]",
    "  - 구간인센%, 특별인센%: 소수로 적습니다. 4.5% 는 0.045 (셀 서식이 % 면 4.5% 라고 입력해도 됩니다). 30% 를 넘으면 단위 실수로 보고 정산을 막습니다.",
    "  - 제외여부: Y 이면 정산에서 제외합니다.",
    "  - 보험코드, 최종제품명, lawdata약제명별칭은 매칭에 쓰이니 함부로 지우지 마세요.",
    "",
    "[주의]",
    "  - 엑셀로 이 파일을 열어 둔 채 프로그램에서 저장하면 바탕화면 복사본이 갱신되지 않을 수 있습니다. 엑셀을 닫고 저장하세요.",
    "  - 과거 월 정산 결과는 바뀌지 않습니다. 고친 값은 앞으로 하는 정산에만 적용됩니다.",
]


# ---------------------------------------------------------------- 통합문서 열기/시트 교체

def open_for_write(path: str | Path) -> openpyxl.Workbook:
    """기존 기준 엑셀이 있으면 열고(다른 시트 보존), 없으면 새로 만든다."""
    path = Path(path)
    if path.exists():
        return openpyxl.load_workbook(path)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    return wb


def replace_sheet(wb: openpyxl.Workbook, title: str):
    """같은 이름의 시트를 비운 새 시트로 바꾼다. 위치는 유지한다."""
    if title in wb.sheetnames:
        index = wb.sheetnames.index(title)
        wb.remove(wb[title])
        ws = wb.create_sheet(title, index)
    else:
        ws = wb.create_sheet(title)
    return ws


def finish_workbook(wb: openpyxl.Workbook) -> None:
    """안내 시트를 맨 앞에 두고 시트 순서를 정리한다."""
    if SHEET_GUIDE not in wb.sheetnames:
        ws = wb.create_sheet(SHEET_GUIDE)
        for line in GUIDE_LINES:
            ws.append([line])
        ws["A1"].font = Font(bold=True, size=14)
        ws.column_dimensions["A"].width = 130
    order = {name: i for i, name in enumerate(SHEET_ORDER)}
    wb._sheets.sort(key=lambda s: order.get(s.title, len(order)))
    wb.active = 0


# ---------------------------------------------------------------- 제약사별 기준 시트

def _amount_text(entry: dict) -> Optional[str]:
    """시트에 적을 최소 인정금액 문구."""
    raw = clean_str(entry.get("raw"))
    value = entry.get("value")
    if raw:
        return raw
    if value is None:
        return None if entry.get("needs_input") else "없음"
    return f"{int(value) // 10_000}만원" if int(value) % 10_000 == 0 else f"{int(value):,}원"


def format_amount(value: Optional[int]) -> str:
    """금액을 시트에 적는 문구로: 100000 → '10만원', None → '없음'."""
    if value is None:
        return "없음"
    value = int(value)
    return f"{value // 10_000}만원" if value % 10_000 == 0 else f"{value:,}원"


def read_thresholds(path: str | Path = CRITERIA_PATH) -> Optional[dict[str, dict]]:
    """`제약사별 기준` 시트를 읽는다. 파일이나 시트가 없으면 None."""
    path = Path(path)
    if not path.exists():
        return None
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        if SHEET_COMPANY not in wb.sheetnames:
            return None
        ws = wb[SHEET_COMPANY]
        rows = ws.iter_rows(min_row=1, values_only=True)
        header = [clean_str(h) for h in (next(rows, ()) or ())]
        index = {name: i for i, name in enumerate(header) if name}
        if "제약사명" not in index or "최소 인정금액" not in index:
            return None

        def get(row, name):
            i = index.get(name)
            return row[i] if i is not None and i < len(row) else None

        result: dict[str, dict] = {}
        for row in rows:
            name = clean_str(get(row, "제약사명"))
            if not name:
                continue
            cell = get(row, "최소 인정금액")
            if cell is None or clean_str(cell) == "":
                value, raw, needs = None, "", True        # 비어 있으면 모름
            elif isinstance(cell, (int, float)):
                value, raw, needs = int(cell), f"{int(cell):,}원", False
            else:
                raw = clean_str(cell)
                value, needs = parse_threshold(raw)
                needs = False if (value is not None or raw in ("없음", "-")) else needs
            if clean_str(get(row, "확인 필요")).upper() in ("Y", "O", "예", "TRUE", "1"):
                needs = True
            alt_text = clean_str(get(row, "요율표 다른 표기"))
            modified = get(row, "마지막 수정 날짜")
            if hasattr(modified, "strftime"):
                modified = modified.strftime("%Y-%m-%d")
            result[name] = {
                "value": value,
                "raw": raw,
                "needs_input": needs,
                "submit": clean_str(get(row, "제출 인정기간")),
                "new_small": clean_str(get(row, "신규소액 정산기간")),
                "conditions": clean_str(get(row, "코드삭제·기타 조건")),
                "modified": clean_str(modified),
                "alt": [a.strip() for a in alt_text.split("|") if a.strip()],
            }
        return result
    finally:
        wb.close()


def write_thresholds(thresholds: dict[str, dict], path: str | Path = CRITERIA_PATH) -> None:
    """`제약사별 기준` 시트를 통째로 다시 쓴다. 다른 시트는 그대로 둔다."""
    path = Path(path)
    wb = open_for_write(path)
    try:
        ws = replace_sheet(wb, SHEET_COMPANY)
        ws.append(COMPANY_COLUMNS)
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DDEBF7")
        for name in sorted(thresholds):
            entry = thresholds[name] or {}
            ws.append(
                [
                    name,
                    _amount_text(entry),
                    entry.get("submit") or None,
                    entry.get("new_small") or None,
                    entry.get("conditions") or None,
                    entry.get("modified") or None,
                    "Y" if entry.get("needs_input") else None,
                    LIST_SEP.join(entry.get("alt") or []) or None,
                ]
            )
        for i, width in enumerate([26, 16, 14, 16, 70, 16, 10, 40], start=1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width
        for row in ws.iter_rows(min_row=2, min_col=5, max_col=5):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions
        finish_workbook(wb)
        ensure_dirs()
        wb.save(path)
    finally:
        wb.close()


# ---------------------------------------------------------------- 검증

def incentive_problems(master) -> list[str]:
    """구간·특별 인센티브가 비정상(음수이거나 30% 초과)인 제품 설명."""
    problems = []
    for product in master.products:
        for label, value in (("구간인센", product.구간인센), ("특별인센", product.특별인센)):
            if value is not None and (value < 0 or value > MAX_INCENTIVE):
                problems.append(
                    f"{product.최종제품명} ({product.code_display}): {label} {value * 100:g}% "
                    f"— 0~{MAX_INCENTIVE * 100:g}% 를 벗어났습니다. 단위(5% 는 0.05)를 확인하세요."
                )
    return problems


def check_incentive_value(value) -> Optional[str]:
    """화면에서 입력받은 인센티브(소수)가 이상하면 이유를 돌려준다."""
    number = to_number(value)
    if number is None:
        return None
    if number < 0 or number > MAX_INCENTIVE:
        return f"{number * 100:g}% 는 허용 범위(0~{MAX_INCENTIVE * 100:g}%)를 벗어났습니다."
    return None


# ---------------------------------------------------------------- 바탕화면 복사본

@dataclass
class SyncResult:
    action: str          # none | published | imported | locked | invalid | missing
    message: str = ""

    @property
    def imported(self) -> bool:
        return self.action == "imported"


def desktop_path(desktop: Optional[Path] = None) -> Path:
    return (Path(desktop) if desktop else desktop_dir()) / CRITERIA_DESKTOP_NAME


def _snapshot(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, target)
    return target


def _is_valid(path: Path) -> bool:
    try:
        wb = openpyxl.load_workbook(path, read_only=True)
        try:
            return SHEET_COMPANY in wb.sheetnames and SHEET_PRODUCT in wb.sheetnames
        finally:
            wb.close()
    except Exception:  # noqa: BLE001 - 깨졌거나 열려 있는 파일
        return False


def sync(data_path: str | Path = CRITERIA_PATH, desktop: Optional[Path] = None) -> SyncResult:
    """data/ 파일과 바탕화면 복사본 중 더 최근에 저장한 쪽을 반대편에 맞춘다."""
    data_path = Path(data_path)
    if not data_path.exists():
        return SyncResult("missing", "기준 엑셀(data/제약사_기준.xlsx)이 없습니다.")
    target = desktop_path(desktop)
    try:
        if not target.exists():
            shutil.copy2(data_path, target)
            return SyncResult("published", f"바탕화면에 기준 엑셀을 만들었습니다: {target.name}")

        desk_time, data_time = target.stat().st_mtime, data_path.stat().st_mtime
        if abs(desk_time - data_time) < 0.5:
            return SyncResult("none")
        if desk_time > data_time:
            if not _is_valid(target):
                return SyncResult(
                    "invalid",
                    f"바탕화면 {target.name} 을 읽지 못했습니다 (시트 '{SHEET_COMPANY}'·'{SHEET_PRODUCT}' 필요). "
                    "기존 기준을 그대로 씁니다.",
                )
            _snapshot(data_path)
            shutil.copy2(target, data_path)
            return SyncResult("imported", f"바탕화면 {target.name} 의 수정 내용을 가져왔습니다.")
        shutil.copy2(data_path, target)
        return SyncResult("published", f"바탕화면 {target.name} 을 최신으로 갱신했습니다.")
    except PermissionError:
        return SyncResult(
            "locked",
            f"바탕화면 {target.name} 이 엑셀에서 열려 있어 갱신하지 못했습니다. 엑셀을 닫으면 다음에 맞춰집니다.",
        )
    except OSError as error:
        return SyncResult("locked", f"바탕화면 복사본을 맞추지 못했습니다: {error}")
