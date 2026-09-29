"""lawdata → 최종 DB 행 변환, 검토 항목 생성, 소액처 판정.

convert() 는 순수 함수다. 검토 결과(decisions)를 바꿔 다시 호출하면 전체가 다시 계산된다.
UI 는 decisions 만 들고 있으면 된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import matcher, notes
from .config import SETTLEMENT_FEE
from .final_db import FinalDB
from .lawdata import LawRow
from .master import Product, ProductMaster, Settings
from .rate_table import RateEntry, RateTable
from .utils import clean_str, code_key, suggest_final_name

# 검토 항목 코드
PRICE_MISMATCH = "PRICE_MISMATCH"
PRODUCT_CODE_CHANGED = "PRODUCT_CODE_CHANGED"
PRODUCT_RENAMED = "PRODUCT_RENAMED"
NEW_PRODUCT = "NEW_PRODUCT"
NOT_IN_RATE_TABLE = "NOT_IN_RATE_TABLE"
RATE_TABLE_DUP = "RATE_TABLE_DUP"
NOTE_RESTRICTION = "NOTE_RESTRICTION"
EXCLUDED_PRODUCT = "EXCLUDED_PRODUCT"
VALUE_CHANGED = "VALUE_CHANGED"
NO_THRESHOLD = "NO_THRESHOLD"
DUPLICATE_MONTH = "DUPLICATE_MONTH"

ISSUE_TITLES = {
    PRICE_MISMATCH: "단가 불일치",
    PRODUCT_CODE_CHANGED: "보험코드 변경 확인",
    PRODUCT_RENAMED: "제품명 변경 확인",
    NEW_PRODUCT: "신규 제품",
    NOT_IN_RATE_TABLE: "요율표에 없는 코드",
    RATE_TABLE_DUP: "요율표 중복 코드",
    NOTE_RESTRICTION: "정산 제한 조건",
    EXCLUDED_PRODUCT: "제외 표시된 제품",
    VALUE_CHANGED: "적용값 변경",
    NO_THRESHOLD: "최소 인정금액 미설정",
    DUPLICATE_MONTH: "같은 정산월 기존 행",
}


@dataclass
class Issue:
    """검토가 필요한 항목. key 로 decisions 와 짝을 맞춘다."""

    code: str                      # 검토 항목 코드
    key: str                       # decisions 키
    scope: str                     # 'row' | 'product' | 'company' | 'global'
    제품명: str = ""
    보험코드: str = ""
    message: str = ""
    detail: dict = field(default_factory=dict)
    rows: list[int] = field(default_factory=list)   # 영향 받는 행 (order 값)
    resolved: bool = False
    blocking: bool = True          # False 면 참고용

    @property
    def title(self) -> str:
        return ISSUE_TITLES.get(self.code, self.code)


@dataclass
class OutRow:
    """최종 DB 표에 들어갈 한 행."""

    order: int
    law: LawRow
    수탁업체명: str = ""
    처방월: Optional[str] = None
    정산월: Optional[str] = None
    사업자번호: str = ""
    병원명: str = ""
    제약사: str = ""
    구분: object = None
    제품명: str = ""
    단가: Optional[float] = None
    수량: Optional[float] = None
    수수료: Optional[float] = None
    구간인센: Optional[float] = None
    특별인센: Optional[float] = None
    소액처: bool = False
    제외: bool = False
    제외사유: str = ""
    참고: list[str] = field(default_factory=list)
    issue_keys: list[str] = field(default_factory=list)

    @property
    def 금액(self) -> float:
        if self.단가 is None or self.수량 is None:
            return 0.0
        return self.단가 * self.수량

    @property
    def 최종요율(self) -> float:
        return (self.수수료 or 0) + (self.구간인센 or 0) + (self.특별인센 or 0) - SETTLEMENT_FEE

    @property
    def 확정금액(self) -> float:
        if self.소액처:
            return 0.0
        return self.금액 * self.최종요율


@dataclass
class ConversionResult:
    rows: list[OutRow]              # 제외되지 않은 행 (출력 대상)
    excluded: list[OutRow]
    issues: list[Issue]
    small_groups: list[dict]
    settlement_month: str = ""

    @property
    def open_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.blocking and not i.resolved]

    @property
    def ready(self) -> bool:
        return not self.open_issues and bool(self.rows)

    @property
    def 금액합계(self) -> float:
        return sum(r.금액 for r in self.rows)

    @property
    def 확정금액합계(self) -> float:
        return sum(r.확정금액 for r in self.rows)

    def issue(self, key: str) -> Optional[Issue]:
        for item in self.issues:
            if item.key == key:
                return item
        return None

    def issues_of(self, code: str) -> list[Issue]:
        return [i for i in self.issues if i.code == code]


@dataclass
class ConvertContext:
    master: ProductMaster
    settings: Settings
    rate_table: RateTable
    final_db: Optional[FinalDB] = None


def convert(
    law_rows: list[LawRow],
    ctx: ConvertContext,
    settlement_month: str,
    decisions: Optional[dict] = None,
) -> ConversionResult:
    """lawdata 행들을 최종 DB 행으로 바꾸고, 검토가 필요한 항목을 모은다."""
    decisions = decisions or {}
    issues: dict[str, Issue] = {}
    out_rows: list[OutRow] = []

    def add_issue(issue: Issue) -> Issue:
        existing = issues.get(issue.key)
        if existing is None:
            issues[issue.key] = issue
            return issue
        existing.rows.extend(issue.rows)
        return existing

    replace_existing = False
    if ctx.final_db is not None:
        existing_rows = ctx.final_db.rows_for_month(settlement_month)
        if existing_rows:
            decision = decisions.get(DUPLICATE_MONTH) or {}
            action = decision.get("action")
            issue = Issue(
                code=DUPLICATE_MONTH,
                key=DUPLICATE_MONTH,
                scope="global",
                message=(
                    f"최종 엑셀에 이미 정산월 {settlement_month} 행이 "
                    f"{len(existing_rows)}개 있습니다."
                ),
                detail={"existing": len(existing_rows)},
                resolved=action in ("replace", "abort"),
            )
            issues[issue.key] = issue
            replace_existing = action == "replace"

    exclude_month = settlement_month if replace_existing else None

    for law in law_rows:
        row = OutRow(
            order=law.order,
            law=law,
            수탁업체명=ctx.settings.vendor_name,
            처방월=law.처방월,
            정산월=law.정산월,
            사업자번호=law.사업자등록번호,
            병원명=law.거래처,
            수량=law.수량,
        )

        # ---- 1) 제품 매칭
        result = matcher.match(ctx.master, law.보험코드, law.제품)
        product = result.product
        code = code_key(law.보험코드)

        if result.kind == matcher.MATCH_CODE_CHANGED:
            key = f"{code}|{PRODUCT_CODE_CHANGED}"
            decision = decisions.get(key) or {}
            add_issue(
                Issue(
                    code=PRODUCT_CODE_CHANGED,
                    key=key,
                    scope="product",
                    제품명=product.최종제품명,
                    보험코드=code,
                    message=(
                        f"'{law.제품}' 은 '{product.최종제품명}' 으로 알고 있는데 "
                        f"보험코드가 {code} 로 바뀌었습니다."
                    ),
                    detail={
                        "lawdata약제명": law.제품,
                        "기존코드": product.보험코드,
                        "새코드": code,
                        "추천제품": product.최종제품명,
                    },
                    rows=[law.order],
                    resolved=decision.get("action") in ("link", "exclude"),
                )
            )
            row.issue_keys.append(key)
            if decision.get("action") == "exclude":
                row.제외, row.제외사유 = True, "보험코드 변경 확인에서 제외"

        elif result.kind == matcher.MATCH_RENAMED:
            key = f"{code}|{PRODUCT_RENAMED}"
            decision = decisions.get(key) or {}
            add_issue(
                Issue(
                    code=PRODUCT_RENAMED,
                    key=key,
                    scope="product",
                    제품명=law.제품,
                    보험코드=code,
                    message=f"'{law.제품}' 과 비슷한 기존 제품이 있습니다.",
                    detail={
                        "lawdata약제명": law.제품,
                        "후보": [(p.최종제품명, p.보험코드, score) for p, score in result.candidates],
                    },
                    rows=[law.order],
                    resolved=decision.get("action") in ("link", "new", "exclude"),
                )
            )
            row.issue_keys.append(key)
            if decision.get("action") == "exclude":
                row.제외, row.제외사유 = True, "제품명 변경 확인에서 제외"
            elif decision.get("action") == "new":
                product = None

        elif result.kind == matcher.MATCH_NEW:
            key = f"{code}|{NEW_PRODUCT}"
            entry = ctx.rate_table.first(code)
            decision = decisions.get(key) or {}
            add_issue(
                Issue(
                    code=NEW_PRODUCT,
                    key=key,
                    scope="product",
                    제품명=law.제품,
                    보험코드=code,
                    message=f"처음 나온 제품입니다: '{law.제품}' ({code})",
                    detail={
                        "lawdata약제명": law.제품,
                        "요율표제품명": entry.제품명 if entry else "",
                        "추천제품명": suggest_final_name(entry.제품명) if entry else law.제품,
                        "요율표있음": entry is not None,
                    },
                    rows=[law.order],
                    resolved=decision.get("action") in ("register", "exclude"),
                )
            )
            row.issue_keys.append(key)
            if decision.get("action") == "exclude":
                row.제외, row.제외사유 = True, "신규 제품 검토에서 제외"
            product = None

        # ---- 2) 제품 마스터 값
        register = (decisions.get(f"{code}|{NEW_PRODUCT}") or {}).get("product") or {}
        if product is not None:
            row.제품명 = product.최종제품명
            row.구간인센 = product.구간인센
            row.특별인센 = product.특별인센
            if product.제외 and not row.제외:
                key = f"{code}|{EXCLUDED_PRODUCT}"
                decision = decisions.get(key) or {}
                add_issue(
                    Issue(
                        code=EXCLUDED_PRODUCT,
                        key=key,
                        scope="product",
                        제품명=product.최종제품명,
                        보험코드=code,
                        message=f"'{product.최종제품명}' 은 제외 표시된 제품입니다. ({product.메모})",
                        detail={"메모": product.메모},
                        rows=[law.order],
                        resolved=decision.get("include") is not None,
                    )
                )
                row.issue_keys.append(key)
                if decision.get("include") is not True:
                    row.제외, row.제외사유 = True, f"제외 표시 제품 ({product.메모})"
        else:
            row.제품명 = clean_str(register.get("최종제품명")) or law.제품
            row.구간인센 = register.get("구간인센")
            row.특별인센 = register.get("특별인센")

        # ---- 3) 요율표 값
        entries = ctx.rate_table.get(code)
        entry: Optional[RateEntry] = None
        if len(entries) > 1:
            key = f"{code}|{RATE_TABLE_DUP}"
            decision = decisions.get(key) or {}
            chosen = decision.get("row")
            add_issue(
                Issue(
                    code=RATE_TABLE_DUP,
                    key=key,
                    scope="product",
                    제품명=row.제품명,
                    보험코드=code,
                    message=f"요율표에 보험코드 {code} 가 {len(entries)}행 있습니다. 쓸 행을 고르세요.",
                    detail={
                        "행": [
                            {
                                "row": e.row,
                                "제품명": e.제품명,
                                "제약사명": e.제약사명,
                                "구분": e.구분,
                                "약가": e.약가,
                                "요율": e.요율,
                                "비고": e.비고,
                            }
                            for e in entries
                        ]
                    },
                    rows=[law.order],
                    resolved=chosen is not None,
                )
            )
            row.issue_keys.append(key)
            entry = next((e for e in entries if e.row == chosen), None) or entries[0]
        elif entries:
            entry = entries[0]

        manual = (decisions.get(f"{code}|{NOT_IN_RATE_TABLE}") or {}).get("values") or {}
        if entry is None:
            key = f"{code}|{NOT_IN_RATE_TABLE}"
            decision = decisions.get(key) or {}
            add_issue(
                Issue(
                    code=NOT_IN_RATE_TABLE,
                    key=key,
                    scope="product",
                    제품명=row.제품명,
                    보험코드=code,
                    message=f"현재 요율표에 보험코드 {code} 가 없습니다. 값을 직접 넣거나 제외하세요.",
                    detail={"lawdata단가": law.단가, "lawdata제조사": law.제조사},
                    rows=[law.order],
                    resolved=decision.get("action") in ("manual", "exclude"),
                )
            )
            row.issue_keys.append(key)
            if decision.get("action") == "exclude":
                row.제외, row.제외사유 = True, "요율표에 없는 코드"
            row.제약사 = ctx.settings.company_display(manual.get("제약사명") or law.제조사)
            row.구분 = manual.get("구분")
            row.수수료 = manual.get("요율")
            rate_price = manual.get("약가")
            note_rules = notes.NoteRules()
        else:
            row.제약사 = ctx.settings.company_display(entry.제약사명)
            row.구분 = entry.구분
            row.수수료 = entry.요율
            rate_price = entry.약가
            note_rules = notes.parse_note(entry.비고)
            if entry.비고:
                row.참고.append(f"요율표 비고: {entry.비고}")
            for promo in ctx.rate_table.promotion(code):
                row.참고.append(f"프로모션: {promo}")
            if not row.제품명:
                row.제품명 = suggest_final_name(entry.제품명)

        # ---- 4) 단가 결정
        law_price = law.단가
        if rate_price is not None and law_price is not None and rate_price != law_price:
            key = f"{code}|{PRICE_MISMATCH}|{law_price:g}"
            decision = decisions.get(key) or {}
            choice = decision.get("choice")
            add_issue(
                Issue(
                    code=PRICE_MISMATCH,
                    key=key,
                    scope="product",
                    제품명=row.제품명,
                    보험코드=code,
                    message=(
                        f"'{row.제품명}' 단가가 다릅니다. "
                        f"lawdata {law_price:,g} / 요율표 {rate_price:,g}"
                    ),
                    detail={"lawdata단가": law_price, "요율표약가": rate_price},
                    rows=[law.order],
                    resolved=choice in ("rate", "lawdata", "custom"),
                )
            )
            row.issue_keys.append(key)
            if choice == "rate":
                row.단가 = rate_price
            elif choice == "lawdata":
                row.단가 = law_price
            elif choice == "custom":
                row.단가 = decision.get("value")
            else:
                row.단가 = None          # 미리 정해두지 않는다
        else:
            row.단가 = rate_price if rate_price is not None else law_price

        # ---- 5) 비고 제한 조건
        if note_rules.has_rule and not row.제외:
            is_new_client = False
            if note_rules.new_ban_from and ctx.final_db is not None:
                is_new_client = ctx.final_db.is_new_client(
                    row.병원명,
                    row.제품명,
                    note_rules.new_ban_from,
                    exclude_month=exclude_month,
                )
            elif note_rules.new_ban_from:
                is_new_client = True
            hits = notes.check_restrictions(note_rules, law.처방월, is_new_client=is_new_client)
            if hits:
                key = f"{law.order}|{NOTE_RESTRICTION}"
                decision = decisions.get(key) or {}
                add_issue(
                    Issue(
                        code=NOTE_RESTRICTION,
                        key=key,
                        scope="row",
                        제품명=row.제품명,
                        보험코드=code,
                        message=f"{row.병원명} / {row.제품명}: " + " ".join(h.message for h in hits),
                        detail={
                            "병원명": row.병원명,
                            "처방월": law.처방월,
                            "비고": note_rules.raw,
                            "종류": [h.kind for h in hits],
                        },
                        rows=[law.order],
                        resolved=decision.get("include") is not None,
                    )
                )
                row.issue_keys.append(key)
                if decision.get("include") is not True:
                    row.제외, row.제외사유 = True, "정산 제한 조건"

        if note_rules.info:
            row.참고.extend(note_rules.info)

        out_rows.append(row)

    # ---- 6) 적용값 변경 확인 (최종 DB 의 마지막 적용값과 비교)
    if ctx.final_db is not None:
        checked: set[str] = set()
        for row in out_rows:
            if row.제외 or not row.제품명 or row.제품명 in checked:
                continue
            checked.add(row.제품명)
            previous = ctx.final_db.last_applied(row.제품명, exclude_month=exclude_month)
            if previous is None:
                continue
            for label, before, after in (
                ("단가", previous.단가, row.단가),
                ("수수료", previous.수수료, row.수수료),
                ("구간인센", previous.구간인센, row.구간인센),
                ("특별인센", previous.특별인센, row.특별인센),
            ):
                if after is None or before is None:
                    continue
                if round(float(before), 6) == round(float(after), 6):
                    continue
                key = f"{row.제품명}|{VALUE_CHANGED}|{label}"
                decision = decisions.get(key) or {}
                issues.setdefault(
                    key,
                    Issue(
                        code=VALUE_CHANGED,
                        key=key,
                        scope="product",
                        제품명=row.제품명,
                        보험코드=row.law.보험코드,
                        message=(
                            f"'{row.제품명}' {label} 이 지난 정산({previous.정산월})의 "
                            f"{before:,g} 에서 {after:,g} 로 바뀝니다."
                        ),
                        detail={
                            "항목": label,
                            "이전값": before,
                            "새값": after,
                            "이전정산월": previous.정산월,
                        },
                        rows=[row.order],
                        resolved=decision.get("confirmed") is True,
                    ),
                )

    # ---- 7) 소액처 판정 (검토를 모두 반영한 뒤)
    kept = [r for r in out_rows if not r.제외]
    excluded = [r for r in out_rows if r.제외]
    small_groups = _apply_small_accounts(kept, ctx, issues, decisions)

    return ConversionResult(
        rows=kept,
        excluded=excluded,
        issues=list(issues.values()),
        small_groups=small_groups,
        settlement_month=settlement_month,
    )


def _apply_small_accounts(
    rows: list[OutRow],
    ctx: ConvertContext,
    issues: dict[str, Issue],
    decisions: dict,
) -> list[dict]:
    """(병원명 × 제약사) 그룹 합계가 최소 인정금액보다 작으면 그룹 전체를 소액처로."""
    groups: dict[tuple[str, str], list[OutRow]] = {}
    for row in rows:
        groups.setdefault((row.병원명, row.제약사), []).append(row)

    # 최종 표기 → 요율표 원본명 (최소 인정금액은 원본명으로 등록되어 있다)
    reverse_alias = {v: k for k, v in ctx.settings.company_aliases.items()}

    summary: list[dict] = []
    for (hospital, company), members in groups.items():
        lookup = reverse_alias.get(company, company)
        threshold = ctx.settings.threshold(lookup)
        total = sum(r.금액 for r in members)

        if not threshold["known"]:
            key = f"{company}|{NO_THRESHOLD}"
            decision = decisions.get(key) or {}
            value = decision.get("value")
            issue = issues.get(key)
            if issue is None:
                issue = Issue(
                    code=NO_THRESHOLD,
                    key=key,
                    scope="company",
                    제품명="",
                    message=f"제약사 '{company}' 의 최소 인정금액을 모릅니다.",
                    detail={"제약사": company, "요율표명": lookup},
                    resolved="value" in decision,
                )
                issues[key] = issue
            issue.rows.extend(r.order for r in members)
            if "value" in decision:
                threshold = {"value": value, "known": True, "needs_input": False, "raw": ""}
            else:
                continue
        elif threshold.get("needs_input"):
            key = f"{company}|{NO_THRESHOLD}"
            decision = decisions.get(key) or {}
            issue = issues.get(key)
            if issue is None:
                issue = Issue(
                    code=NO_THRESHOLD,
                    key=key,
                    scope="company",
                    message=(
                        f"제약사 '{company}' 의 최소 인정금액 '{threshold.get('raw')}' 을 "
                        f"숫자로 확인해 주세요."
                    ),
                    detail={"제약사": company, "요율표명": lookup, "원문": threshold.get("raw")},
                    resolved="value" in decision,
                )
                issues[key] = issue
            issue.rows.extend(r.order for r in members)
            if "value" in decision:
                threshold = {"value": decision.get("value"), "known": True, "needs_input": False}
            else:
                continue

        limit = threshold.get("value")
        if limit is None:
            continue  # '없음' → 판정하지 않는다
        if total < limit:
            for member in members:
                member.소액처 = True
            summary.append(
                {
                    "병원명": hospital,
                    "제약사": company,
                    "금액": total,
                    "기준": limit,
                    "행수": len(members),
                }
            )
    summary.sort(key=lambda g: (g["병원명"], g["제약사"]))
    return summary
