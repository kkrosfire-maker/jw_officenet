"""수탁업체명 자동 변환 프로그램 - 핵심 변환 로직 (순수 함수 위주)

PRD.md 참고. GUI 없이 이 모듈만으로 커맨드라인 검증이 가능하도록 구성한다.
"""
from __future__ import annotations

import difflib
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import openpyxl
import xlwings as xw

TARGET_SHEET_INDEX = 2  # 0-based -> 3번째 탭
TARGET_HEADER_ROW = 9
TARGET_DATA_START_ROW = 10
COL_B_수탁업체명 = 2
COL_E_사업자번호 = 5
COL_F_병원명 = 6
COL_I_제품명 = 9

EXPECTED_HEADERS = {
    COL_B_수탁업체명: "수탁업체명",
    COL_E_사업자번호: "사업자번호",
    COL_F_병원명: "병원명",
    COL_I_제품명: "제품명",
}

REF_SHEET_거래처별담당자 = "거래처별 담당자"
REF_SHEET_윤병옥내과 = "윤병옥내과"
REF_거래처_HEADER_ROW = 2
REF_거래처_DATA_START_ROW = 3
REF_윤병옥_HEADER_ROW = 2
REF_윤병옥_DATA_START_ROW = 3

YB_HOSPITAL_MARKERS = ("윤병옥내과의원", "윤병옥내과")

_PAREN_PATTERN = re.compile(r"\([^()]*\)(-\S*)?")


def normalize_biz_no(value) -> str:
    """사업자번호에서 숫자만 남긴다."""
    return re.sub(r"\D", "", str(value or ""))


def is_yb_hospital(hospital_name) -> bool:
    name = str(hospital_name or "")
    return any(marker in name for marker in YB_HOSPITAL_MARKERS)


def strip_product_name(value) -> str:
    """제품명에서 괄호(및 공백 없이 붙은 하이픈 꼬리표)를 제거한다. (§4.4)"""
    text = str(value or "")
    text = _PAREN_PATTERN.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class ReferenceFormatError(ValueError):
    pass


class TargetFormatError(ValueError):
    pass


class ExcelNotAvailableError(RuntimeError):
    pass


@dataclass
class ReferenceData:
    path: Path
    biz_map: dict = field(default_factory=dict)  # normalized biz_no -> 담당자
    product_map: dict = field(default_factory=dict)  # 품목 원문 -> 담당자
    biz_last_row: int = 0  # 거래처별 담당자 탭의 마지막 데이터 행
    product_last_row: int = 0  # 윤병옥내과 탭의 마지막 데이터 행
    pending_biz_rows: list = field(default_factory=list)  # [(사업자번호, 거래처명, 담당자), ...]
    pending_product_rows: list = field(default_factory=list)  # [(품목, 담당자), ...]


def load_reference(path: str | Path) -> ReferenceData:
    path = Path(path)
    wb = openpyxl.load_workbook(path)

    if REF_SHEET_거래처별담당자 not in wb.sheetnames:
        raise ReferenceFormatError(f"기준엑셀에 '{REF_SHEET_거래처별담당자}' 탭이 없습니다.")
    if REF_SHEET_윤병옥내과 not in wb.sheetnames:
        raise ReferenceFormatError(f"기준엑셀에 '{REF_SHEET_윤병옥내과}' 탭이 없습니다.")

    ref = ReferenceData(path=path)

    ws1 = wb[REF_SHEET_거래처별담당자]
    row = REF_거래처_DATA_START_ROW
    while True:
        biz_no = ws1.cell(row=row, column=1).value
        manager = ws1.cell(row=row, column=3).value
        if biz_no is None and manager is None:
            break
        if biz_no is not None and manager is not None:
            ref.biz_map[normalize_biz_no(biz_no)] = str(manager).strip()
        row += 1
    ref.biz_last_row = row - 1

    ws2 = wb[REF_SHEET_윤병옥내과]
    row = REF_윤병옥_DATA_START_ROW
    while True:
        product = ws2.cell(row=row, column=1).value
        manager = ws2.cell(row=row, column=2).value
        if product is None and manager is None:
            break
        if product is not None and manager is not None:
            ref.product_map[str(product)] = str(manager).strip()
        row += 1
    ref.product_last_row = row - 1

    return ref


@dataclass
class MismatchItem:
    row: int
    kind: str  # "biz" | "product"
    key: str  # 정규화된 사업자번호 또는 품목 원문
    hospital: str
    raw_display: str  # 사용자에게 보여줄 실패 값


@dataclass
class ProcessResult:
    target_path: Path
    app: object = field(repr=False)  # xlwings App (실제 Excel 프로세스)
    book: object = field(repr=False)  # xlwings Book
    sheet: object = field(repr=False)  # xlwings Sheet (3번째 탭)
    last_data_row: int
    b_values: list = field(default_factory=list)  # 인메모리 수탁업체명 값 (커밋 전까지 시트에 안 씀)
    i_values: list = field(default_factory=list)  # 인메모리 제품명 값 (괄호 제거 후)
    matched_biz_count: int = 0
    matched_product_count: int = 0
    skipped_count: int = 0
    mismatches: list[MismatchItem] = field(default_factory=list)

    def _offset(self, row: int) -> int:
        return row - TARGET_DATA_START_ROW


def _launch_excel() -> "xw.App":
    """실제 Excel을 백그라운드(숨김)로 띄운다. 슬라이서·표·수식 등을 100% 보존하기 위해
    openpyxl로 파일을 재작성하지 않고, 실제 Excel이 파일을 열고 저장하게 한다."""
    try:
        app = xw.App(visible=False, add_book=False)
    except Exception as e:
        raise ExcelNotAvailableError(
            "이 PC에서 Microsoft Excel을 실행할 수 없습니다. Excel이 설치되어 있는지 확인해주세요."
        ) from e
    app.display_alerts = False
    try:
        app.screen_updating = False
    except Exception:
        pass
    return app


def close_target(result: ProcessResult) -> None:
    """대상 파일을 저장하지 않고 닫는다 (취소/오류 시 Excel 프로세스 정리용)."""
    try:
        result.book.close()
    except Exception:
        pass
    try:
        result.app.quit()
    except Exception:
        pass


def validate_target_headers(sheet) -> list[str]:
    """헤더가 예상과 다르면 경고 메시지 목록을 반환한다 (빈 리스트면 정상)."""
    header_row = sheet.range(
        (TARGET_HEADER_ROW, COL_B_수탁업체명), (TARGET_HEADER_ROW, COL_I_제품명)
    ).value
    offset_map = {
        COL_B_수탁업체명: 0,
        COL_E_사업자번호: COL_E_사업자번호 - COL_B_수탁업체명,
        COL_F_병원명: COL_F_병원명 - COL_B_수탁업체명,
        COL_I_제품명: COL_I_제품명 - COL_B_수탁업체명,
    }
    warnings = []
    for col, expected in EXPECTED_HEADERS.items():
        actual = header_row[offset_map[col]]
        if str(actual or "").strip() != expected:
            warnings.append(
                f"{TARGET_HEADER_ROW}행 {openpyxl.utils.get_column_letter(col)}열 헤더가 "
                f"'{expected}'가 아니라 '{actual}' 입니다."
            )
    return warnings


def process_target_file(target_path: str | Path, ref: ReferenceData) -> ProcessResult:
    """실제 Excel을 열어 대상 시트를 읽고, 매칭 결과는 인메모리 배열에만 반영한다.

    시트/파일에는 아직 아무 것도 쓰지 않는다 (미스매칭 확인까지 끝난 뒤 commit_and_save에서
    한 번에 기록) — 슬라이서·표·수식 등 Excel 고유 요소는 실제 Excel이 그대로 들고 있으므로
    변경되지 않는다.
    """
    target_path = Path(target_path)
    app = _launch_excel()
    try:
        book = app.books.open(str(target_path), update_links=False)
    except Exception as e:
        app.quit()
        raise TargetFormatError(
            "변경할 엑셀파일을 여는 중 오류가 발생했습니다. "
            "다른 프로그램(엑셀 등)에서 이 파일을 열어두지 않았는지 확인해주세요.\n" + str(e)
        )

    if len(book.sheets) < TARGET_SHEET_INDEX + 1:
        book.close()
        app.quit()
        raise TargetFormatError("변경할 엑셀파일에 3번째 탭이 없습니다.")

    sheet = book.sheets[TARGET_SHEET_INDEX]

    # 시트에 자동필터/슬라이서로 숨겨진 행이 있으면, 그 상태에서 여러 행에 한 번에
    # 값을 쓰는 범위 대입이 조용히 무시된다(Excel의 알려진 동작). 값을 쓰기 전에
    # 필터를 임시로 해제해 모든 행을 보이게 한다 — 원본 파일은 건드리지 않으므로
    # (Save As로만 저장) 안전하다. 결과 파일에는 필터 선택 상태가 초기화된다.
    try:
        if sheet.api.FilterMode:
            sheet.api.ShowAllData()
    except Exception:
        pass

    used_last_row = sheet.used_range.last_cell.row
    block = []
    if used_last_row >= TARGET_DATA_START_ROW:
        block = sheet.range(
            (TARGET_DATA_START_ROW, COL_B_수탁업체명), (used_last_row, COL_I_제품명)
        ).value
        if block and not isinstance(block[0], list):
            block = [block]

    while block and block[-1][0] is None and block[-1][COL_E_사업자번호 - COL_B_수탁업체명] is None:
        block.pop()

    last_data_row = TARGET_DATA_START_ROW + len(block) - 1

    result = ProcessResult(target_path=target_path, app=app, book=book, sheet=sheet, last_data_row=last_data_row)

    e_off = COL_E_사업자번호 - COL_B_수탁업체명
    f_off = COL_F_병원명 - COL_B_수탁업체명
    i_off = COL_I_제품명 - COL_B_수탁업체명

    b_values = [row_data[0] for row_data in block]
    i_values = [row_data[i_off] for row_data in block]

    for offset, row_data in enumerate(block):
        row = TARGET_DATA_START_ROW + offset
        hospital = row_data[f_off]
        if is_yb_hospital(hospital):
            product = row_data[i_off]
            key = str(product or "")
            manager = ref.product_map.get(key)
            if manager is not None:
                b_values[offset] = manager
                result.matched_product_count += 1
            else:
                result.mismatches.append(
                    MismatchItem(row=row, kind="product", key=key, hospital=str(hospital or ""), raw_display=key)
                )
        else:
            biz_no_raw = row_data[e_off]
            key = normalize_biz_no(biz_no_raw)
            manager = ref.biz_map.get(key)
            if manager is not None:
                b_values[offset] = manager
                result.matched_biz_count += 1
            else:
                result.mismatches.append(
                    MismatchItem(
                        row=row, kind="biz", key=key, hospital=str(hospital or ""),
                        raw_display=str(biz_no_raw or ""),
                    )
                )

    for offset in range(len(i_values)):
        if i_values[offset] is not None:
            i_values[offset] = strip_product_name(i_values[offset])

    result.b_values = b_values
    result.i_values = i_values
    return result


def commit_and_save(result: ProcessResult, save_path: str | Path) -> None:
    """인메모리 배열(b_values/i_values)을 실제 시트에 기록하고 '다른 이름으로 저장' 방식으로
    저장한다 (원본 파일은 절대 덮어쓰지 않음). 성공/실패와 무관하게 Excel은 항상 정리한다."""
    try:
        n = len(result.b_values)
        if n:
            result.sheet.range(
                (TARGET_DATA_START_ROW, COL_B_수탁업체명), (result.last_data_row, COL_B_수탁업체명)
            ).value = [[v] for v in result.b_values]
            result.sheet.range(
                (TARGET_DATA_START_ROW, COL_I_제품명), (result.last_data_row, COL_I_제품명)
            ).value = [[v] for v in result.i_values]
        result.book.save(str(save_path))
    finally:
        close_target(result)


def backup_reference_file(ref_path: str | Path) -> Path:
    ref_path = Path(ref_path)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = ref_path.with_name(f"{ref_path.stem}_백업_{stamp}{ref_path.suffix}")
    shutil.copy2(ref_path, backup_path)
    return backup_path


@dataclass
class MismatchGroup:
    kind: str  # "biz" | "product"
    key: str
    hospital: str  # 대표 병원명 (첫 건 기준)
    items: list = field(default_factory=list)  # list[MismatchItem], 같은 key를 공유하는 모든 행
    suggestions: list = field(default_factory=list)  # [(후보키, 담당자, 유사도), ...] 유사도 내림차순


def suggest_candidates(key: str, candidates: dict, top_n: int = 3, min_ratio: float = 0.0) -> list[tuple]:
    """key와 candidates(딕셔너리: 후보키 -> 담당자)를 문자열 유사도로 비교해 가장 비슷한 것부터 top_n개 반환.

    표기법만 다른 동일 품목(예: "글루스탑정15mg" vs "글루스탑정 15mg (피오글리타존)")처럼
    완전일치는 안 되지만 사람이 보면 같은 걸 알 수 있는 경우를 참고용으로 보여주기 위함이다.
    실제 매칭 로직(완전일치)에는 전혀 영향을 주지 않는다 — 어디까지나 사용자 판단을 돕는 참고 정보.
    """
    if not key:
        return []
    scored = []
    for cand_key, manager in candidates.items():
        if not cand_key or cand_key == key:
            continue
        ratio = difflib.SequenceMatcher(None, key, cand_key).ratio()
        if ratio >= min_ratio:
            scored.append((cand_key, manager, ratio))
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:top_n]


def group_mismatches(mismatches: list[MismatchItem], ref: "ReferenceData | None" = None) -> list[MismatchGroup]:
    """동일 (kind, key)를 가진 미스매칭 행들을 하나의 그룹으로 묶는다.

    FR-5.6: 같은 실행 안에서 동일 키는 한 번만 물어보고 나머지 행에는 그대로 적용한다.
    ref가 주어지면 그룹별로 유사 후보(suggestions)도 함께 계산한다.
    """
    groups: dict[tuple[str, str], MismatchGroup] = {}
    order: list[tuple[str, str]] = []
    for item in mismatches:
        gkey = (item.kind, item.key)
        if gkey not in groups:
            groups[gkey] = MismatchGroup(kind=item.kind, key=item.key, hospital=item.hospital)
            order.append(gkey)
        groups[gkey].items.append(item)

    result = [groups[k] for k in order]
    if ref is not None:
        for group in result:
            if group.kind == "biz":
                group.suggestions = suggest_candidates(group.key, ref.biz_map, min_ratio=0.75)
            else:
                group.suggestions = suggest_candidates(group.key, ref.product_map, min_ratio=0.35)
    return result


def resolve_mismatch_group(
    ref: ReferenceData,
    result: ProcessResult,
    group: MismatchGroup,
    manager: str,
    hospital_name_for_new_row: str | None = None,
) -> None:
    """미스매칭 그룹(동일 키를 공유하는 모든 행)을 한 번에 확정한다.

    (a) 그룹에 속한 모든 행의 인메모리 B열 값을 갱신 (commit_and_save에서 실제 시트에 기록)
    (b) 기준엑셀에는 새 행을 단 한 줄만 추가 (in-memory, save_reference()로 실제 파일 반영)
    """
    for item in group.items:
        result.b_values[result._offset(item.row)] = manager

    if group.kind == "biz":
        ref.biz_map[group.key] = manager
        ref.pending_biz_rows.append((group.key, hospital_name_for_new_row or group.hospital, manager))
    else:
        ref.product_map[group.key] = manager
        ref.pending_product_rows.append((group.key, manager))


def skip_mismatch_group(result: ProcessResult, group: MismatchGroup) -> None:
    """FR-5.7: 건너뛴 그룹은 B열을 비우고, 결과 요약의 미확인 건수에 반영한다.

    기준엑셀에는 아무 것도 추가하지 않는다.
    """
    for item in group.items:
        result.b_values[result._offset(item.row)] = None
    result.skipped_count += len(group.items)


def read_biz_table(path: str | Path) -> list[dict]:
    wb = openpyxl.load_workbook(path)
    ws = wb[REF_SHEET_거래처별담당자]
    rows = []
    row = REF_거래처_DATA_START_ROW
    while True:
        biz_no = ws.cell(row=row, column=1).value
        hospital = ws.cell(row=row, column=2).value
        manager = ws.cell(row=row, column=3).value
        if biz_no is None and manager is None:
            break
        rows.append({"biz_no": biz_no, "hospital": hospital, "manager": manager})
        row += 1
    return rows


def read_product_table(path: str | Path) -> list[dict]:
    wb = openpyxl.load_workbook(path)
    ws = wb[REF_SHEET_윤병옥내과]
    rows = []
    row = REF_윤병옥_DATA_START_ROW
    while True:
        product = ws.cell(row=row, column=1).value
        manager = ws.cell(row=row, column=2).value
        if product is None and manager is None:
            break
        rows.append({"product": product, "manager": manager})
        row += 1
    return rows


def overwrite_biz_table(path: str | Path, rows: list[dict]) -> None:
    """거래처별 담당자 탭 전체를 rows로 재작성한다 (조회/수정/삭제 화면용). 사전 백업 필수."""
    wb = openpyxl.load_workbook(path)
    ws = wb[REF_SHEET_거래처별담당자]
    old_last = REF_거래처_DATA_START_ROW - 1
    r = REF_거래처_DATA_START_ROW
    while ws.cell(row=r, column=1).value is not None or ws.cell(row=r, column=3).value is not None:
        old_last = r
        r += 1

    for i, item in enumerate(rows):
        r = REF_거래처_DATA_START_ROW + i
        ws.cell(row=r, column=1).value = item["biz_no"]
        ws.cell(row=r, column=2).value = item["hospital"]
        ws.cell(row=r, column=3).value = item["manager"]

    for r in range(REF_거래처_DATA_START_ROW + len(rows), old_last + 1):
        for c in (1, 2, 3):
            ws.cell(row=r, column=c).value = None

    wb.save(path)


def overwrite_product_table(path: str | Path, rows: list[dict]) -> None:
    """윤병옥내과 탭 전체를 rows로 재작성한다 (조회/수정/삭제 화면용). 사전 백업 필수."""
    wb = openpyxl.load_workbook(path)
    ws = wb[REF_SHEET_윤병옥내과]
    old_last = REF_윤병옥_DATA_START_ROW - 1
    r = REF_윤병옥_DATA_START_ROW
    while ws.cell(row=r, column=1).value is not None or ws.cell(row=r, column=2).value is not None:
        old_last = r
        r += 1

    for i, item in enumerate(rows):
        r = REF_윤병옥_DATA_START_ROW + i
        ws.cell(row=r, column=1).value = item["product"]
        ws.cell(row=r, column=2).value = item["manager"]

    for r in range(REF_윤병옥_DATA_START_ROW + len(rows), old_last + 1):
        for c in (1, 2):
            ws.cell(row=r, column=c).value = None

    wb.save(path)


def all_manager_names(ref: ReferenceData) -> list[str]:
    names = set(ref.biz_map.values()) | set(ref.product_map.values())
    return sorted(names)


def save_reference(ref: ReferenceData) -> None:
    """ref.pending_*_rows에 쌓인 신규 행을 실제 기준엑셀 파일에 append하고 저장한다."""
    wb = openpyxl.load_workbook(ref.path)
    ws1 = wb[REF_SHEET_거래처별담당자]
    row = ref.biz_last_row + 1
    for biz_no, hospital_name, manager in ref.pending_biz_rows:
        ws1.cell(row=row, column=1).value = biz_no
        ws1.cell(row=row, column=2).value = hospital_name
        ws1.cell(row=row, column=3).value = manager
        row += 1
    ref.biz_last_row = row - 1

    ws2 = wb[REF_SHEET_윤병옥내과]
    row = ref.product_last_row + 1
    for product, manager in ref.pending_product_rows:
        ws2.cell(row=row, column=1).value = product
        ws2.cell(row=row, column=2).value = manager
        row += 1
    ref.product_last_row = row - 1

    wb.save(ref.path)
    ref.pending_biz_rows.clear()
    ref.pending_product_rows.clear()
