"""정산 엔진: 파일 읽기 → 정산 주체 판별 → 동일인 후보 → 집계·검증.

화면·엑셀 쓰기와 분리된 순수 로직이다. 송하인 마스터의 판정(별칭)은
`aliases`(원본이름 → 대표명)와 `different_pairs`(다른 사람 판정 쌍)로 받는다.
"""
from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

AMOUNT_COLS = ["운임", "사합비", "할증료", "기타비용"]
REQUIRED_COLS = [
    "운송장번호", "수량", *AMOUNT_COLS, "지불조건",
    "송하인명", "송하인전화번호", "수하인명", "수하인전화번호",
    "출고일", "현재상태",
]
OPTIONAL_COLS = ["품목명", "인보이스"]

KIND_SEND = "발송"
KIND_RETURN = "착신(반품)"
KIND_UNKNOWN = "미분류"
KIND_ORDER = [KIND_SEND, KIND_RETURN, KIND_UNKNOWN]


class DataError(Exception):
    """사용자에게 그대로 보여줄 한국어 오류."""


# ── 파일 읽기 ────────────────────────────────────────────────

def _read_csv(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    raise DataError(f"{path.name}: CSV 인코딩을 알 수 없습니다(UTF-8/CP949 아님).")


def _read_raw(path: Path, header) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        df = _read_csv(path)
        if header:
            df.columns = df.iloc[header - 1].astype(str)
            df = df.iloc[header:]
        return df
    if ext in (".xlsx", ".xlsm"):
        return pd.read_excel(path, dtype=str, header=header, engine="openpyxl", keep_default_na=False)
    if ext == ".xls":
        return pd.read_excel(path, dtype=str, header=header, engine="xlrd", keep_default_na=False)
    raise DataError(f"{path.name}: 지원하지 않는 형식입니다(.xlsx, .xls, .csv만 가능).")


def read_file(path: str | Path) -> pd.DataFrame:
    """헤더 행이 맨 위가 아니어도(위에 제목·빈 줄) '운송장번호'가 있는 행을 헤더로 잡는다."""
    path = Path(path)
    try:
        df = _read_raw(path, 0)
        df.columns = [str(c).strip() for c in df.columns]
        if "운송장번호" not in df.columns:
            for i in range(min(15, len(df))):
                if "운송장번호" in [str(v).strip() for v in df.iloc[i].tolist()]:
                    df = _read_raw(path, i + 1)
                    df.columns = [str(c).strip() for c in df.columns]
                    break
    except DataError:
        raise
    except PermissionError:
        raise DataError(f"{path.name}: 파일이 다른 프로그램에서 열려 있습니다. 닫고 다시 시도하세요.")
    except Exception as e:  # 깨진 파일 등
        raise DataError(f"{path.name}: 파일을 읽을 수 없습니다 ({e}).")

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise DataError(f"{path.name}: 필수 열이 없습니다 → {', '.join(missing)}")
    for c in OPTIONAL_COLS:
        if c not in df.columns:
            df[c] = ""
    df = df[REQUIRED_COLS + OPTIONAL_COLS].fillna("").astype(str)
    df = df.apply(lambda s: s.str.strip())
    df = df[df["운송장번호"] != ""]
    df["원본파일"] = path.name
    return df


def load_files(paths) -> tuple[pd.DataFrame, int]:
    """여러 파일을 합치고 운송장번호 기준 중복 제거. (데이터, 제거된 중복 수)"""
    frames = [read_file(p) for p in paths]
    if not frames:
        raise DataError("불러올 파일이 없습니다.")
    df = pd.concat(frames, ignore_index=True)
    before = len(df)
    df = df.drop_duplicates(subset="운송장번호", keep="first").reset_index(drop=True)
    if df.empty:
        raise DataError("파일에 운송장 자료가 없습니다.")
    return df, before - len(df)


# ── 건별 레코드 ──────────────────────────────────────────────

def parse_amount(value: str) -> Decimal:
    v = str(value).replace(",", "").strip()
    if v in ("", "nan", "None", "-"):
        return Decimal(0)
    return Decimal(v)


def to_number(d: Decimal):
    """엑셀에 쓸 숫자: 정수면 int."""
    return int(d) if d == d.to_integral_value() else float(d)


@dataclass
class Shipment:
    waybill: str
    ship_date: str
    item: str
    pay_term: str
    kind: str
    name: str        # 정산 주체 이름(원본 그대로, 공백만 제거)
    phone: str       # 정산 주체 전화(마스킹 그대로)
    receiver: str
    status: str
    invoice: str
    fees: dict
    amount: Decimal


def _kind(pay_term: str) -> str:
    if pay_term == "발신":
        return KIND_SEND
    if pay_term == "착신":
        return KIND_RETURN
    return KIND_UNKNOWN


def norm_phone(p: str) -> str:
    return p.replace("-", "").replace(" ", "").strip()


def build_shipments(df: pd.DataFrame) -> list[Shipment]:
    bad = []
    out = []
    for r in df.to_dict("records"):
        fees = {}
        for c in AMOUNT_COLS:
            try:
                fees[c] = parse_amount(r[c])
            except InvalidOperation:
                bad.append(f"{r['운송장번호']}({c}={r[c]})")
        if bad and len(fees) < len(AMOUNT_COLS):
            continue
        kind = _kind(r["지불조건"])
        # 착신(반품)은 수하인이, 그 외에는 송하인이 정산 주체
        if kind == KIND_RETURN:
            name, phone = r["수하인명"], r["수하인전화번호"]
        else:
            name, phone = r["송하인명"], r["송하인전화번호"]
        out.append(Shipment(
            waybill=r["운송장번호"], ship_date=r["출고일"][:10], item=r["품목명"],
            pay_term=r["지불조건"], kind=kind, name=name.strip(), phone=norm_phone(phone),
            receiver=r["수하인명"], status=r["현재상태"], invoice=r["인보이스"],
            fees=fees, amount=sum(fees.values(), Decimal(0)),
        ))
    if bad:
        raise DataError("금액 칸이 숫자가 아닌 운송장이 있습니다 → " + ", ".join(bad[:20])
                        + (f" 외 {len(bad) - 20}건" if len(bad) > 20 else ""))
    return out


def raw_total(df: pd.DataFrame) -> Decimal:
    """검증용: 원본 표의 (운임+사합비+할증료+기타비용) 합계를 레코드와 무관하게 따로 계산."""
    total = Decimal(0)
    for c in AMOUNT_COLS:
        total += sum((parse_amount(v) for v in df[c]), Decimal(0))
    return total


def in_month(ship_date: str, year: int, month: int) -> bool:
    return ship_date[:7] == f"{year:04d}-{month:02d}"


# ── 동일인 묶기 ──────────────────────────────────────────────

def strip_symbols(name: str) -> str:
    """★ 같은 기호(유니코드 Symbol 분류)를 뺀 이름. 마스킹 '*'는 Po라서 남는다."""
    return "".join(ch for ch in name if not unicodedata.category(ch).startswith("S")).strip()


def resolve(name: str, aliases: dict[str, str]) -> str:
    seen = set()
    while name in aliases and name not in seen:
        seen.add(name)
        name = aliases[name]
    return name


@dataclass
class Group:
    name: str
    raw_names: set = field(default_factory=set)
    phones: Counter = field(default_factory=Counter)
    count: Counter = field(default_factory=Counter)      # 구분별 건수
    amount: dict = field(default_factory=lambda: defaultdict(Decimal))
    items: Counter = field(default_factory=Counter)
    shipments: list = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return sum(self.count.values())

    @property
    def total_amount(self) -> Decimal:
        return sum(self.amount.values(), Decimal(0))

    @property
    def main_phone(self) -> str:
        return self.phones.most_common(1)[0][0] if self.phones else ""

    def item_examples(self, n=3) -> list[str]:
        return [i for i, _ in self.items.most_common() if i and i != "."][:n]


@dataclass
class Candidate:
    base: str
    other: str
    reason: str      # "전화번호 일치" | "특수문자 제외 시 같은 이름"
    phone: str       # 공통 전화번호(특수문자 후보는 other의 번호)

    @property
    def key(self) -> frozenset:
        return frozenset((self.base, self.other))


def group_shipments(shipments, aliases) -> dict[str, Group]:
    groups: dict[str, Group] = {}
    for s in shipments:
        key = resolve(s.name, aliases)
        g = groups.setdefault(key, Group(key))
        g.raw_names.add(s.name)
        if s.phone:
            g.phones[s.phone] += 1
        g.count[s.kind] += 1
        g.amount[s.kind] += s.amount
        g.items[s.item] += 1
        g.shipments.append(s)
    return groups


def find_candidates(groups: dict[str, Group], different_pairs: set[frozenset]) -> list[Candidate]:
    def rank(n):  # 건수가 많은 쪽을 기준으로
        return (-groups[n].total_count, n)

    cands: dict[frozenset, Candidate] = {}
    by_phone = defaultdict(set)
    for g in groups.values():
        for p in g.phones:
            by_phone[p].add(g.name)
    for phone, names in sorted(by_phone.items()):
        if len(names) < 2:
            continue
        ordered = sorted(names, key=rank)
        base = ordered[0]
        for other in ordered[1:]:
            c = Candidate(base, other, "전화번호 일치", phone)
            if c.key not in different_pairs and c.key not in cands:
                cands[c.key] = c
    for g in groups.values():
        stripped = strip_symbols(g.name)
        if stripped != g.name and stripped in groups:
            c = Candidate(stripped, g.name, "특수문자 제외 시 같은 이름", g.main_phone)
            if c.key not in different_pairs and c.key not in cands:
                cands[c.key] = c
    return sorted(cands.values(), key=lambda c: (rank(c.base), rank(c.other)))


# ── 정산 결과 ────────────────────────────────────────────────

@dataclass
class SummaryRow:
    name: str
    room: str
    phone: str
    kind: str
    count: int
    amount: Decimal
    first_of_group: bool


@dataclass
class Settlement:
    groups: dict[str, Group]
    candidates: list[Candidate]
    source_total: Decimal
    shipments: list[Shipment]

    @property
    def total_count(self) -> int:
        return len(self.shipments)

    @property
    def total_amount(self) -> Decimal:
        return sum((s.amount for s in self.shipments), Decimal(0))

    def sorted_groups(self) -> list[Group]:
        return [self.groups[k] for k in sorted(self.groups)]

    def multi_phone_names(self) -> list[str]:
        return [g.name for g in self.sorted_groups() if len(g.phones) > 1]

    def unknown_terms(self) -> Counter:
        return Counter(s.pay_term for s in self.shipments if s.kind == KIND_UNKNOWN)

    def summary_rows(self, senders: dict[str, dict] | None = None) -> list[SummaryRow]:
        """송하인마다 발송 → 착신(반품) → 미분류 순. 두 번째 행부터 이름·호실·전화 비움."""
        senders = senders or {}
        rows = []
        for g in self.sorted_groups():
            info = senders.get(g.name, {})
            room = info.get("호실", "") or ""
            phone = info.get("전화번호", "") or g.main_phone
            first = True
            for kind in KIND_ORDER:
                if g.count[kind] == 0:
                    continue
                rows.append(SummaryRow(
                    g.name if first else "", room if first else "", phone if first else "",
                    kind, g.count[kind], g.amount[kind], first,
                ))
                first = False
        return rows

    def verify(self, rows: list[SummaryRow]) -> None:
        out_total = sum((r.amount for r in rows), Decimal(0))
        out_count = sum(r.count for r in rows)
        if out_total != self.source_total or out_count != self.total_count:
            raise DataError(
                f"검증 실패: 출력 합계 {out_total:,}원/{out_count}건 ≠ 원본 합계 "
                f"{self.source_total:,}원/{self.total_count}건. 저장하지 않았습니다."
            )


def settle(df: pd.DataFrame, aliases: dict[str, str] | None = None,
           different_pairs: set[frozenset] | None = None,
           month: tuple[int, int] | None = None, include_out_of_month: bool = True) -> Settlement:
    aliases = aliases or {}
    if month and not include_out_of_month:
        df = df[df["출고일"].str[:7] == f"{month[0]:04d}-{month[1]:02d}"]
    shipments = build_shipments(df)
    groups = group_shipments(shipments, aliases)
    pairs = {frozenset(resolve(n, aliases) for n in p) for p in (different_pairs or set())}
    return Settlement(groups, find_candidates(groups, pairs), raw_total(df), shipments)


def data_period(df: pd.DataFrame) -> tuple[str, str]:
    dates = sorted(d[:10] for d in df["출고일"] if d)
    return (dates[0], dates[-1]) if dates else ("", "")


def out_of_month_count(df: pd.DataFrame, year: int, month: int) -> int:
    return int((df["출고일"].str[:7] != f"{year:04d}-{month:02d}").sum())
