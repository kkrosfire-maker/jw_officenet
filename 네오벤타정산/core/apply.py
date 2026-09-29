"""검토에서 고른 내용을 제품 마스터와 설정에 반영하고 이력을 남긴다."""
from __future__ import annotations

from typing import Optional

from . import changelog, converter as conv
from .converter import ConversionResult, ConvertContext
from .master import Product
from .utils import code_key, to_number


def apply_decisions(
    ctx: ConvertContext,
    result: ConversionResult,
    decisions: dict,
    *,
    settlement_month: str = "",
) -> list[str]:
    """정산 생성 직전에 호출한다. 바뀐 내용 설명을 돌려준다."""
    notes: list[str] = []
    master_changed = False
    settings_changed = False
    entries: list[changelog.LogEntry] = []

    for issue in result.issues:
        decision = decisions.get(issue.key) or {}
        edi_month = _edi_month(result, issue)

        if issue.code == conv.PRODUCT_CODE_CHANGED and decision.get("action") == "link":
            product = ctx.master.by_alias(issue.detail["lawdata약제명"])
            if product is not None:
                before = product.보험코드
                ctx.master.link_code(product, issue.detail["새코드"], issue.detail["lawdata약제명"])
                master_changed = True
                notes.append(f"{product.최종제품명}: 보험코드 {before} → {product.보험코드}")
                entries.append(
                    changelog.LogEntry(
                        구분="검토선택",
                        항목="보험코드 연결",
                        보험코드=product.보험코드,
                        제품명=product.최종제품명,
                        이전값=before,
                        새값=product.보험코드,
                        사유=decision.get("reason", ""),
                        적용EDI월=edi_month,
                    )
                )

        elif issue.code == conv.PRODUCT_RENAMED and decision.get("action") == "link":
            target_code = decision.get("target")
            product = ctx.master.by_code(target_code) if target_code else None
            if product is not None:
                ctx.master.link_code(product, issue.보험코드, issue.detail["lawdata약제명"])
                master_changed = True
                notes.append(
                    f"{product.최종제품명}: 별칭 '{issue.detail['lawdata약제명']}' 추가"
                )
                entries.append(
                    changelog.LogEntry(
                        구분="검토선택",
                        항목="제품명 연결",
                        보험코드=product.보험코드,
                        제품명=product.최종제품명,
                        새값=issue.detail["lawdata약제명"],
                        사유=decision.get("reason", ""),
                        적용EDI월=edi_month,
                    )
                )

        elif issue.code == conv.NEW_PRODUCT and decision.get("action") == "register":
            values = decision.get("product") or {}
            product = Product(
                보험코드=code_key(issue.보험코드),
                최종제품명=values.get("최종제품명") or issue.detail.get("추천제품명", ""),
                별칭=[issue.detail["lawdata약제명"]],
                구간인센=to_number(values.get("구간인센")),
                특별인센=to_number(values.get("특별인센")),
                메모=values.get("메모", ""),
            )
            ctx.master.upsert(product)
            master_changed = True
            notes.append(f"신규 제품 등록: {product.최종제품명} ({product.보험코드})")
            entries.append(
                changelog.LogEntry(
                    구분="검토선택",
                    항목="신규 제품 등록",
                    보험코드=product.보험코드,
                    제품명=product.최종제품명,
                    새값=f"구간 {product.구간인센} / 특별 {product.특별인센}",
                    사유=decision.get("reason", ""),
                    적용EDI월=edi_month,
                )
            )

        elif issue.code == conv.NO_THRESHOLD and "value" in decision:
            company = issue.detail.get("요율표명") or issue.detail.get("제약사", "")
            ctx.settings.set_threshold(company, decision.get("value"))
            settings_changed = True
            notes.append(f"{company} 최소 인정금액 저장: {decision.get('value')}")
            entries.append(
                changelog.LogEntry(
                    구분="설정변경",
                    항목="최소 인정금액",
                    제품명=company,
                    이전값=issue.detail.get("원문", ""),
                    새값=str(decision.get("value")),
                    사유=decision.get("reason", ""),
                    적용EDI월=edi_month,
                )
            )

        elif issue.code == conv.PRICE_MISMATCH and decision.get("choice"):
            chosen = {
                "rate": issue.detail["요율표약가"],
                "lawdata": issue.detail["lawdata단가"],
                "custom": decision.get("value"),
            }[decision["choice"]]
            entries.append(
                changelog.LogEntry(
                    구분="검토선택",
                    항목="단가 선택",
                    보험코드=issue.보험코드,
                    제품명=issue.제품명,
                    이전값=f"lawdata {issue.detail['lawdata단가']} / 요율표 {issue.detail['요율표약가']}",
                    새값=str(chosen),
                    사유=decision.get("reason", ""),
                    적용EDI월=edi_month,
                )
            )

        elif issue.code in (conv.NOTE_RESTRICTION, conv.EXCLUDED_PRODUCT) and "include" in decision:
            entries.append(
                changelog.LogEntry(
                    구분="검토선택",
                    항목=issue.title,
                    보험코드=issue.보험코드,
                    제품명=issue.제품명,
                    이전값=issue.message,
                    새값="포함" if decision["include"] else "제외",
                    사유=decision.get("reason", ""),
                    적용EDI월=edi_month,
                )
            )

        elif issue.code == conv.VALUE_CHANGED and decision.get("confirmed"):
            entries.append(
                changelog.LogEntry(
                    구분="검토선택",
                    항목=f"적용값 변경 확인 ({issue.detail['항목']})",
                    보험코드=issue.보험코드,
                    제품명=issue.제품명,
                    이전값=str(issue.detail["이전값"]),
                    새값=str(issue.detail["새값"]),
                    사유=decision.get("reason", ""),
                    적용EDI월=edi_month,
                )
            )

        elif issue.code == conv.RATE_TABLE_DUP and decision.get("row"):
            entries.append(
                changelog.LogEntry(
                    구분="검토선택",
                    항목="요율표 중복 코드 선택",
                    보험코드=issue.보험코드,
                    제품명=issue.제품명,
                    새값=f"요율표 {decision['row']}행",
                    사유=decision.get("reason", ""),
                    적용EDI월=edi_month,
                )
            )

        elif issue.code == conv.NOT_IN_RATE_TABLE and decision.get("action") == "manual":
            values = decision.get("values") or {}
            entries.append(
                changelog.LogEntry(
                    구분="검토선택",
                    항목="요율표에 없는 코드 직접 입력",
                    보험코드=issue.보험코드,
                    제품명=issue.제품명,
                    새값=str(values),
                    사유=decision.get("reason", ""),
                    적용EDI월=edi_month,
                )
            )

        elif issue.code == conv.DUPLICATE_MONTH and decision.get("action"):
            entries.append(
                changelog.LogEntry(
                    구분="검토선택",
                    항목="같은 정산월 기존 행",
                    새값="교체" if decision["action"] == "replace" else "중단",
                    사유=decision.get("reason", ""),
                    적용EDI월=settlement_month,
                )
            )

    if master_changed:
        ctx.master.save()
    if settings_changed:
        ctx.settings.save()
    if entries:
        changelog.append(entries)
    return notes


def _edi_month(result: ConversionResult, issue) -> str:
    """이 검토 항목이 걸린 행의 처방월 (없으면 빈 문자열)."""
    if not issue.rows:
        return ""
    orders = set(issue.rows)
    months = sorted(
        {r.처방월 for r in (result.rows + result.excluded) if r.order in orders and r.처방월}
    )
    return months[0] if months else ""
