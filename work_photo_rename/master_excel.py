"""기본(마스터) 엑셀 읽기. '통계 참고파일.xlsx'의 '통계입력확인' 시트 구조:
연도 | 담당자명 | 상태(헤더 없음) | 거래처명 | 처방월 | 입력월 | 제약사명 | 통합(수식) | ... | 특이사항
헤더 이름으로 열을 찾는다 (3번째 열은 헤더가 비어 있어 '상태'로 간주)."""
import re

import openpyxl

from labeling import clean_pharma
from suggest_entry import norm


def memo_key(hospital, pharma):
    return f"{hospital.strip()}|{norm(pharma)}"


def create_work_file(base_path, work_path, input_month, header_only=False):
    """기본파일에서 '이번 달 정산분(입력월 = input_month, 가장 최근 연도)'만 담은 작업 엑셀을 만든다.
    나머지 달 데이터는 빼서 이번 달 입력분만 보이게 한다 (서식·수식·상태 드롭다운 유지)."""
    from copy import copy
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = openpyxl.load_workbook(base_path)
    ws = wb["통계입력확인"] if "통계입력확인" in wb.sheetnames else wb.active
    rows = [r for r in range(2, ws.max_row + 1)
            if ws.cell(r, 4).value and str(ws.cell(r, 6).value or "").strip() == input_month]
    years = [ws.cell(r, 1).value for r in rows if isinstance(ws.cell(r, 1).value, int)]
    if years:
        ymax = max(years)
        rows = [r for r in rows if ws.cell(r, 1).value == ymax]
    if header_only:
        rows = []
    ncol = ws.max_column
    for i, r in enumerate(rows, start=2):               # 위로 당겨 쓰기 (i <= r 이라 안전)
        if i == r:
            continue
        for c in range(1, ncol + 1):
            s, d = ws.cell(r, c), ws.cell(i, c)
            d.value = s.value
            if s.has_style:
                d._style = copy(s._style)
    first_extra = len(rows) + 2
    if ws.max_row >= first_extra:
        ws.delete_rows(first_extra, ws.max_row - first_extra + 1)
    for i in range(2, len(rows) + 2):                   # 통합 수식 행번호 맞춤
        if isinstance(ws.cell(i, 8).value, str) and ws.cell(i, 8).value.startswith("=CONCATENATE"):
            ws.cell(i, 8).value = f'=CONCATENATE(D{i}," ",E{i}," ",G{i})'
    status_formula = None
    for dv in ws.data_validations.dataValidation:
        if dv.type == "list" and dv.formula1 and "입력완료" in dv.formula1:
            status_formula = dv.formula1
            break
    ws.data_validations.dataValidation = []
    if status_formula:
        dv = DataValidation(type="list", formula1=status_formula, allow_blank=True)
        dv.add("C2:C2000")
        ws.add_data_validation(dv)
    ws.auto_filter.ref = f"A1:{ws.cell(1, ncol).column_letter}{max(2, len(rows) + 1)}"
    wb.calculation.fullCalcOnLoad = True
    wb.save(work_path)
    wb.close()
    return len(rows)


def set_notes(work_path, hospital, pharma, text):
    """작업 엑셀에서 그 병원·제약사 행(이번 달 정산분)의 특이사항(J열)을 text로 바꾼다. 바꾼 행 수 반환."""
    wb = openpyxl.load_workbook(work_path)
    ws = wb["통계입력확인"] if "통계입력확인" in wb.sheetnames else wb.active
    n = 0
    for r in range(2, ws.max_row + 1):
        if (str(ws.cell(r, 4).value or "").strip() == hospital
                and norm(clean_pharma(str(ws.cell(r, 7).value or ""))) == norm(pharma)):
            ws.cell(r, 10).value = text or None
            n += 1
    if n:
        wb.save(work_path)
    wb.close()
    return n


def _insert_row_after(ws, after_row):
    """after_row 바로 아래에 빈 행을 끼워 넣고 그 행 번호를 돌려준다.
    openpyxl의 insert_rows는 수식을 고쳐 주지 않으므로 H열(CONCATENATE) 수식을 행 번호에 맞게 다시 쓰고,
    필터 범위를 한 줄 늘린다. 서식은 위 행에서 복사한다."""
    from copy import copy
    n = after_row + 1
    ws.insert_rows(n)
    for c in range(1, ws.max_column + 1):
        s = ws.cell(after_row, c)
        if s.has_style:
            ws.cell(n, c)._style = copy(s._style)
    ws.cell(n, 8).value = "=CONCATENATE"                 # 아래 루프에서 행 번호에 맞게 채워짐
    for r in range(n, ws.max_row + 1):
        v = ws.cell(r, 8).value
        if isinstance(v, str) and v.startswith("=CONCATENATE"):
            ws.cell(r, 8).value = f'=CONCATENATE(D{r}," ",E{r}," ",G{r})'
    if ws.auto_filter.ref:
        ws.auto_filter.ref = re.sub(r"(\d+)$", str(ws.max_row), ws.auto_filter.ref)
    return n


class MasterExcel:
    def __init__(self, path: str):
        self.path = path
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb["통계입력확인"] if "통계입력확인" in wb.sheetnames else wb.active
        rows = ws.iter_rows(values_only=True)
        header = [(str(c).strip() if c is not None else "") for c in next(rows)]
        col = {name: i for i, name in enumerate(header) if name}
        i_year, i_mgr = col.get("연도", 0), col.get("담당자명", 1)
        i_host, i_rx = col.get("거래처명", 3), col.get("처방월", 4)
        i_ph = col.get("제약사명", 6)
        i_in, i_note = col.get("입력월", 5), col.get("특이사항", 9)
        self.rows = []
        self.latest = {}              # 정규화한 이름 -> 엑셀에서 가장 최근(연도·아래쪽 행) 표기
        for r in rows:
            if len(r) <= max(i_host, i_ph) or not r[i_host] or not r[i_ph]:
                continue
            self.rows.append({
                "year": r[i_year], "manager": r[i_mgr], "status": r[2] if len(r) > 2 else None,
                "hospital": str(r[i_host]).strip(), "rx_month": str(r[i_rx] or "").strip(),
                "pharma": clean_pharma(str(r[i_ph])),
                "input_month": str(r[i_in] or "").strip() if len(r) > i_in else "",
                "note": str(r[i_note]).strip() if len(r) > i_note and r[i_note] else "",
            })
        wb.close()
        self._index()

    def _index(self):
        best = {}
        for i, r in enumerate(self.rows):
            k = norm(r["pharma"])
            rank = (r["year"] if isinstance(r["year"], int) else 0, i)
            if k and (k not in best or rank >= best[k][0]):
                best[k] = (rank, r["pharma"])
        self.latest = {k: v[1] for k, v in best.items()}

    def merged_with(self, other):
        """이 엑셀(기본파일 이력)에 다른 엑셀(이번 달 작업본)의 행을 더한 새 객체. 새로 생긴 병원·제약사가 후보에 들어온다."""
        import copy
        m = copy.copy(self)
        m.rows = list(self.rows) + list(other.rows)
        m._index()
        return m

    def notes_for(self, hospital, memos=None, month=None):
        """그 병원의 제약사별 특이사항. [{pharma, note, tag}] 를 제약사명 가나다순(괄호·(주) 무시)으로.
        note = 사용자가 프로그램에서 고친 메모(memos) > 엑셀 특이사항 열의 가장 최근 값(이전 달 것을 이월해서 보여줌).
        tag = 이전 달 기록을 이월해 보여줄 때 '9월 기록' 같은 출처."""
        memos = memos or {}
        groups = {}
        for r in self.rows:
            if r["hospital"] != hospital:
                continue
            g = groups.setdefault(norm(r["pharma"]), {"pharma": r["pharma"], "note": "", "tag": ""})
            g["pharma"] = r["pharma"]
            if r["note"]:
                g["note"] = r["note"]
                g["tag"] = "" if (month and r["rx_month"] == month) else f"{r['rx_month']} 기록"
        out = []
        for k, g in groups.items():
            key = memo_key(hospital, g["pharma"])
            if key in memos:
                g["note"], g["tag"] = memos[key], ""
            out.append(g)
        out.sort(key=lambda g: norm(g["pharma"]))
        return out

    def match_pharma(self, raw, hospital=None, prefer=None, threshold=0.6):
        """사진에서 읽은 글자(raw)와 가장 비슷한 제약사 표기를 (이름, 점수)로. 비슷한 게 없으면 (None, 0).
        그 병원에서 처방이 나왔던 제약사는 점수를 조금 더 쳐준다."""
        import difflib
        nr = norm(raw)
        if len(nr) < 2:
            return None, 0.0
        mine = set()
        if hospital and hospital in set(self.hospitals()):
            mine = {norm(p) for p in self.hospital_pharmas(hospital)}
        best, best_s, best_r = None, 0.0, 0.0
        for k in self.latest:
            r = difflib.SequenceMatcher(None, nr, k).ratio()
            s = r + (0.05 if k in mine else 0.0)
            if r >= threshold and s > best_s:
                best, best_s, best_r = k, s, r
        if best is None:
            return None, 0.0
        return (prefer or {}).get(best) or self.latest[best], best_r

    def dedupe(self, names, prefer=None, drop_norms=(), sort=False):
        """'(주)이든파마' / '이든파마(주)' / '이든파마'처럼 정규화하면 같은 이름은 하나만 남긴다.
        남기는 표기: prefer(사용자가 최근 저장한 표기) > 엑셀에서 가장 최근 행의 표기 > 첫 표기.
        names의 순서는 유지(그룹의 첫 자리에 놓음). drop_norms에 있는 이름 그룹은 뺀다."""
        prefer = prefer or {}
        seen, out = set(), []
        for n in names:
            k = norm(n)
            if not k or k in seen or k in drop_norms:
                continue
            seen.add(k)
            out.append(prefer.get(k) or self.latest.get(k) or n)
        if sort:                                   # (주)·기호 무시하고 ㄱㄴㄷ 순
            out.sort(key=norm)
        return out

    def mark_done(self, hospital, month, year, pharma, input_month=None, manager_hint=None):
        """저장한 사진 1장을 엑셀에 반영한다.
        해당 병원·처방월·제약사의 '아직 입력완료가 아닌' 첫 행의 상태를 '입력완료'로 바꾸고,
        그런 행이 없으면(새 제약사 / 같은 제약사 추가 사진) 새 행을 맨 아래에 추가한다.
        self.path 파일을 직접 수정하므로, 호출자가 작업용 복사본을 열어서 써야 한다.
        반환: ("updated"|"added", 행번호)."""
        from copy import copy

        wb = openpyxl.load_workbook(self.path)          # 수식·데이터검증 유지를 위해 read_only 아님
        ws = wb["통계입력확인"] if "통계입력확인" in wb.sheetnames else wb.active
        last = 1
        free = None                                     # 일치하지만 아직 입력완료 아닌 첫 행
        last_same = None                                # 같은 병원·월·제약사의 마지막 행
        manager = manager_hint
        for r in range(2, ws.max_row + 1):
            host = ws.cell(r, 4).value
            if not host:
                continue
            last = r
            if str(host).strip() != hospital:
                continue
            manager = ws.cell(r, 2).value or manager
            if (str(ws.cell(r, 5).value or "").strip() == month and ws.cell(r, 1).value == year
                    and norm(clean_pharma(str(ws.cell(r, 7).value or ""))) == norm(pharma)):
                last_same = r
                if free is None and ws.cell(r, 3).value != "입력완료":
                    free = r
        if free is not None:
            ws.cell(free, 3).value = "입력완료"
            if not ws.cell(free, 6).value and input_month:
                ws.cell(free, 6).value = input_month
            result = ("updated", free)
        else:
            # 같은 병원·월·제약사 줄이 있으면 그 바로 아래에, 없으면(새 제약사) 맨 아래에 추가
            n = _insert_row_after(ws, last_same) if last_same else _insert_row_after(ws, last)
            name = pharma                                # 끝 번호는 붙이지 않는다 (행 수 = 건수)
            ws.cell(n, 1).value = year
            ws.cell(n, 2).value = manager
            ws.cell(n, 3).value = "입력완료"
            ws.cell(n, 4).value = hospital
            ws.cell(n, 5).value = month
            ws.cell(n, 6).value = input_month
            ws.cell(n, 7).value = name
            result = ("added", n)
        wb.calculation.fullCalcOnLoad = True
        wb.save(self.path)
        wb.close()
        return result

    def hospitals(self):
        return list(dict.fromkeys(r["hospital"] for r in self.rows))

    def all_pharmas(self):
        return sorted(set(r["pharma"] for r in self.rows))

    def guess_from_filename(self, path):
        """사진 파일명에서 병원명(과 제약사명)을 추측한다. 못 찾으면 (None, None).
        '노상준.jpg'처럼 병원명의 일부만 있어도 되고, '(주)'·공백·괄호는 무시한다."""
        import re
        from pathlib import Path
        from suggest_entry import norm
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

    def hospital_pharmas(self, hospital: str, month: str = None):
        """그 병원에서 (어느 달이든) 처방이 나온 적 있는 제약사. 해당 월 항목을 맨 앞에, 나머지는 빈도순."""
        from collections import Counter
        cnt = Counter(r["pharma"] for r in self.rows if r["hospital"] == hospital)
        cur = [p for p in dict.fromkeys(r["pharma"] for r in self.rows
                                        if r["hospital"] == hospital and r["rx_month"] == month)]
        rest = [p for p, _ in cnt.most_common() if p not in cur]
        return cur + rest

    def pharmas_for(self, hospital: str, month: str, year=None):
        """해당 병원·처방월에 엑셀에 올라 있는 제약사 (엑셀 순서 유지)."""
        return list(dict.fromkeys(
            r["pharma"] for r in self.rows
            if r["hospital"] == hospital and r["rx_month"] == month
            and (year is None or r["year"] == year)))


def merge_into_base(work_path: str, base_path: str):
    """통계입력(작업) 엑셀에서 '입력완료'인 행을 기본파일에 반영한다.
    키 = (연도, 병원, 처방월, 제약사 원본표기). 기본파일에 있으면 상태만 입력완료로(입력월이 비면 채움),
    없으면 맨 아래에 새 행으로 추가한다. 여러 번 실행해도 같은 결과(중복 추가 없음).
    반환: (상태변경 수, 추가 수)."""
    import datetime
    import shutil
    from copy import copy
    from pathlib import Path

    base = Path(base_path)
    bdir = base.parent / "백업"
    bak = bdir / f"{base.stem}_({datetime.date.today():%y%m%d}){base.suffix}"
    if not bak.exists():
        bdir.mkdir(exist_ok=True)
        shutil.copy2(base, bak)

    def key(ws, r):
        return (ws.cell(r, 1).value, str(ws.cell(r, 4).value or "").strip(),
                str(ws.cell(r, 5).value or "").strip(), norm(clean_pharma(str(ws.cell(r, 7).value or ""))))

    wwb = openpyxl.load_workbook(work_path, data_only=False)
    wws = wwb["통계입력확인"] if "통계입력확인" in wwb.sheetnames else wwb.active
    bwb = openpyxl.load_workbook(base_path)
    bws = bwb["통계입력확인"] if "통계입력확인" in bwb.sheetnames else bwb.active

    from collections import defaultdict
    brows = defaultdict(list)                 # 키 -> 기본파일 행 번호들 (같은 키가 여러 행일 수 있음)
    last = 1
    for r in range(2, bws.max_row + 1):
        if bws.cell(r, 4).value:
            last = r
            brows[key(bws, r)].append(r)
    wrows = defaultdict(list)                 # 키 -> 작업파일의 입력완료 행들
    for r in range(2, wws.max_row + 1):
        if wws.cell(r, 4).value and wws.cell(r, 3).value == "입력완료":
            wrows[key(wws, r)].append(r)

    updated = added = 0
    for k, wlist in wrows.items():
        rows = brows.get(k, [])
        need = len(wlist) - sum(1 for b in rows if bws.cell(b, 3).value == "입력완료")
        for b in [b for b in rows if bws.cell(b, 3).value != "입력완료"]:
            if need <= 0:
                break
            bws.cell(b, 3).value = "입력완료"
            if not bws.cell(b, 6).value:
                bws.cell(b, 6).value = wws.cell(wlist[0], 6).value
            updated += 1
            need -= 1
        for r in wlist[len(wlist) - need:] if need > 0 else []:
            anchor = max(rows) if rows else last         # 같은 키 줄 바로 아래, 없으면 맨 아래
            n = _insert_row_after(bws, anchor)
            for kk, lst in brows.items():                # 끼워 넣은 만큼 뒤 행 번호 밀기
                brows[kk] = [x + 1 if x >= n else x for x in lst]
            rows = brows[k] = sorted(brows.get(k, []) + [n])
            last = last + 1
            for c in (1, 2, 3, 4, 5, 6, 7, 10):
                bws.cell(n, c).value = wws.cell(r, c).value
            added += 1
    # 특이사항(J열): 작업본에서 고친 메모를 기본파일의 같은 병원·월·제약사 마지막 행에 반영
    latest_row = {}
    for r in range(2, bws.max_row + 1):
        if bws.cell(r, 4).value:
            latest_row[key(bws, r)] = r
    notes = {}
    for r in range(2, wws.max_row + 1):
        if wws.cell(r, 4).value and wws.cell(r, 10).value:
            notes[key(wws, r)] = str(wws.cell(r, 10).value).strip()
    for k, text in notes.items():
        b = latest_row.get(k)
        if b and str(bws.cell(b, 10).value or "").strip() != text:
            bws.cell(b, 10).value = text
    bwb.calculation.fullCalcOnLoad = True
    bwb.save(base_path)
    wwb.close()
    bwb.close()
    return updated, added


def clean_names(path: str, backup_dir=None) -> int:
    """제약사명 열의 끝 번호('명문제약 (2)', '명문제약2')를 모두 지운다. 지운 셀 수를 반환(0이면 파일을 건드리지 않음)."""
    import datetime
    import shutil
    from pathlib import Path

    wb = openpyxl.load_workbook(path)
    ws = wb["통계입력확인"] if "통계입력확인" in wb.sheetnames else wb.active
    todo = []
    for r in range(2, ws.max_row + 1):
        v = ws.cell(r, 7).value
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
        ws.cell(r, 7).value = name
    wb.calculation.fullCalcOnLoad = True
    wb.save(path)
    wb.close()
    return len(todo)
