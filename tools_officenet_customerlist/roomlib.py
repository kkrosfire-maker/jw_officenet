# 호실 자동 배정 + 고객list(엑셀) 읽기/쓰기. 서버(server.py)에서 사용.
import os, re
from datetime import datetime

DESKTOP = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
def _cfg_xlsx():      # 엑셀 위치는 app_config.json 의 "xlsx" 에서 바꿀 수 있음 (없으면 바탕화면)
    try:
        import json
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_config.json"), encoding="utf-8") as f: return json.load(f).get("xlsx")
    except (OSError, ValueError): return None
XLSX = os.environ.get("JW_XLSX") or _cfg_xlsx() or os.path.join(DESKTOP, "정원오피스넷_고객관리_통합본.xlsx")
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
    ws = wb[SHEET]; rooms = []; active = []; nums = {"S": 0, "N": 0}; last = FIRST_ROW - 1
    for i, row in enumerate(ws.iter_rows(min_row=FIRST_ROW, max_col=12, values_only=True), start=FIRST_ROW):
        a, b, c = row[0], row[1], row[2]; status = row[11]
        if a:
            last = i
            m = re.match(r"([SN])(\d+)$", str(a))
            if m: nums[m.group(1)] = max(nums[m.group(1)], int(m.group(2)))
        if c:
            rooms.append(str(c).strip())
            if status not in ("퇴실", "취소"): active.append(str(c).strip())   # 퇴실·취소 호실은 겹침 판정에서 제외
    wb.close()
    return {"rooms": rooms, "active": active, "nums": nums, "last": last}

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

def _digits(x): return re.sub(r"\D", "", str(x or ""))

def read_rows():
    """고객마스터 전체 행을 {열문자: 값} 사전 목록으로 읽음"""
    import openpyxl
    from openpyxl.utils import get_column_letter as L
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=False)
    ws = wb[SHEET]; out = []
    for i, row in enumerate(ws.iter_rows(min_row=FIRST_ROW, max_col=28, values_only=True), start=FIRST_ROW):
        if not row[0]: continue
        d = {L(k+1): v for k, v in enumerate(row)}; d["row"] = i; out.append(d)
    wb.close()
    return out

def build_vals(c, kind, room):
    biz, jumin = "", ""
    bn = (c.get("bizNo") or "").strip()
    if re.fullmatch(r"\d{6}-\d{7}", bn): jumin = bn          # 주민번호 형태는 J열
    else: biz = bn
    if c.get("corp") and c.get("corpNo"): jumin = c["corpNo"]
    v = {"C": room, "D": c.get("company") or c.get("rep") or "", "E": c.get("rep") or "", "F": c.get("rep") or "",
         "G": c.get("phone") or "", "H": c.get("email") or "", "I": biz, "J": jumin,
         "M": c.get("start") or "", "N": c.get("end") or ""}
    if kind == "비상주":
        if c.get("prepaid"): v.update({"P": "선납", "V": c.get("total") or ""})
    else:
        v.update({"P": "매월", "Q": c.get("deposit") or "", "S": c.get("disc") or ""})
    return v

LABEL = {"C": "호실", "D": "업체명", "E": "대표자", "G": "연락처", "H": "이메일", "I": "사업자번호", "J": "법인/주민번호",
         "M": "계약 시작일", "N": "계약 종료일", "P": "결제방식", "V": "선납 총액(VAT포함)", "Q": "보증금", "S": "월 이용료(공급가)"}

def _norm(col, v):
    if v in (None, ""): return ""
    if col in ("M", "N"): return v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)[:10]
    if col in ("V", "Q", "S"):
        try: return str(int(round(float(str(v).replace(",", "")))))
        except ValueError: return str(v)
    if col == "G": return _digits(v)
    if col in ("I", "J"): return _digits(v)
    return str(v).strip()

def _find(c, kind, rows, num_hint):
    """같은 고객의 기존 행 찾기: 이 화면에서 등록한 고객번호(연락처나 이름이 같을 때) → 계약중/예정인 같은 연락처"""
    if num_hint:
        for r in rows:
            if r["A"] == num_hint and (_digits(r.get("G")) == _digits(c.get("phone")) or str(r.get("E") or "").strip() == (c.get("rep") or "").strip()):
                return r
    ph = _digits(c.get("phone"))
    if ph:
        for r in rows:
            if r.get("B") == kind and _digits(r.get("G")) == ph and r.get("L") in ("계약중", "예정", None): return r
    return None

def check(c):
    kind = "상주" if c["type"] == "resident" else "비상주"
    st = read_master(); rows = read_rows()
    ex = _find(c, kind, rows, c.get("num"))
    if not ex:
        return {"status": "new", "room": resolve_room(c.get("room", ""), st["active"])}
    new = build_vals(c, kind, c.get("room", ""))
    diffs = []
    for col, nv in new.items():
        if col == "F" or col not in LABEL: continue
        if nv in ("", None): continue                      # 화면에서 비워둔 값은 비교 안 함
        a, b = _norm(col, ex.get(col)), _norm(col, nv)
        if a != b: diffs.append({"col": col, "label": LABEL[col], "old": a or "(비어 있음)", "new": str(nv)})
    return {"status": "changed" if diffs else "dup", "num": ex["A"], "row": ex["row"], "room": ex.get("C"), "diffs": diffs, "name": ex.get("D") or ex.get("E") or ""}

def _write(ws, row, vals):
    for col, v in vals.items():
        if v in ("", None): continue
        cell = ws.Range(f"{col}{row}")
        if col in ("M", "N"): cell.NumberFormat = "yyyy-mm-dd"; v = (datetime.strptime(v, "%Y-%m-%d") - datetime(1899, 12, 30)).days
        if col in ("G", "I", "J"): cell.NumberFormat = "@"
        cell.Value2 = v

def insert(c):
    st = read_master()
    kind = "상주" if c["type"] == "resident" else "비상주"
    prefix = "S" if kind == "상주" else "N"
    num = f"{prefix}{st['nums'][prefix]+1:03d}"
    room = resolve_room(c.get("room", ""), st["active"])
    row = st["last"] + 1
    vals = build_vals(c, kind, room)
    vals.update({"A": num, "B": kind, "L": "계약중", "T": "부과", "Y": "미발행", "AB": "고객정보 프로그램 " + datetime.now().strftime("%Y-%m-%d")})
    xl, wb, opened = _excel_wb()
    try:
        _write(wb.Worksheets(SHEET), row, vals); wb.Save()
    finally:
        if opened: wb.Close(False)
    return {"num": num, "room": room, "row": row}

def update(c):
    """같은 고객의 기존 행에서 달라진 칸만 고침"""
    r = check(c)
    if r["status"] != "changed": return r
    kind = "상주" if c["type"] == "resident" else "비상주"
    active = [x for x in read_master()["active"]]
    vals = {}
    for d in r["diffs"]:
        v = d["new"]
        if d["col"] == "C":
            others = list(active)
            if r["room"] in others: others.remove(r["room"])      # 자기 자신 호실은 제외하고 겹침 확인
            v = resolve_room(v, others)
        vals[d["col"]] = v
    if "E" in vals: vals["F"] = vals["E"]
    xl, wb, opened = _excel_wb()
    try:
        _write(wb.Worksheets(SHEET), r["row"], vals); wb.Save()
    finally:
        if opened: wb.Close(False)
    return {"num": r["num"], "row": r["row"], "room": vals.get("C", r["room"]), "changed": [d["label"] for d in r["diffs"]]}

def remove(c):
    """등록 취소: 같은 고객의 행에서 값만 지움(수식 칸은 그대로 둠)"""
    kind = "상주" if c["type"] == "resident" else "비상주"
    ex = _find(c, kind, read_rows(), c.get("num"))
    if not ex: return {"removed": False}
    xl, wb, opened = _excel_wb()
    try:
        ws = wb.Worksheets(SHEET); row = ex["row"]
        if str(ws.Range(f"A{row}").Value).strip() != str(ex["A"]).strip(): raise RuntimeError("엑셀이 바뀌어서 행을 다시 확인해야 해요. 다시 시도해 주세요.")
        for col in range(1, 29):                       # A~AB
            cell = ws.Cells(row, col)
            if not cell.HasFormula: cell.ClearContents()
        wb.Save()
    finally:
        if opened: wb.Close(False)
    return {"removed": True, "num": ex["A"], "row": row}

def fix_legacy_dupes():   # (퇴실·취소 행은 건너뜀)
    """엑셀에 이미 있는 같은 호실(A18 등)을 A18, A18(2), A18(3) 으로 정리 (1회성)"""
    xl, wb, opened = _excel_wb()
    out = []
    try:
        ws = wb.Worksheets(SHEET); seen = {}
        r = FIRST_ROW
        while ws.Range(f"A{r}").Value:
            v = ws.Range(f"C{r}").Value
            if v and ws.Range(f"L{r}").Value not in ("퇴실", "취소"):
                v = str(v).strip(); b = base(v); seen[b] = seen.get(b, 0) + 1
                want = b if seen[b] == 1 else f"{b}({seen[b]})"
                if v != want: ws.Range(f"C{r}").Value = want; out.append((r, v, want))
            r += 1
        wb.Save()
    finally:
        if opened: wb.Close(False)
    return out
