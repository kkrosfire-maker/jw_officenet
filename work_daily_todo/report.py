"""내보내기 - 기간별 엑셀 분석 파일(요약·할일기록·일별요약)과 오늘 목록 JPG 를 만든다."""
from datetime import date

from ledger import WEEKDAY, dday_text, due_gap, parse_day

GREEN, TINT = "0D4A32", "EAF1ED"


def build_image(tasks, dest, today_label):
    """오늘 목록을 메모장 캡처 같은 JPG 로 만든다: 날짜 제목, 끝낸 일, 빈 줄, 남은 일(대기)."""
    from PIL import Image, ImageDraw, ImageFont

    def font(bold, size):
        return ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf" if bold else r"C:\Windows\Fonts\malgun.ttf", size)

    done = [t["text"] for t in tasks if t.get("done_at")]
    todo = [t["text"] + " (대기)" for t in tasks if not t.get("done_at")]
    W, pad, fs = 760, 44, 34
    title_f, body_f = font(True, 44), font(False, fs)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def wrap(text):
        out, cur = [], ""
        for ch in text:
            if probe.textlength(cur + ch, font=body_f) > W - pad * 2 and cur:
                out.append(cur)
                cur = ch
            else:
                cur += ch
        return [w.strip() for w in out + [cur]]

    lines = [(today_label, True), ("", False)]
    for group in (done, todo):
        if group:
            if lines[-1][0]:
                lines.append(("", False))
            for text in group:
                lines += [(w, False) for w in wrap(text)]
    gap = int(fs * 1.55)
    H = pad * 2 + 60 + gap * (len(lines) - 1)
    img = Image.new("RGB", (W, H), "#FFC9A6")
    d = ImageDraw.Draw(img)
    y = pad
    for text, is_title in lines:
        if text:
            d.text((pad, y), text, font=title_f if is_title else body_f, fill="#1A1A1A")
        y += 70 if is_title else gap
    img.save(dest, "JPEG", quality=95)


class _Look:
    """세 시트가 함께 쓰는 서식."""

    def __init__(self):
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        self.Font, self.Alignment, self.PatternFill = Font, Alignment, PatternFill
        self.head_font = Font(bold=True, color="FFFFFF", name="맑은 고딕")
        self.head_fill = PatternFill("solid", fgColor=GREEN)
        thin = Side(style="thin", color="C6D3CC")
        self.box = Border(left=thin, right=thin, top=thin, bottom=thin)

    def header(self, ws, ncol, freeze=True):
        for c in range(1, ncol + 1):
            cell = ws.cell(1, c)
            cell.font, cell.fill, cell.border = self.head_font, self.head_fill, self.box
            cell.alignment = self.Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 24
        if freeze:
            ws.freeze_panes = "A2"

    @staticmethod
    def widths(ws, ws_widths):
        from openpyxl.utils import get_column_letter
        for i, w in enumerate(ws_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def _pick_rows(tasks, start, end):
    lo = parse_day(start) if start else date.min
    hi = parse_day(end) if end else date.max
    rows = []
    for t in tasks:
        reg = parse_day(t["date"])
        done = parse_day(t["done_at"]) if t.get("done_at") else None
        if lo <= reg <= hi or (done and lo <= done <= hi):
            rows.append((t, reg, done))
    rows.sort(key=lambda r: (r[1], r[0]["created_at"]))
    return rows, lo, hi


def _records_sheet(wb, look, rows, tasks, today_d):
    """할일기록 시트를 채우고, 다른 시트가 쓸 (task, 등록일, 완료일, 걸린 일수, 마감 대비) 목록을 돌려준다."""
    Font = look.Font
    by_id = {t["id"]: t for t in tasks}
    children = {}
    for t in tasks:
        if t.get("parent"):
            children.setdefault(t["parent"], []).append(t["text"])

    ws = wb.active
    ws.title = "할일기록"
    ws.append(["등록일", "요일", "할 일", "상태", "마감일", "완료일", "걸린 일수", "마감 대비", "밀린 일수", "후속 원본", "후속 작업", "메모"])
    stats = []
    for t, reg, done in rows:
        days = (done - reg).days if done else None
        late = (today_d - reg).days if not done else None
        due = parse_day(t["due"]) if t.get("due") else None
        gap = due_gap(t, done or today_d)
        parent = by_id.get(t.get("parent"))
        ws.append([reg, WEEKDAY[reg.weekday()], t["text"], "완료" if done else "미완료", due, done, days,
                   None if gap is None else dday_text(gap), late,
                   parent["text"] if parent else None, "\n".join(children.get(t["id"], [])) or None, t.get("note") or None])
        stats.append((t, reg, done, days, gap))
        if gap is not None:
            color = "B3261E" if gap > 0 else GREEN if gap == 0 else "1A5FB4"
            ws.cell(ws.max_row, 8).font = Font(color=color, bold=True)
    for r in ws.iter_rows(min_row=2):
        for c in r:
            c.border = look.box
            c.alignment = look.Alignment(vertical="top", wrap_text=True, horizontal="center" if c.column != 3 and c.column < 10 else "left")
        for i in (0, 4, 5):
            r[i].number_format = "yyyy-mm-dd"
        if r[3].value == "미완료":
            r[3].font = Font(color="B3261E", bold=True)
    look.header(ws, 12)
    look.widths(ws, [12, 6, 40, 8, 12, 12, 10, 10, 10, 24, 28, 36])
    ws.auto_filter.ref = ws.dimensions
    return stats, children


def _daily_sheet(wb, look, stats, lo, hi):
    ws = wb.create_sheet("일별요약")
    ws.append(["날짜", "요일", "등록", "완료(그날 끝낸 수)", "당일 등록·당일 완료", "밀렸다가 완료", "당일 처리율"])
    days_set = {r for _, r, _, _, _ in stats} | {d for _, _, d, _, _ in stats if d}
    for d in sorted(x for x in days_set if lo <= x <= hi):
        reg_n = sum(1 for _, r, _, _, _ in stats if r == d)
        done_n = sum(1 for _, _, dn, _, _ in stats if dn == d)
        same = sum(1 for _, r, dn, _, _ in stats if dn == d and r == d)
        ws.append([d, WEEKDAY[d.weekday()], reg_n, done_n, same, done_n - same, (same / reg_n) if reg_n else None])
    for r in ws.iter_rows(min_row=2):
        r[0].number_format = "yyyy-mm-dd"
        r[6].number_format = "0%"
        for c in r:
            c.border = look.box
            c.alignment = look.Alignment(horizontal="center")
    look.header(ws, 7)
    look.widths(ws, [12, 6, 8, 18, 18, 14, 14])


def _summary_items(stats, children, start, end):
    """(항목, 값, 서식) 목록. 퍼센트 칸은 서식을 항목이 직접 가진다."""
    total = len(stats)
    done_list = [s for s in stats if s[2]]
    day_vals = [s[3] for s in done_list]
    same_n = sum(1 for d in day_vals if d == 0)
    due_done = [s for s in done_list if s[4] is not None]
    on_time = sum(1 for s in due_done if s[4] <= 0)
    delays = [s[4] for s in due_done if s[4] > 0]
    pct = "0%"
    return [
        ("기간", f"{start or '처음'} ~ {end or '현재'}", None),
        ("전체 할 일", total, None),
        ("완료", len(done_list), None),
        ("미완료(아직 남음)", total - len(done_list), None),
        ("완료율", (len(done_list) / total) if total else 0, pct),
        ("당일 처리 비율(완료 중)", (same_n / len(done_list)) if done_list else 0, pct),
        ("평균 걸린 일수", round(sum(day_vals) / len(day_vals), 1) if day_vals else 0, None),
        ("완료한 건(마감 기준)", len(due_done), None),
        ("마감 내 완료율", (on_time / len(due_done)) if due_done else 0, pct),
        ("평균 지연일(지연된 건만)", round(sum(delays) / len(delays), 1) if delays else 0, None),
        ("후속 작업이 생긴 건", sum(1 for s in stats if children.get(s[0]["id"])), None),
    ]


def _summary_sheet(wb, look, stats, children, start, end):
    from openpyxl.worksheet.views import Selection
    Font = look.Font
    ws = wb.create_sheet("요약", 0)
    ws.append(["항목", "값"])
    items = _summary_items(stats, children, start, end)
    for k, v, _ in items:
        ws.append([k, v])
    for r, (_, _, fmt) in zip(ws.iter_rows(min_row=2), items):
        r[0].font = Font(bold=True, color=GREEN)
        r[0].fill = look.PatternFill("solid", fgColor=TINT)
        for c in r:
            c.border = look.box
        r[1].alignment = look.Alignment(horizontal="right")
        if fmt:
            r[1].number_format = fmt
    look.header(ws, 2, freeze=False)  # 틀 고정을 걸었다 풀면 pane 없는 selection 이 남아 엑셀이 '복구하시겠습니까?' 를 띄운다
    ws.sheet_view.selection = [Selection()]
    # 오래 걸린 일 TOP 5
    base = len(items) + 3
    ws.cell(base, 1, "오래 걸린 일 TOP 5").font = Font(bold=True, color=GREEN, size=12)
    for i, h in enumerate(["할 일", "걸린 일수"], 1):
        c = ws.cell(base + 1, i, h)
        c.font, c.fill, c.border = look.head_font, look.head_fill, look.box
        c.alignment = look.Alignment(horizontal="center")
    top = sorted((s for s in stats if s[2]), key=lambda s: s[3], reverse=True)[:5]
    for j, (t, _, _, d, _) in enumerate(top, base + 2):
        for i, v in enumerate([t["text"], d], 1):
            c = ws.cell(j, i, v)
            c.border = look.box
            c.alignment = look.Alignment(wrap_text=True, horizontal="left" if i == 1 else "center")
    look.widths(ws, [34, 16])


def build_excel(tasks, start, end, dest, today_d=None):
    """start~end(YYYY-MM-DD, 빈 값이면 전체) 동안 등록되었거나 완료된 일을 엑셀로 저장하고 (건수, 완료된 id 목록)을 돌려준다."""
    from openpyxl import Workbook

    today_d = today_d or date.today()
    rows, lo, hi = _pick_rows(tasks, start, end)
    look = _Look()
    wb = Workbook()
    stats, children = _records_sheet(wb, look, rows, tasks, today_d)
    _daily_sheet(wb, look, stats, lo, hi)
    _summary_sheet(wb, look, stats, children, start, end)
    wb.active = 0
    wb.worksheets[0].sheet_view.tabSelected = True
    for other in wb.worksheets[1:]:
        other.sheet_view.tabSelected = False
    wb.save(dest)
    return len(stats), [t["id"] for t, _, d in rows if d]
