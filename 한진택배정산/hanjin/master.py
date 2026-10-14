"""송하인마스터.xlsx: 호실·전화번호와 동일인 판정을 누적 학습한다.

사용자가 엑셀에서 직접 고쳐도 다음 실행 때 그대로 읽는다.
"""
from __future__ import annotations

import copy
import shutil
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from .engine import resolve

SENDER_SHEET = "송하인"
ALIAS_SHEET = "별칭판정"
SENDER_COLS = ["대표명", "호실", "전화번호", "메모", "최초등록일", "최근정산월"]
ALIAS_COLS = ["원본이름", "원본전화(마스킹)", "대표명", "판정", "판정일"]
SAME, DIFFERENT = "같음", "다름"
BACKUP_KEEP = 30


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class MasterLockedError(Exception):
    pass


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _phone_text(v) -> str:
    s = _text(v)
    # 엑셀이 숫자로 바꿔 앞자리 0이 사라진 번호 복구 (1012345678 → 01012345678)
    if s.isdigit() and not s.startswith("0") and len(s) in (9, 10):
        s = "0" + s
    return s


class Master:
    def __init__(self, path: Path, backup_dir: Path):
        self.path = Path(path)
        self.backup_dir = Path(backup_dir)
        self.senders: dict[str, dict] = {}
        self.aliases: list[dict] = []
        self.load()

    # ── 읽기 ──
    def load(self):
        self.senders, self.aliases = {}, []
        if not self.path.exists():
            return
        try:
            wb = load_workbook(self.path, data_only=True)
        except PermissionError:
            raise MasterLockedError("송하인마스터.xlsx를 읽을 수 없습니다. 엑셀에서 파일을 닫고 다시 시도하세요.")
        if SENDER_SHEET in wb.sheetnames:
            for row in self._rows(wb[SENDER_SHEET]):
                name = _text(row.get("대표명"))
                if name:
                    rec = {c: _text(row.get(c)) for c in SENDER_COLS}
                    rec["전화번호"] = _phone_text(row.get("전화번호"))
                    self.senders[name] = rec
        if ALIAS_SHEET in wb.sheetnames:
            for row in self._rows(wb[ALIAS_SHEET]):
                rec = {c: _text(row.get(c)) for c in ALIAS_COLS}
                if rec["원본이름"] and rec["대표명"] and rec["판정"] in (SAME, DIFFERENT):
                    self.aliases.append(rec)
        wb.close()
        self._flatten()  # 엑셀에서 직접 고쳐 생긴 여러 단계 체인을 정리

    @staticmethod
    def _rows(ws):
        it = ws.iter_rows(values_only=True)
        header = next(it, None)
        if not header:
            return
        header = [_text(h) for h in header]
        for values in it:
            if any(v not in (None, "") for v in values):
                yield dict(zip(header, values))

    # ── 엔진에 넘길 판정 ──
    def alias_map(self) -> dict[str, str]:
        return {a["원본이름"]: a["대표명"] for a in self.aliases
                if a["판정"] == SAME and a["원본이름"] != a["대표명"]}

    def different_pairs(self) -> set[frozenset]:
        return {frozenset((a["원본이름"], a["대표명"])) for a in self.aliases if a["판정"] == DIFFERENT}

    # ── 변경 ──
    # 같음 판정은 항상 '원본이름 → 최상위 대표명' 한 단계로 유지한다(_flatten).
    # 그래서 묶음 안의 이름 하나를 옮기거나 떼어내도 다른 이름이 딸려가지 않는다.

    def clone(self) -> "Master":
        """동일인 정리 창에서 [저장] 전까지 고쳐 볼 사본."""
        return copy.deepcopy(self)

    def assign(self, name: str, rep: str, phone: str = ""):
        """name을 rep 묶음에 넣는다. name이 다른 이름들의 대표였다면 그 묶음 전체가 rep로 옮겨간다."""
        rep = resolve(rep, self.alias_map())
        if name == rep:
            return
        for a in self.aliases:
            if a["판정"] == SAME and a["대표명"] == name:
                a["대표명"] = rep
        self.aliases = [a for a in self.aliases if not (
            (a["판정"] == SAME and a["원본이름"] == name)
            or (a["판정"] == DIFFERENT and {a["원본이름"], a["대표명"]} == {name, rep}))]
        self.aliases.append({"원본이름": name, "원본전화(마스킹)": phone, "대표명": rep,
                             "판정": SAME, "판정일": _today()})
        self._move_sender_info(name, rep)
        self._flatten()

    def split(self, name: str):
        """묶음에서 name만 떼어 독립 송하인으로."""
        self.aliases = [a for a in self.aliases if not (a["판정"] == SAME and a["원본이름"] == name)]

    def make_rep(self, name: str):
        """name이 속한 묶음의 대표명을 name으로 바꾼다."""
        root = resolve(name, self.alias_map())
        if root == name:
            return
        phone = next((a["원본전화(마스킹)"] for a in self.aliases if a["원본이름"] == name), "")
        self.split(name)
        self.assign(root, name, phone)

    def record_same(self, loser: str, winner: str, phone: str):
        """loser가 속한 묶음 전체를 winner 묶음으로 합친다."""
        amap = self.alias_map()
        loser, winner = resolve(loser, amap), resolve(winner, amap)
        if loser != winner:
            self.assign(loser, winner, phone)

    def record_different(self, other: str, base: str, phone: str):
        self.undo_different(other, base)
        self.aliases.append({"원본이름": other, "원본전화(마스킹)": phone, "대표명": base,
                             "판정": DIFFERENT, "판정일": _today()})

    def undo_different(self, a: str, b: str):
        self.aliases = [x for x in self.aliases
                        if not (x["판정"] == DIFFERENT and {x["원본이름"], x["대표명"]} == {a, b})]

    def remove_alias(self, rec: dict):
        """저장된 판정 한 줄 취소."""
        self.aliases = [a for a in self.aliases if a is not rec]

    def _flatten(self):
        amap = self.alias_map()
        for a in self.aliases:
            if a["판정"] == SAME:
                a["대표명"] = resolve(a["대표명"], amap)
        self.aliases = [a for a in self.aliases if not (a["판정"] == SAME and a["원본이름"] == a["대표명"])]

    def _move_sender_info(self, src: str, dst: str):
        lost = self.senders.pop(src, None)
        if not lost:
            return
        win = self.senders.setdefault(dst, self._new_sender(dst))
        for c in ("호실", "전화번호", "메모"):
            if not win.get(c) and lost.get(c):
                win[c] = lost[c]
        if lost.get("최초등록일") and (not win.get("최초등록일") or lost["최초등록일"] < win["최초등록일"]):
            win["최초등록일"] = lost["최초등록일"]

    def _new_sender(self, name: str) -> dict:
        rec = dict.fromkeys(SENDER_COLS, "")
        rec["대표명"] = name
        rec["최초등록일"] = datetime.now().strftime("%Y-%m-%d")
        return rec

    def set_sender_field(self, name: str, column: str, value: str):
        rec = self.senders.setdefault(name, self._new_sender(name))
        rec[column] = value.strip()

    def touch_senders(self, names, month_label: str):
        """정산에 나온 송하인을 등록하고 최근정산월을 갱신."""
        for n in names:
            rec = self.senders.setdefault(n, self._new_sender(n))
            if not rec.get("최근정산월") or rec["최근정산월"] < month_label:
                rec["최근정산월"] = month_label

    # ── 저장 ──
    def save(self):
        self._check_writable()
        self._backup()
        wb = Workbook()
        ws = wb.active
        ws.title = SENDER_SHEET
        self._write_sheet(ws, SENDER_COLS, [self.senders[k] for k in sorted(self.senders)],
                          widths=[22, 10, 16, 30, 12, 12], text_cols={"전화번호", "호실"})
        ws2 = wb.create_sheet(ALIAS_SHEET)
        self._write_sheet(ws2, ALIAS_COLS, self.aliases, widths=[22, 16, 22, 8, 12])
        tmp = self.path.with_suffix(".tmp.xlsx")
        wb.save(tmp)
        tmp.replace(self.path)

    @staticmethod
    def _write_sheet(ws, cols, rows, widths, text_cols=()):
        ws.append(cols)
        for c in ws[1]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="F1F1EF")
        for r in rows:
            ws.append([r.get(c, "") for c in cols])
        for i, w in enumerate(widths):
            ws.column_dimensions[chr(65 + i)].width = w
        for i, c in enumerate(cols):
            if c in text_cols:
                for cell in ws.iter_cols(min_col=i + 1, max_col=i + 1, min_row=2):
                    for x in cell:
                        x.number_format = "@"
        ws.freeze_panes = "A2"

    def _check_writable(self):
        if not self.path.exists():
            return
        try:
            with open(self.path, "r+b"):
                pass
        except PermissionError:
            raise MasterLockedError("송하인마스터.xlsx가 엑셀에서 열려 있어 저장할 수 없습니다. 엑셀에서 파일을 닫고 다시 시도하세요.")

    def _backup(self):
        if not self.path.exists():
            return
        self.backup_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self.backup_dir / f"송하인마스터_{stamp}.xlsx"
        if not dest.exists():
            shutil.copy2(self.path, dest)
        backups = sorted(self.backup_dir.glob("송하인마스터_*.xlsx"))
        for old in backups[:-BACKUP_KEEP]:
            old.unlink(missing_ok=True)
