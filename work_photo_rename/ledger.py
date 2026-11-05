"""통계 장부 모듈 — '통계입력확인' 엑셀(기본파일 / 이번 달 작업 엑셀)에 대한 모든 규칙을 한곳에 모았다.

  - 시트 구조(열 위치)와 "같은 줄" 판정 기준          → Schema, row_key
  - 읽기(병원·제약사 이력, 특이사항 이월)              → MasterExcel
  - 쓰기(입력완료 표시·줄 삽입·메모·작업본 생성·통계완료 병합) → mark_done, set_notes, create_work_file, merge_into_base
  - 화면을 멈추지 않는 백그라운드 반영과 중복 방지      → Ledger  (화면 코드는 이것만 부르면 된다)

시트 열: 연도 | 담당자명 | 상태(헤더 없음) | 거래처명 | 처방월 | 입력월(=정산월) | 제약사명 | 통합(수식) | ... | 특이사항
열 위치는 헤더 이름으로 찾고, 못 찾으면 위 순서의 기본 위치를 쓴다.
"""
import copy
import datetime
import queue
import re
import shutil
import threading
from collections import Counter, defaultdict, namedtuple
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from names import NameBook, clean_pharma, memo_key, norm   # noqa: F401  (memo_key는 호출자 편의로 다시 내보냄)

SHEET = "통계입력확인"
DONE = "입력완료"
NOSETTLE = "정산불가"
FINISHED = (DONE, NOSETTLE)        # 처리가 끝난 줄로 치는 상태들


# ── 시트 구조 ────────────────────────────────────────────────────────────

class Schema:
    """열 번호(1부터). 헤더 이름으로 찾고, 없으면 기본 위치."""
    DEFAULTS = dict(year=1, manager=2, status=3, hospital=4, rx_month=5, input_month=6,
                    pharma=7, combined=8, note=10)
    HEADERS = {"연도": "year", "담당자명": "manager", "거래처명": "hospital", "처방월": "rx_month",
               "입력월": "input_month", "제약사명": "pharma", "통합": "combined", "특이사항": "note"}

    def __init__(self, header=()):
        for k, v in self.DEFAULTS.items():
            setattr(self, k, v)
        for i, name in enumerate(header, start=1):
            key = self.HEADERS.get(str(name).strip()) if name is not None else None
            if key:
                setattr(self, key, i)

    @classmethod
    def of(cls, ws):
        return cls([c.value for c in ws[1]])

    def combined_formula(self, r):
        h, m, p = (get_column_letter(c) for c in (self.hospital, self.rx_month, self.pharma))
        return f'=CONCATENATE({h}{r}," ",{m}{r}," ",{p}{r})'

    @property
    def copy_cols(self):
        """새 줄에 값을 옮길 열들 (통합 수식은 줄마다 새로 만든다)."""
        return [self.year, self.manager, self.status, self.hospital, self.rx_month,
                self.input_month, self.pharma, self.note]


def _sheet(wb):
    return wb[SHEET] if SHEET in wb.sheetnames else wb.active


def _text(ws, r, c):
    return str(ws.cell(r, c).value or "").strip()


def row_key(ws, sc, r):
    """'같은 건' 판정 기준: (연도, 병원, 처방월, 제약사 정규화 이름)."""
    return (ws.cell(r, sc.year).value, _text(ws, r, sc.hospital), _text(ws, r, sc.rx_month),
            norm(clean_pharma(_text(ws, r, sc.pharma))))


def pair_matches(ws, sc, r, hospital, pharma):
    """병원·제약사만 같은 줄인가 (월 무관 — 메모처럼 월을 넘어 이어지는 정보용)."""
    return _text(ws, r, sc.hospital) == hospital and norm(clean_pharma(_text(ws, r, sc.pharma))) == norm(pharma)


def insert_row_after(ws, sc, after_row):
    """after_row 바로 아래에 빈 줄을 끼워 넣고 그 줄 번호를 돌려준다.
    openpyxl의 insert_rows는 수식을 고쳐 주지 않아서 통합 수식을 줄 번호에 맞게 다시 쓰고, 필터 범위를 늘린다.
    서식은 위 줄에서 복사한다."""
    n = after_row + 1
    ws.insert_rows(n)
    for c in range(1, ws.max_column + 1):
        s = ws.cell(after_row, c)
        if s.has_style:
            ws.cell(n, c)._style = copy.copy(s._style)
    ws.cell(n, sc.combined).value = "=CONCATENATE"       # 아래 루프에서 줄 번호에 맞게 채워짐
    for r in range(n, ws.max_row + 1):
        v = ws.cell(r, sc.combined).value
        if isinstance(v, str) and v.startswith("=CONCATENATE"):
            ws.cell(r, sc.combined).value = sc.combined_formula(r)
    if ws.auto_filter.ref:
        ws.auto_filter.ref = re.sub(r"(\d+)$", str(ws.max_row), ws.auto_filter.ref)
    return n


# ── 읽기: 이력 ───────────────────────────────────────────────────────────

class MasterExcel:
    """엑셀을 읽기 전용으로 읽어 병원·제약사 이력을 제공한다. self.rows 는 엑셀 순서(아래쪽이 최근)."""

    hidden = frozenset()      # 병원별로 목록에서 지운 제약사의 memo_key 들 (엑셀 기록은 그대로, 후보·특이사항에서만 뺀다)

    def _is_hidden(self, hospital, pharma):
        return memo_key(hospital, pharma) in self.hidden

    def __init__(self, path: str):
        self.path = path
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = _sheet(wb)
        rows = ws.iter_rows(values_only=True)
        header = [(str(c).strip() if c is not None else "") for c in next(rows)]
        sc = Schema(header)
        i = {k: getattr(sc, k) - 1 for k in Schema.DEFAULTS}
        self.rows = []
        for r in rows:
            if len(r) <= max(i["hospital"], i["pharma"]) or not r[i["hospital"]] or not r[i["pharma"]]:
                continue

            def cell(k):
                return r[i[k]] if len(r) > i[k] else None
            self.rows.append({
                "year": cell("year"), "manager": cell("manager"), "status": cell("status"),
                "hospital": str(cell("hospital")).strip(), "rx_month": str(cell("rx_month") or "").strip(),
                "pharma": clean_pharma(str(cell("pharma"))),
                "input_month": str(cell("input_month") or "").strip(),
                "note": str(cell("note")).strip() if cell("note") else "",
            })
        wb.close()
        self._index()

    def _index(self):
        order = sorted(range(len(self.rows)),
                       key=lambda j: (self.rows[j]["year"] if isinstance(self.rows[j]["year"], int) else 0, j))
        self.names = NameBook.from_names(self.rows[j]["pharma"] for j in order)   # 이름별 가장 최근 표기

    def merged_with(self, other):
        """기본파일 이력에 이번 달 작업본의 줄을 더한 새 객체 (새로 생긴 병원·제약사가 후보에 들어온다)."""
        m = copy.copy(self)
        m.rows = list(self.rows) + list(other.rows)
        m._index()
        return m

    def hospitals(self):
        return list(dict.fromkeys(r["hospital"] for r in self.rows))

    def all_pharmas(self):
        return sorted(set(r["pharma"] for r in self.rows))

    def manager_of(self, hospital):
        return next((r["manager"] for r in self.rows if r["hospital"] == hospital and r["manager"]), None)

    RECENT_MONTHS = 3      # 후보로 치는 기간: 엑셀에서 가장 최근 처방월부터 거슬러 3개월 (옛 자료의 끊긴 제약사 제외)

    @staticmethod
    def _period(r):
        """처방 (연도, 월) 숫자 — '08월'·'8월' 모두 8. 읽을 수 없으면 None.
        연도 열은 입력(정산) 연도라서, 처방월이 입력월보다 크면(12월분을 2월에 입력) 전년도로 본다."""
        m = re.match(r"\d+", r["rx_month"] or "")
        y = r["year"]
        if not m or not isinstance(y, int):
            return None
        rx = int(m.group())
        im = re.match(r"\d+", r["input_month"] or "")
        if im and rx > int(im.group()):
            y -= 1
        return (y, rx)

    def recent_periods(self):
        """가장 최근 처방월부터 RECENT_MONTHS개월의 (연도, 월) 집합."""
        latest = max((p for p in map(self._period, self.rows) if p), default=None)
        if not latest:
            return set()
        y, m = latest
        out = set()
        for _ in range(self.RECENT_MONTHS):
            out.add((y, m))
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        return out

    def hospital_pharmas(self, hospital: str, month: str = None):
        """그 병원에서 최근 3개월 안에 처방이 나온 제약사. 해당 월 항목을 맨 앞에, 나머지는 빈도순."""
        recent = self.recent_periods()
        cnt = Counter(r["pharma"] for r in self.rows
                      if r["hospital"] == hospital and self._period(r) in recent
                      and not self._is_hidden(hospital, r["pharma"]))
        cur = list(dict.fromkeys(r["pharma"] for r in self.rows
                                 if r["hospital"] == hospital and r["rx_month"] == month
                                 and not self._is_hidden(hospital, r["pharma"])))
        return cur + [p for p, _ in cnt.most_common() if p not in cur]

    def pharmas_for(self, hospital: str, month: str, year=None):
        """해당 병원·처방월에 엑셀에 올라 있는 제약사 (엑셀 순서 유지)."""
        return list(dict.fromkeys(
            r["pharma"] for r in self.rows
            if r["hospital"] == hospital and r["rx_month"] == month and (year is None or r["year"] == year)
            and not self._is_hidden(hospital, r["pharma"])))

    def notes_for(self, hospital, memos=None, month=None):
        """그 병원의 제약사별 특이사항 [{pharma, note, tag}] 을 가나다순으로.
        note = 프로그램에서 고친 메모(memos) > 엑셀 특이사항 열의 가장 최근 값(이전 달 것은 tag로 출처 표시)."""
        memos = memos or {}
        groups = {}
        for r in self.rows:
            if r["hospital"] != hospital or self._is_hidden(hospital, r["pharma"]):
                continue
            g = groups.setdefault(norm(r["pharma"]), {"pharma": r["pharma"], "note": "", "tag": ""})
            g["pharma"] = r["pharma"]
            if r["note"]:
                g["note"] = r["note"]
                g["tag"] = "" if (month and r["rx_month"] == month) else f"{r['rx_month']} 기록"
        out = []
        for g in groups.values():
            key = memo_key(hospital, g["pharma"])
            if key in memos:
                g["note"], g["tag"] = memos[key], ""
            out.append(g)
        out.sort(key=lambda g: norm(g["pharma"]))
        return out

    def match_pharma(self, raw, hospital=None, prefer=None, threshold=0.6):
        """사진에서 읽은 글자와 가장 비슷한 제약사 (이름, 유사도). 그 병원 제약사는 점수를 조금 더 쳐준다."""
        favored = set()
        if hospital and hospital in set(self.hospitals()):
            favored = {norm(p) for p in self.hospital_pharmas(hospital)}
        return self.names.closest(raw, prefer, favored, threshold)

    def guess_from_filename(self, path):
        """사진 파일명에서 병원명(과 제약사명)을 추측한다. 못 찾으면 (None, None)."""
        stem = Path(path).stem
        tokens = [norm(t) for t in re.split(r"[\s_\-()\[\].,]+", stem)]
        tokens = [t for t in tokens if len(t) >= 2 and not t.isdigit()]
        whole = norm(stem)
        best, best_score = None, 0.0
        for h in self.hospitals():
            nh = norm(h)
            if len(nh) >= 2 and nh in whole:
                score = len(nh) + 100            # 병원명 전체가 들어 있으면 최우선
            else:
                score = max((len(t) for t in tokens if t in nh), default=0)
            if score > best_score:
                best, best_score = h, score
        if not best:
            return None, None
        pharma = None
        for p in self.hospital_pharmas(best):
            if len(norm(p)) >= 2 and norm(p) in whole and (pharma is None or len(p) > len(pharma)):
                pharma = p
        return best, pharma


# ── 쓰기 ─────────────────────────────────────────────────────────────────

def mark_done(path, hospital, month, year, pharma, input_month=None, manager_hint=None, status=DONE):
    """저장한 사진 1장을 엑셀 파일(path)에 반영한다. status는 '입력완료'(기본) 또는 '정산불가'.
    해당 병원·처방월·제약사의 '아직 입력완료/정산불가가 아닌' 첫 줄을 status로 바꾸고,
    없으면(새 제약사 / 같은 제약사 추가 사진) 같은 건의 마지막 줄 바로 아래에, 그런 줄도 없으면 맨 아래에 새 줄을 넣는다.
    반환: ("updated"|"added", 줄 번호)."""
    wb = openpyxl.load_workbook(path)                    # 수식·데이터검증 유지를 위해 read_only 아님
    ws = _sheet(wb)
    sc = Schema.of(ws)
    last, free, last_same, manager = 1, None, None, manager_hint
    for r in range(2, ws.max_row + 1):
        host = ws.cell(r, sc.hospital).value
        if not host:
            continue
        last = r
        if str(host).strip() != hospital:
            continue
        manager = ws.cell(r, sc.manager).value or manager
        if (_text(ws, r, sc.rx_month) == month and ws.cell(r, sc.year).value == year
                and norm(clean_pharma(_text(ws, r, sc.pharma))) == norm(pharma)):
            last_same = r
            if free is None and ws.cell(r, sc.status).value not in FINISHED:
                free = r
    if free is not None:
        ws.cell(free, sc.status).value = status
        if not ws.cell(free, sc.input_month).value and input_month:
            ws.cell(free, sc.input_month).value = input_month
        result = ("updated", free)
    else:
        n = insert_row_after(ws, sc, last_same or last)
        for col, val in ((sc.year, year), (sc.manager, manager), (sc.status, status), (sc.hospital, hospital),
                         (sc.rx_month, month), (sc.input_month, input_month), (sc.pharma, pharma)):
            ws.cell(n, col).value = val                  # 제약사명 끝에 번호는 붙이지 않는다 (줄 수 = 건수)
        result = ("added", n)
    wb.calculation.fullCalcOnLoad = True
    wb.save(path)
    wb.close()
    return result


def create_work_file(base_path, work_path, input_month, header_only=False):
    """기본파일에서 '이번 달 정산분(입력월 = input_month, 가장 최근 연도)'만 담은 작업 엑셀을 만든다.
    나머지 달 데이터는 빼서 이번 달 입력분만 보이게 한다 (서식·수식·상태 드롭다운 유지). 담은 줄 수를 반환."""
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = openpyxl.load_workbook(base_path)
    ws = _sheet(wb)
    sc = Schema.of(ws)
    rows = [r for r in range(2, ws.max_row + 1)
            if ws.cell(r, sc.hospital).value and _text(ws, r, sc.input_month) == input_month]
    years = [ws.cell(r, sc.year).value for r in rows if isinstance(ws.cell(r, sc.year).value, int)]
    if years:
        rows = [r for r in rows if ws.cell(r, sc.year).value == max(years)]
    if header_only:
        rows = []
    ncol = ws.max_column
    for i, r in enumerate(rows, start=2):                # 위로 당겨 쓰기 (i <= r 이라 안전)
        if i == r:
            continue
        for c in range(1, ncol + 1):
            s, d = ws.cell(r, c), ws.cell(i, c)
            d.value = s.value
            if s.has_style:
                d._style = copy.copy(s._style)
    first_extra = len(rows) + 2
    if ws.max_row >= first_extra:
        ws.delete_rows(first_extra, ws.max_row - first_extra + 1)
    for i in range(2, len(rows) + 2):                    # 통합 수식 줄 번호 맞춤
        v = ws.cell(i, sc.combined).value
        if isinstance(v, str) and v.startswith("=CONCATENATE"):
            ws.cell(i, sc.combined).value = sc.combined_formula(i)
    status_formula = next((dv.formula1 for dv in ws.data_validations.dataValidation
                           if dv.type == "list" and dv.formula1 and DONE in dv.formula1), None)
    ws.data_validations.dataValidation = []
    if status_formula:
        dv = DataValidation(type="list", formula1=status_formula, allow_blank=True)
        col = get_column_letter(sc.status)
        dv.add(f"{col}2:{col}2000")
        ws.add_data_validation(dv)
    ws.auto_filter.ref = f"A1:{get_column_letter(ncol)}{max(2, len(rows) + 1)}"
    wb.calculation.fullCalcOnLoad = True
    wb.save(work_path)
    wb.close()
    return len(rows)


def set_notes(path, hospital, pharma, text):
    """엑셀(path)에서 그 병원·제약사 줄들의 특이사항을 text로 바꾼다 (월 무관). 바꾼 줄 수 반환."""
    wb = openpyxl.load_workbook(path)
    ws = _sheet(wb)
    sc = Schema.of(ws)
    n = 0
    for r in range(2, ws.max_row + 1):
        if pair_matches(ws, sc, r, hospital, pharma):
            ws.cell(r, sc.note).value = text or None
            n += 1
    if n:
        wb.save(path)
    wb.close()
    return n


def merge_into_base(work_path: str, base_path: str):
    """작업 엑셀의 '입력완료' 줄을 기본파일에 반영한다.
    같은 건((연도, 병원, 처방월, 제약사)) 개수가 맞을 때까지 기본파일의 미완료 줄을 입력완료로 바꾸고(입력월이 비면 채움),
    모자라면 같은 건 마지막 줄 바로 아래(없으면 맨 아래)에 새 줄을 넣는다. 여러 번 실행해도 중복 추가가 없다.
    작업본에서 고친 특이사항은 기본파일의 같은 건 마지막 줄에 반영한다. 하루 한 번 백업을 남긴다.
    반환: (상태변경 수, 추가 수)."""
    base = Path(base_path)
    bak = base.parent / "백업" / f"{base.stem}_({datetime.date.today():%y%m%d}){base.suffix}"
    if not bak.exists():
        bak.parent.mkdir(exist_ok=True)
        shutil.copy2(base, bak)

    wwb = openpyxl.load_workbook(work_path, data_only=False)
    wws = _sheet(wwb)
    bwb = openpyxl.load_workbook(base_path)
    bws = _sheet(bwb)
    ws_sc, bs_sc = Schema.of(wws), Schema.of(bws)

    brows = defaultdict(list)                  # 건 -> 기본파일 줄 번호들
    last = 1
    for r in range(2, bws.max_row + 1):
        if bws.cell(r, bs_sc.hospital).value:
            last = r
            brows[row_key(bws, bs_sc, r)].append(r)
    wrows = defaultdict(list)                  # 건 -> 작업본의 입력완료 줄들
    for r in range(2, wws.max_row + 1):
        if wws.cell(r, ws_sc.hospital).value and wws.cell(r, ws_sc.status).value in FINISHED:
            wrows[row_key(wws, ws_sc, r)].append(r)

    updated = added = 0
    for k, wlist in wrows.items():
        rows = brows.get(k, [])
        need = len(wlist) - sum(1 for b in rows if bws.cell(b, bs_sc.status).value in FINISHED)
        todo = wlist[len(wlist) - need:] if need > 0 else []      # 기본파일에 아직 없는 작업본 줄들
        for b in [b for b in rows if bws.cell(b, bs_sc.status).value not in FINISHED]:
            if not todo:
                break
            w = todo.pop(0)
            bws.cell(b, bs_sc.status).value = wws.cell(w, ws_sc.status).value
            if not bws.cell(b, bs_sc.input_month).value:
                bws.cell(b, bs_sc.input_month).value = wws.cell(wlist[0], ws_sc.input_month).value
            updated += 1
        for r in todo:
            n = insert_row_after(bws, bs_sc, max(rows) if rows else last)
            for kk, lst in brows.items():      # 끼워 넣은 만큼 뒤 줄 번호 밀기
                brows[kk] = [x + 1 if x >= n else x for x in lst]
            rows = brows[k] = sorted(brows.get(k, []) + [n])
            last += 1
            for wc, bc in zip(ws_sc.copy_cols, bs_sc.copy_cols):
                bws.cell(n, bc).value = wws.cell(r, wc).value
            added += 1

    latest_row = {}
    for r in range(2, bws.max_row + 1):
        if bws.cell(r, bs_sc.hospital).value:
            latest_row[row_key(bws, bs_sc, r)] = r
    notes = {row_key(wws, ws_sc, r): str(wws.cell(r, ws_sc.note).value).strip()
             for r in range(2, wws.max_row + 1)
             if wws.cell(r, ws_sc.hospital).value and wws.cell(r, ws_sc.note).value}
    for k, text in notes.items():
        b = latest_row.get(k)
        if b and _text(bws, b, bs_sc.note) != text:
            bws.cell(b, bs_sc.note).value = text
    bwb.calculation.fullCalcOnLoad = True
    bwb.save(base_path)
    wwb.close()
    bwb.close()
    return updated, added


def clean_names(path: str, backup_dir=None) -> int:
    """제약사명 열의 끝 번호('명문제약 (2)', '명문제약2')를 모두 지운다. 지운 셀 수를 반환(0이면 파일을 건드리지 않음)."""
    wb = openpyxl.load_workbook(path)
    ws = _sheet(wb)
    sc = Schema.of(ws)
    todo = []
    for r in range(2, ws.max_row + 1):
        v = ws.cell(r, sc.pharma).value
        if isinstance(v, str) and clean_pharma(v) != v.strip():
            todo.append((r, clean_pharma(v)))
    if not todo:
        wb.close()
        return 0
    src = Path(path)
    bdir = Path(backup_dir) if backup_dir else src.parent / "백업"
    bdir.mkdir(exist_ok=True)
    shutil.copy2(src, bdir / f"{src.stem}_번호제거전_({datetime.date.today():%y%m%d}){src.suffix}")
    for r, name in todo:
        ws.cell(r, sc.pharma).value = name
    wb.calculation.fullCalcOnLoad = True
    wb.save(path)
    wb.close()
    return len(todo)


# ── 장부: 화면이 쓰는 단 하나의 입구 ─────────────────────────────────────

LedgerEvent = namedtuple("LedgerEvent", "kind message")     # kind: "done" | "note" | "error"


class Ledger:
    """기본파일(이력) + 이번 달 작업 엑셀을 묶어 다룬다.

    쓰기(입력완료 표시·메모)는 한 줄 스레드에서 차례로 처리해 화면이 멈추지 않는다.
    화면은 주기적으로 poll() 해서 끝난 일의 결과를 받는다. 같은 사진을 같은 이름으로 다시 저장하면 중복 반영하지 않는다.
    """

    def __init__(self, base_path):
        self.base = Path(base_path)
        self.work = None                       # 이번 달 작업 엑셀 경로 (없을 수 있음)
        self._base_master = None
        self._master = None
        self._jobs = queue.Queue()
        self._events = queue.Queue()
        self._marked = {}                      # 사진 -> 이미 반영한 (병원, 월, 제약사)
        self.hidden = set()                    # 병원별로 목록에서 지운 제약사 (memo_key) — 새로 저장하면 다시 나타난다
        self.pending = 0
        threading.Thread(target=self._run, daemon=True).start()

    # 이력
    @property
    def master(self):
        if self._master is not None:
            self._master.hidden = self.hidden            # 항상 최신 '지운 목록'을 따르게 한다
        return self._master

    def load(self):
        """기본파일을 (다시) 읽는다. 실패하면 예외."""
        self._base_master = MasterExcel(str(self.base))
        self._rebuild()

    def set_work_path(self, path):
        self.work = Path(path) if path else None
        self._rebuild()

    def _rebuild(self):
        if not self._base_master:
            return
        self._master = self._base_master
        if self.work and self.work.exists():
            try:
                self._master = self._base_master.merged_with(MasterExcel(str(self.work)))
            except Exception:
                pass

    # 쓰기 (백그라운드)
    def record_done(self, photo, hospital, month, year, pharma, input_month, status=DONE):
        """사진 한 장을 입력완료(또는 정산불가)로 반영하도록 맡긴다. 이미 같은 내용으로 반영했으면 False."""
        key = (hospital, month, pharma, status)
        self.hidden.discard(memo_key(hospital, pharma))      # 지웠던 제약사도 새로 저장하면 다시 목록에 나타난다
        if self._marked.get(photo) == key:
            return False
        self._marked[photo] = key
        mgr = self._master.manager_of(hospital) if self._master else None
        self.pending += 1
        self._jobs.put(("done", photo, key, self.work, year, input_month, mgr))
        return True

    def set_note(self, hospital, pharma, text):
        """특이사항을 이번 달 작업 엑셀에 반영하도록 맡긴다 (작업 엑셀이 아직 없으면 할 일 없음 → False)."""
        if not (self.work and self.work.exists()):
            return False
        self.pending += 1
        self._jobs.put(("note", None, (hospital, pharma, text), self.work, None, None, None))
        return True

    def poll(self):
        """끝난 일의 결과를 모두 꺼낸다 (화면 스레드에서 호출). 이력이 바뀌었으면 self.master 도 갱신돼 있다."""
        out = []
        try:
            while True:
                kind, photo, key, payload = self._events.get_nowait()
                self.pending -= 1
                if kind == "done":
                    result, work_master = payload
                    self._master = (self._base_master.merged_with(work_master) if self._base_master else work_master)
                    out.append(LedgerEvent("done", f"{self.work.name if self.work else ''} {result[1]}행 "
                                                   + (f"{key[3]}로 변경" if result[0] == "updated" else f"{key[3]} 새 행 추가")))
                elif kind == "note":
                    out.append(LedgerEvent("note", ""))
                else:
                    if photo is not None and self._marked.get(photo) == key:
                        del self._marked[photo]            # 다시 저장하면 다시 반영되게
                    out.append(LedgerEvent("error", payload))
        except queue.Empty:
            pass
        return out

    def wait(self):
        """진행 중인 쓰기가 모두 끝날 때까지 기다린다 (창 닫기 직전)."""
        self._jobs.join()

    def complete(self):
        """통계완료: 작업 엑셀의 내용을 기본파일에 병합한다. 반영 중인 일이 있으면 RuntimeError. (상태변경 수, 추가 수) 반환."""
        if self.pending:
            raise RuntimeError("엑셀에 반영 중인 저장 건이 있습니다.")
        if not (self.work and self.work.exists()):
            raise FileNotFoundError("반영할 통계입력 엑셀이 없습니다.")
        result = merge_into_base(str(self.work), str(self.base))
        self.load()
        return result

    def _run(self):
        while True:
            kind, photo, key, work, year, input_month, mgr = self._jobs.get()
            try:
                if kind == "note":
                    set_notes(str(work), *key)
                    self._events.put(("note", None, None, None))
                else:
                    hospital, month, pharma, status = key
                    if not work.exists():
                        work.parent.mkdir(parents=True, exist_ok=True)
                        create_work_file(str(self.base), str(work), input_month)   # 이번 달 정산분만 담아 시작
                    result = mark_done(str(work), hospital, month, year, pharma, input_month, mgr, status)
                    self._events.put(("done", photo, key, (result, MasterExcel(str(work)))))
            except PermissionError:
                self._events.put(("error", photo, key, f"{Path(work).name} 이(가) 열려 있습니다. 닫고 다시 저장하세요."))
            except Exception as e:
                self._events.put(("error", photo, key, str(e)))
            finally:
                self._jobs.task_done()
