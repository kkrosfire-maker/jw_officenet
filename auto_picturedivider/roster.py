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

    # 첫 행 헤더 여부 자동 감지
    start_row = 0
    first = [str(c).strip() if c else "" for c in rows[0]]
    if any(k in " ".join(first) for k in ["거래처", "담당자", "이름", "성명"]):
        start_row = 1

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
