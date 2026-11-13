"""거래처명/담당자 엑셀 읽기. GUI와 무관하게 단독으로 사용·테스트할 수 있다."""
import openpyxl


class ExcelParseError(Exception):
    pass


def parse_excel(filepath: str) -> list[dict]:
    """엑셀에서 거래처명/담당자 목록을 파싱해 반환.

    Raises:
        ExcelParseError: 빈 파일이거나 유효한 데이터 행이 없을 때
        Exception: openpyxl 읽기 실패
    """
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        raise ExcelParseError("엑셀 파일이 비어 있습니다.")

    # 맨 위의 빈 줄은 건너뛰고, 첫 데이터 줄이 헤더인지 자동 감지
    start_row = next((i for i, r in enumerate(rows) if any(c not in (None, "") for c in r)), len(rows))
    if start_row < len(rows):
        first = [str(c).strip() if c else "" for c in rows[start_row]]
        if any(k in " ".join(first) for k in ["거래처", "담당자", "이름", "성명"]):
            start_row += 1

    data = []
    for row in rows[start_row:]:
        if len(row) < 2:
            continue
        name = str(row[0]).strip() if row[0] else ""
        manager = str(row[1]).strip() if row[1] else ""
        if name and manager:
            data.append({"거래처명": name, "담당자": manager})

    if not data:
        raise ExcelParseError("유효한 데이터가 없습니다.\n(거래처명, 담당자 열을 확인하세요)")

    return data


def _cell_text(value) -> str:
    return str(value).strip() if value else ""


def add_entry(filepath: str, name: str, manager: str) -> None:
    """엑셀 맨 아래에 거래처명/담당자 한 줄을 추가해 저장한다. (.xlsx만 가능)"""
    wb = openpyxl.load_workbook(filepath)
    try:
        wb.active.append([name, manager])
        wb.save(filepath)
    finally:
        wb.close()


def update_entry(filepath: str, old_name: str, old_manager: str, name: str, manager: str) -> bool:
    """엑셀에서 (old_name, old_manager) 줄을 찾아 새 값으로 바꿔 저장한다. 못 찾으면 False."""
    wb = openpyxl.load_workbook(filepath)
    try:
        ws = wb.active
        for row in ws.iter_rows(min_col=1, max_col=2):
            if _cell_text(row[0].value) == old_name and _cell_text(row[1].value) == old_manager:
                row[0].value = name
                row[1].value = manager
                wb.save(filepath)
                return True
        return False
    finally:
        wb.close()
