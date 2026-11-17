# 호실 자동 배정 + 고객list(엑셀) 읽기/쓰기. 서버(server.py)에서 사용.
import os, re
from datetime import datetime

DESKTOP = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
XLSX = os.environ.get("JW_XLSX") or os.path.join(DESKTOP, "정원오피스넷_고객관리_통합본.xlsx")
SHEET = "고객마스터"
FIRST_ROW = 5
LETTERS = "DEFGHIJK"

def _seq(start_block):
    """D01~D10, E01~E10 … K01~K10, 다음 블록 D11~D20 … 형태로 끝없이 생성"""
    b = start_block
    while True:
        for L in LETTERS:
            for n in range(b*10+1, b*10+11):
                yield f"{L}{n:02d}"
        b += 1

def base(room):            # 'A18(2)' -> 'A18'
    return re.sub(r"\(\d+\)$", "", (room or "").strip())

def next_room(used, corp):
    """개인: D01부터 / 법인: D11부터. 이미 쓰인 호실은 건너뜀."""
    bases = {base(r) for r in used}
    for r in _seq(1 if corp else 0):
        if r not in bases: return r

def resolve_room(room, used):
    """직접 입력한 호실이 이미 있으면 (2), (3)… 을 붙임"""
    room = (room or "").strip()
    if not room: return ""
    used = set(used)
    if room not in used: return room
    b = base(room); n = 2
    while f"{b}({n})" in used: n += 1
    return f"{b}({n})"

def read_master():
    import openpyxl
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=False)
    ws = wb[SHEET]; rooms = []; nums = {"S": 0, "N": 0}; last = FIRST_ROW - 1
    for i, row in enumerate(ws.iter_rows(min_row=FIRST_ROW, max_col=3, values_only=True), start=FIRST_ROW):
        a, b, c = row
        if a:
            last = i
            m = re.match(r"([SN])(\d+)$", str(a))
            if m: nums[m.group(1)] = max(nums[m.group(1)], int(m.group(2)))
        if c: rooms.append(str(c).strip())
    wb.close()
    return {"rooms": rooms, "nums": nums, "last": last}

def _excel_wb():
    import pythoncom, win32com.client
    pythoncom.CoInitialize()
    xl = win32com.client.Dispatch("Excel.Application")
    for wb in xl.Workbooks:
        if os.path.normcase(wb.FullName) == os.path.normcase(XLSX): return xl, wb, False
    was_visible = xl.Visible
    wb = xl.Workbooks.Open(XLSX)
    return xl, wb, True

def _pj(d):                # 날짜 문자열 -> 엑셀 날짜
    return (datetime.strptime(d, "%Y-%m-%d") - datetime(1899, 12, 30)).days if d else None   # 엑셀 날짜 일련번호(시간대 밀림 방지)

def register(c):
    """c: dict(type, corp, company, rep, bizNo, corpNo, phone, email, room, start, end, total, prepaid, deposit, disc, std)"""
    st = read_master()
    kind = "상주" if c["type"] == "resident" else "비상주"
    prefix = "S" if kind == "상주" else "N"
    num = f"{prefix}{st['nums'][prefix]+1:03d}"
    room = resolve_room(c.get("room", ""), st["rooms"])
    row = st["last"] + 1
    biz, jumin = "", ""
    bn = (c.get("bizNo") or "").strip()
    if re.fullmatch(r"\d{6}-\d{7}", bn): jumin = bn          # 주민번호 형태는 J열
    else: biz = bn
    if c.get("corp") and c.get("corpNo"): jumin = c["corpNo"]
    vals = {"A": num, "B": kind, "C": room, "D": c.get("company") or c.get("rep") or "", "E": c.get("rep") or "", "F": c.get("rep") or "",
            "G": c.get("phone") or "", "H": c.get("email") or "", "I": biz, "J": jumin, "L": "계약중",
            "M": _pj(c.get("start")), "N": _pj(c.get("end")), "T": "부과", "Y": "미발행",
            "AB": "고객정보 프로그램 " + datetime.now().strftime("%Y-%m-%d")}
    if kind == "비상주":
        if c.get("prepaid"): vals.update({"P": "선납", "V": c.get("total") or None})
    else:
        vals.update({"P": "매월", "Q": c.get("deposit") or None, "S": c.get("disc") or None})
    xl, wb, opened = _excel_wb()
    try:
        ws = wb.Worksheets(SHEET)
        for col, v in vals.items():
            if v in ("", None): continue
            cell = ws.Range(f"{col}{row}")
            if col in ("M", "N"): cell.NumberFormat = "yyyy-mm-dd"
            if col in ("G", "I", "J"): cell.NumberFormat = "@"
            cell.Value2 = v
        wb.Save()
    finally:
        if opened: wb.Close(False)
    return {"num": num, "room": room, "row": row}

def fix_legacy_dupes():
    """엑셀에 이미 있는 같은 호실(A18 등)을 A18, A18(2), A18(3) 으로 정리 (1회성)"""
    xl, wb, opened = _excel_wb()
    out = []
    try:
        ws = wb.Worksheets(SHEET); seen = {}
        r = FIRST_ROW
        while ws.Range(f"A{r}").Value:
            v = ws.Range(f"C{r}").Value
            if v:
                v = str(v).strip(); b = base(v); seen[b] = seen.get(b, 0) + 1
                want = b if seen[b] == 1 else f"{b}({seen[b]})"
                if v != want: ws.Range(f"C{r}").Value = want; out.append((r, v, want))
            r += 1
        wb.Save()
    finally:
        if opened: wb.Close(False)
    return out
