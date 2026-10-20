"""제품 마스터, 제약사 설정, 초기화.

마스터는 사람이 엑셀로 열어볼 수 있게 data/product_master.xlsx 로 보관한다.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import openpyxl

from . import changelog
from .config import (
    BACKUP_DIR,
    PRODUCT_MASTER_PATH,
    SETTINGS_PATH,
    VENDOR_NAME,
    ensure_dirs,
)
from .rate_table import RateTable
from .utils import clean_str, code_key, normalize_name, parse_month, parse_threshold, to_number

MASTER_COLUMNS = [
    "보험코드",
    "최종제품명",
    "lawdata약제명별칭",
    "이전보험코드",
    "구간인센%",
    "특별인센%",
    "제외여부",
    "메모",
]

LIST_SEP = " | "

# 보험코드를 아직 모르는 제품에 임시로 붙이는 키. 화면에는 'none' 으로 보여준다.
NO_CODE_PREFIX = "?"
NO_CODE_TEXT = "none"

# 요율표 제약사명 → 최종파일 표기
DEFAULT_COMPANY_ALIASES = {"유니메드제약": "유니메드"}

# 금액인정 시트에 없는 제약사의 최소 인정금액 (PRD 3.3)
DEFAULT_THRESHOLDS = {"안국뉴팜": 100_000}


# ---------------------------------------------------------------- 제품 마스터

@dataclass
class Product:
    보험코드: str
    최종제품명: str = ""
    별칭: list[str] = field(default_factory=list)
    이전보험코드: list[str] = field(default_factory=list)
    구간인센: Optional[float] = None
    특별인센: Optional[float] = None
    제외: bool = False
    메모: str = ""

    @property
    def codes(self) -> list[str]:
        return [c for c in [self.보험코드, *self.이전보험코드] if c]

    @property
    def code_unknown(self) -> bool:
        """보험코드를 아직 찾지 못한 행(초기화 때 생길 수 있다)."""
        return self.보험코드.startswith(NO_CODE_PREFIX)

    @property
    def code_display(self) -> str:
        """화면에 보여줄 보험코드. 모르면 'none'."""
        return NO_CODE_TEXT if self.code_unknown else self.보험코드

    def alias_keys(self) -> set[str]:
        keys = {normalize_name(a) for a in self.별칭 if a}
        if self.최종제품명:
            keys.add(normalize_name(self.최종제품명))
        return {k for k in keys if k}


class ProductMaster:
    def __init__(self, products: Optional[list[Product]] = None):
        self.products: list[Product] = products or []
        self._reindex()

    # ---- 색인

    def _reindex(self) -> None:
        self._by_code: dict[str, Product] = {}
        self._by_alias: dict[str, Product] = {}
        for product in self.products:
            for code in product.codes:
                self._by_code.setdefault(code, product)
            for key in product.alias_keys():
                self._by_alias.setdefault(key, product)

    def by_code(self, code) -> Optional[Product]:
        return self._by_code.get(code_key(code))

    def by_alias(self, name) -> Optional[Product]:
        return self._by_alias.get(normalize_name(name))

    def all_codes(self) -> list[str]:
        return [c for p in self.products for c in p.codes if not c.startswith(NO_CODE_PREFIX)]

    def similar(self, name, limit: int = 3) -> list[tuple[Product, float]]:
        """이름이 비슷한 제품 후보를 찾는다(difflib)."""
        import difflib

        target = normalize_name(name)
        if not target:
            return []
        scored: list[tuple[Product, float]] = []
        for product in self.products:
            best = 0.0
            for key in product.alias_keys():
                best = max(best, difflib.SequenceMatcher(None, target, key).ratio())
            if best >= 0.75:
                scored.append((product, round(best, 3)))
        scored.sort(key=lambda x: -x[1])
        return scored[:limit]

    # ---- 편집

    def upsert(self, product: Product) -> None:
        existing = self.by_code(product.보험코드)
        if existing is not None and existing.보험코드 == product.보험코드:
            self.products[self.products.index(existing)] = product
        else:
            self.products.append(product)
        self._reindex()

    def remove(self, code: str) -> None:
        self.products = [p for p in self.products if p.보험코드 != code_key(code)]
        self._reindex()

    def link_code(self, product: Product, new_code: str, new_alias: str = "") -> None:
        """새 보험코드/약제명을 이 제품에 연결한다. 다음 달부터 자동 매칭된다."""
        new_code = code_key(new_code)
        if product.code_unknown and new_code:
            product.이전보험코드 = [c for c in product.이전보험코드 if c != new_code]
            product.보험코드 = new_code
        elif new_code and new_code not in product.codes:
            # 새 코드를 대표로 올리고 옛 코드는 이전 코드로 남긴다.
            old = product.보험코드
            product.보험코드 = new_code
            if old and old not in product.이전보험코드:
                product.이전보험코드.append(old)
        alias = clean_str(new_alias)
        if alias and alias not in product.별칭:
            product.별칭.append(alias)
        self._reindex()

    # ---- 파일

    @classmethod
    def load(cls, path: str | Path = PRODUCT_MASTER_PATH) -> "ProductMaster":
        path = Path(path)
        if not path.exists():
            return cls([])
        wb = openpyxl.load_workbook(path, data_only=True)
        try:
            ws = wb.active
            rows = ws.iter_rows(min_row=1, values_only=True)
            header = [clean_str(h) for h in (next(rows, ()) or ())]
            index = {name: i for i, name in enumerate(header) if name}
            products: list[Product] = []
            for row in rows:
                def get(name):
                    i = index.get(name)
                    return row[i] if i is not None and i < len(row) else None

                code = code_key(get("보험코드"))
                if not code:
                    continue
                products.append(
                    Product(
                        보험코드=code,
                        최종제품명=clean_str(get("최종제품명")),
                        별칭=_split_list(get("lawdata약제명별칭")),
                        이전보험코드=[code_key(c) for c in _split_list(get("이전보험코드"))],
                        구간인센=to_number(get("구간인센%")),
                        특별인센=to_number(get("특별인센%")),
                        제외=clean_str(get("제외여부")).upper() in ("Y", "TRUE", "1", "제외"),
                        메모=clean_str(get("메모")),
                    )
                )
            return cls(products)
        finally:
            wb.close()

    def save(self, path: str | Path = PRODUCT_MASTER_PATH) -> None:
        path = Path(path)
        backup(path)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "제품마스터"
        ws.append(MASTER_COLUMNS)
        for cell in ws[1]:
            cell.font = openpyxl.styles.Font(bold=True)
        for product in sorted(self.products, key=lambda p: (p.최종제품명, p.보험코드)):
            ws.append(
                [
                    product.보험코드,
                    product.최종제품명,
                    LIST_SEP.join(product.별칭),
                    LIST_SEP.join(product.이전보험코드),
                    product.구간인센,
                    product.특별인센,
                    "Y" if product.제외 else "",
                    product.메모,
                ]
            )
        widths = [14, 34, 60, 22, 11, 11, 9, 30]
        for i, width in enumerate(widths, start=1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width
        for row in ws.iter_rows(min_row=2, min_col=1, max_col=1):
            for cell in row:
                cell.number_format = "@"
        for row in ws.iter_rows(min_row=2, min_col=5, max_col=6):
            for cell in row:
                cell.number_format = "0.00%"
        ws.freeze_panes = "A2"
        ensure_dirs()
        wb.save(path)


def _split_list(value) -> list[str]:
    text = clean_str(value)
    if not text:
        return []
    parts = [p.strip() for p in text.replace("\n", LIST_SEP).split("|")]
    return [p for p in parts if p]


def backup(path: str | Path) -> Optional[Path]:
    """저장 전 이전 파일을 data/backup/ 에 남긴다."""
    path = Path(path)
    if not path.exists():
        return None
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, target)
    return target


# ---------------------------------------------------------------- 설정

class Settings:
    def __init__(self, raw: Optional[dict] = None):
        raw = raw or {}
        self.vendor_name: str = raw.get("vendor_name") or VENDOR_NAME
        self.company_aliases: dict[str, str] = dict(
            raw.get("company_aliases") or DEFAULT_COMPANY_ALIASES
        )
        self.thresholds: dict[str, dict] = dict(raw.get("thresholds") or {})
        self.last_paths: dict[str, str] = dict(raw.get("last_paths") or {})
        self.initialized: bool = bool(raw.get("initialized"))

    # ---- 제약사명

    def company_display(self, rate_company: str) -> str:
        name = clean_str(rate_company)
        return self.company_aliases.get(name, name)

    # ---- 최소 인정금액

    def threshold(self, rate_company: str) -> dict:
        """{'value': int|None, 'raw': str, 'needs_input': bool, 'known': bool}"""
        name = clean_str(rate_company)
        for key in (name, self.company_display(name)):
            if key in self.thresholds:
                entry = dict(self.thresholds[key])
                entry["known"] = True
                return entry
        return {"value": None, "raw": "", "needs_input": True, "known": False}

    def set_threshold(self, company: str, value: Optional[int], raw: str = "") -> None:
        self.thresholds[clean_str(company)] = {
            "value": value,
            "raw": raw or ("없음" if value is None else f"{value:,}원"),
            "needs_input": False,
        }

    # ---- 파일

    @classmethod
    def load(cls, path: str | Path = SETTINGS_PATH) -> "Settings":
        path = Path(path)
        if not path.exists():
            return cls()
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def to_dict(self) -> dict:
        return {
            "vendor_name": self.vendor_name,
            "company_aliases": self.company_aliases,
            "thresholds": self.thresholds,
            "last_paths": self.last_paths,
            "initialized": self.initialized,
        }

    def save(self, path: str | Path = SETTINGS_PATH) -> None:
        path = Path(path)
        backup(path)
        ensure_dirs()
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ---------------------------------------------------------------- 초기화

@dataclass
class InitDiff:
    """초기화 대조 리포트 한 줄: 변환자료 값 vs 요율표 값."""

    보험코드: str
    제품명: str
    항목: str
    변환엑셀값: object
    요율표값: object


@dataclass
class InitResult:
    master: ProductMaster
    settings: Settings
    diffs: list[InitDiff]
    unmatched: list[str]         # 끝까지 보험코드를 못 찾은 제품 (최종 제품명)
    pair_count: int
    recovered: list[tuple] = field(default_factory=list)
    # 이름이 정확히 같아 자동으로 채운 것: (제품명, 보험코드, 요율표 제품명, 유사도)
    suggestions: list[tuple] = field(default_factory=list)
    # 비슷하지만 확실하지 않아 사람이 확인해야 하는 것: (제품명, 후보코드, 요율표 제품명, 유사도)


def build_rate_name_index(rate_table: RateTable) -> dict[str, list]:
    """요율표 제품명(정규화) → 요율표 행. 보험코드를 거꾸로 찾을 때 쓴다."""
    index: dict[str, list] = {}
    for entries in rate_table.entries.values():
        for entry in entries:
            key = normalize_name(entry.제품명)
            if key:
                index.setdefault(key, []).append(entry)
    return index


def find_code_by_name(
    name: str,
    rate_table: RateTable,
    name_index: Optional[dict[str, list]] = None,
    *,
    cutoff: float = 0.86,
) -> tuple[Optional[str], Optional[str], float]:
    """제품명으로 요율표에서 보험코드를 찾는다.

    변환엑셀에만 있고 lawdata 에 없던 제품은 보험코드를 모른다. 요율표를 거꾸로
    뒤져서 이름이 같거나 아주 비슷하면 코드를 되찾는다.

    돌려주는 값: (보험코드, 요율표 제품명, 유사도). 못 찾으면 (None, None, 0.0)
    """
    import difflib

    index = name_index if name_index is not None else build_rate_name_index(rate_table)
    key = normalize_name(name)
    if not key:
        return None, None, 0.0

    exact = index.get(key)
    if exact and len(exact) == 1:
        return exact[0].보험코드, exact[0].제품명, 1.0
    if exact:
        return None, None, 0.0  # 같은 이름이 여러 개면 사람이 골라야 한다

    best_key = difflib.get_close_matches(key, list(index), n=1, cutoff=cutoff)
    if not best_key:
        return None, None, 0.0
    candidates = index[best_key[0]]
    if len(candidates) != 1:
        return None, None, 0.0
    score = difflib.SequenceMatcher(None, key, best_key[0]).ratio()
    # 1.0 이 아니면 추천일 뿐이다. 용량만 다른 제품(75mg vs 37.5mg)이 여기 걸리므로
    # 부르는 쪽에서 반드시 사람에게 확인받아야 한다.
    return candidates[0].보험코드, candidates[0].제품명, round(score, 3)


def read_conversion_rows(path: str | Path) -> list[dict]:
    """변환엑셀 '변환자료' 시트를 읽는다(헤더 3행)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        ws = wb["변환자료"]
        rows = ws.iter_rows(min_row=3, values_only=True)
        header = [clean_str(h) for h in (next(rows, ()) or ())]
        index = {name: i for i, name in enumerate(header) if name}
        result = []
        for row in rows:
            def get(name):
                i = index.get(name)
                return row[i] if i is not None and i < len(row) else None

            약제명 = clean_str(get("약제명"))
            변경명 = clean_str(get("변경명"))
            if not 약제명 or not 변경명:
                continue
            result.append(
                {
                    "약제명": 약제명,
                    "변경명": 변경명,
                    "제약회사": clean_str(get("제약회사")),
                    "구분": get("구분"),
                    "단가": to_number(get("단가")),
                    "수수료": to_number(get("제약사\n수수료%")),
                    "구간인센": to_number(get("제약사\n구간인센%")),
                    "특별인센": to_number(get("제약사\n특별인센%")),
                    "특이사항": clean_str(get("특이사항")),
                }
            )
        return result
    finally:
        wb.close()


def read_threshold_rows(path: str | Path) -> list[dict]:
    """변환엑셀 '금액인정' 시트를 읽는다(헤더 2행)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        ws = wb["금액인정"]
        rows = ws.iter_rows(min_row=2, values_only=True)
        header = [clean_str(h) for h in (next(rows, ()) or ())]
        index = {name: i for i, name in enumerate(header) if name}
        result = []
        for row in rows:
            def get(name):
                i = index.get(name)
                return row[i] if i is not None and i < len(row) else None

            name = clean_str(get("제약사명"))
            if not name:
                continue
            result.append({"제약사명": name, "최소 인정금액": clean_str(get("최소 인정금액"))})
        return result
    finally:
        wb.close()


def initialize(
    *,
    conversion_path: str | Path,
    lawdata_path: str | Path,
    rate_table: RateTable,
) -> InitResult:
    """변환엑셀 + lawdata + 요율표로 제품 마스터와 설정을 만든다.

    1. lawdata 전체 시트에서 제품 ↔ 보험코드 쌍을 모은다.
    2. 변환자료 약제명으로 연결해 변경명 → 최종 제품명, 구간인센, 특별인센을 가져온다.
    3. 코드를 못 찾은 변환자료 행은 '코드 미확인'으로 넣어둔다.
    4. 변환자료 값과 요율표 값이 다른 항목을 대조 리포트로 만든다.
    """
    from . import lawdata as lawdata_mod

    pairs = lawdata_mod.product_code_pairs(lawdata_path)
    # 정규화한 약제명 → 보험코드
    name_to_code: dict[str, str] = {}
    for code, names in pairs.items():
        for name in names:
            name_to_code.setdefault(normalize_name(name), code)

    conversion = read_conversion_rows(conversion_path)

    # 변경명(최종 제품명) 단위로 묶는다.
    grouped: dict[str, dict] = {}
    for row in conversion:
        bucket = grouped.setdefault(
            row["변경명"],
            {"별칭": [], "rows": [], "code": None},
        )
        if row["약제명"] not in bucket["별칭"]:
            bucket["별칭"].append(row["약제명"])
        bucket["rows"].append(row)
        if bucket["code"] is None:
            bucket["code"] = name_to_code.get(normalize_name(row["약제명"]))

    products: list[Product] = []
    diffs: list[InitDiff] = []
    unmatched: list[str] = []
    recovered: list[tuple] = []
    suggestions: list[tuple] = []
    unknown_seq = 1

    # 변환엑셀에만 있어 보험코드를 모르는 제품은 요율표를 거꾸로 뒤져 코드를 되찾는다.
    name_index = build_rate_name_index(rate_table)
    taken = {c for c in (b["code"] for b in grouped.values()) if c}

    for final_name, bucket in grouped.items():
        first = bucket["rows"][0]
        code = bucket["code"]
        if code is None:
            found, rate_name, score = find_code_by_name(
                final_name, rate_table, name_index
            )
            if found is None:
                # 변환자료의 원래 약제명으로도 한 번 더 찾아본다.
                for alias in bucket["별칭"]:
                    found, rate_name, score = find_code_by_name(
                        alias, rate_table, name_index
                    )
                    if found is not None:
                        break
            if found is not None and found not in taken:
                if score >= 1.0:
                    # 이름이 정확히 같을 때만 자동으로 채운다.
                    code = found
                    taken.add(code)
                    recovered.append((final_name, code, rate_name, score))
                else:
                    # 비슷하기만 한 것은 사람이 확인해야 한다 (용량이 다를 수 있다).
                    suggestions.append((final_name, found, rate_name, score))
        if code is None:
            code = f"{NO_CODE_PREFIX}{unknown_seq:03d}"
            unknown_seq += 1
            unmatched.append(final_name)
        excluded = "정산불가" in (first["특이사항"] or "") or first["수수료"] is None
        products.append(
            Product(
                보험코드=code,
                최종제품명=final_name,
                별칭=bucket["별칭"],
                이전보험코드=[],
                구간인센=first["구간인센"],
                특별인센=first["특별인센"],
                제외=excluded,
                메모=first["특이사항"],
            )
        )
        # 대조 리포트: 요율표 값과 다른 항목
        entry = rate_table.first(code) if not code.startswith(NO_CODE_PREFIX) else None
        if entry is not None:
            if first["단가"] is not None and entry.약가 is not None and first["단가"] != entry.약가:
                diffs.append(InitDiff(code, final_name, "단가", first["단가"], entry.약가))
            if (
                first["수수료"] is not None
                and entry.요율 is not None
                and round(first["수수료"], 6) != round(entry.요율, 6)
            ):
                diffs.append(InitDiff(code, final_name, "수수료", first["수수료"], entry.요율))

    # lawdata 에만 있는 코드도 마스터에 넣어둔다(최종 제품명은 요율표 추천값).
    # 단, 이름이 기존 제품의 별칭과 같은 코드(코드만 바뀐 제품)는 넣지 않는다.
    # 정산할 때 PRODUCT_CODE_CHANGED 로 사용자에게 연결을 확인받는다.
    known = {c for p in products for c in p.codes}
    alias_index = ProductMaster(products)
    from .utils import suggest_final_name

    for code, names in sorted(pairs.items()):
        if code in known:
            continue
        if any(alias_index.by_alias(n) is not None for n in names):
            continue
        entry = rate_table.first(code)
        products.append(
            Product(
                보험코드=code,
                최종제품명=suggest_final_name(entry.제품명) if entry else sorted(names)[0],
                별칭=sorted(names),
                구간인센=None,
                특별인센=None,
                메모="lawdata 에서 자동 추가 (변환엑셀에 없음)",
            )
        )

    master = ProductMaster(products)

    settings = Settings.load()
    for row in read_threshold_rows(conversion_path):
        name = row["제약사명"]
        value, needs_input = parse_threshold(row["최소 인정금액"])
        prior = settings.thresholds.get(name)
        if prior is not None and prior.get("value") != value:
            # 같은 제약사가 서로 다른 값으로 두 번 나오면 사용자가 정해야 한다.
            needs_input = True
        settings.thresholds[name] = {
            "value": value,
            "raw": row["최소 인정금액"],
            "needs_input": needs_input,
        }
    for name, value in DEFAULT_THRESHOLDS.items():
        if name not in settings.thresholds:
            settings.set_threshold(name, value, raw=f"{value:,}원 (기본 설정)")
    for key, value in DEFAULT_COMPANY_ALIASES.items():
        settings.company_aliases.setdefault(key, value)

    return InitResult(
        master=master,
        settings=settings,
        diffs=diffs,
        unmatched=unmatched,
        pair_count=len(pairs),
        recovered=recovered,
        suggestions=suggestions,
    )


def commit_initialize(result: InitResult) -> None:
    result.master.save()
    result.settings.initialized = True
    result.settings.save()
    changelog.log(
        "초기화",
        "제품 마스터 초기화",
        새값=f"제품 {len(result.master.products)}개 / 코드쌍 {result.pair_count}개",
        사유=f"대조 차이 {len(result.diffs)}건, 코드 미확인 {len(result.unmatched)}건",
    )
