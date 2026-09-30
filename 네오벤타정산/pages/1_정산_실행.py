"""정산 실행: lawdata → 검토 → 최종 엑셀 생성."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import uihelp
from core import apply as apply_mod
from core import converter as conv
from core import lawdata as lawdata_mod
from core import writer as writer_mod
from core.final_db import load_final_db
from core.utils import month_shift

uihelp.page_setup("정산 실행")

if not uihelp.require_ready():
    st.stop()

decisions: dict = st.session_state.setdefault("decisions", {})


def sync(key: str, payload) -> None:
    """검토 선택을 저장하고 다시 계산한다. payload 가 None 이면 미결정."""
    current = decisions.get(key)
    if payload is None:
        if key in decisions:
            del decisions[key]
            st.rerun()
        return
    if current != payload:
        decisions[key] = payload
        st.rerun()


def reason_box(key: str, existing: dict) -> str:
    return st.text_input(
        "사유 (선택)", value=existing.get("reason", ""), key=f"reason_{key}", label_visibility="collapsed",
        placeholder="사유 (변경 이력에 남습니다)",
    )


# ------------------------------------------------------------------ 1. 파일

st.subheader("① 파일 고르기")
col1, col2 = st.columns(2)
with col1:
    lawdata_path = uihelp.path_input("lawdata 엑셀", "lawdata", help_text="EDI 처방 원본")
with col2:
    final_path = uihelp.path_input("최종 정산 엑셀", "final", help_text="2026년 거래처별 세부내역 시트가 있는 파일")

if lawdata_path is None or final_path is None:
    st.info("두 파일을 모두 고르면 다음 단계가 열립니다.")
    st.stop()

uihelp.remember_path("lawdata", lawdata_path)
uihelp.remember_path("final", final_path)

# ------------------------------------------------------------------ 2. 시트·정산월

st.subheader("② 정산월 고르기")
try:
    sheet_months = lawdata_mod.scan(lawdata_path)
except Exception as exc:  # noqa: BLE001
    st.error(f"lawdata 를 읽지 못했습니다: {exc}")
    st.stop()

sheets = [s for s, months in sheet_months.items() if months]
if not sheets:
    st.error("lawdata 에서 정산월을 찾지 못했습니다. '정산월' 컬럼이 있는지 확인하세요.")
    st.stop()

# 시트가 하나면 고를 것도 없다. 여러 개일 때만 보여준다.
if len(sheets) == 1:
    sheet = sheets[0]
    st.caption(f"시트: **{sheet}** (하나뿐이라 자동 선택)")
else:
    default_sheet = lawdata_mod.suggest_sheet(
        sheets, st.session_state.get("month", pd.Timestamp.today().strftime("%Y-%m"))
    )
    sheet = st.selectbox(
        "시트", sheets, index=sheets.index(default_sheet) if default_sheet in sheets else len(sheets) - 1
    )

months_in_sheet = sheet_months[sheet]
col1, col2 = st.columns([2, 5])
settlement_month = col1.selectbox(
    "정산월", months_in_sheet, index=len(months_in_sheet) - 1,
    help="lawdata 에 들어 있는 정산월만 고를 수 있습니다.",
)
if len(months_in_sheet) > 1:
    col2.caption(f"이 시트에 있는 정산월: {', '.join(months_in_sheet)}")

signature = (str(lawdata_path), sheet, settlement_month, str(final_path))
if st.session_state.get("signature") != signature:
    st.session_state["signature"] = signature
    st.session_state["month"] = settlement_month
    decisions.clear()

law_rows = lawdata_mod.load_settlement(lawdata_path, sheet, settlement_month)
rx_first, rx_last = lawdata_mod.prescription_range(law_rows)
rx_text = rx_first if rx_first == rx_last else f"{rx_first} ~ {rx_last}"

st.info(
    f"**정산월 {settlement_month}**  ·  **처방월 {rx_text}**  ·  {len(law_rows)}행",
    icon="🗓️",
)
st.caption(
    "요율표 비고의 'O월 EDI' 는 처방월을 뜻합니다. 정산 제한 조건은 처방월로 따집니다."
)

ctx = conv.ConvertContext(
    master=uihelp.load_master(),
    settings=uihelp.load_settings(),
    rate_table=uihelp.load_rate_table(),
    final_db=load_final_db(final_path),
)
result = conv.convert(law_rows, ctx, settlement_month, decisions)

# ------------------------------------------------------------------ 3. 미리보기

st.subheader("③ 변환 미리보기")
cols = st.columns(5)
cols[0].metric("가져온 행", f"{len(law_rows)}")
cols[1].metric("출력 행", f"{len(result.rows)}")
cols[2].metric("검토 필요", f"{len(result.open_issues)}")
cols[3].metric("금액 합계", uihelp.money(result.금액합계))
cols[4].metric("확정금액 합계", uihelp.money(result.확정금액합계))

need_review = {order for issue in result.open_issues for order in issue.rows}


def preview_frame(rows) -> pd.DataFrame:
    data = []
    for row in rows:
        data.append(
            {
                "검토": "⚠️" if row.order in need_review else ("제외" if row.제외 else ""),
                "처방월": row.처방월,
                "정산월": row.정산월,
                "병원명": row.병원명,
                "제약사": row.제약사,
                "구분": row.구분,
                "제품명": row.제품명,
                "단가": row.단가,
                "수량": row.수량,
                "금액": row.금액,
                "수수료": uihelp.percent(row.수수료),
                "구간인센": uihelp.percent(row.구간인센),
                "특별인센": uihelp.percent(row.특별인센),
                "최종요율": uihelp.percent(row.최종요율),
                "확정금액": round(row.확정금액, 2),
                "정산내역확인": "소액처" if row.소액처 else "",
                "참고": " / ".join(row.참고),
            }
        )
    return pd.DataFrame(data)


tab_all, tab_excluded = st.tabs([f"출력 대상 {len(result.rows)}행", f"제외 {len(result.excluded)}행"])
with tab_all:
    st.dataframe(preview_frame(result.rows), use_container_width=True, hide_index=True, height=340)
with tab_excluded:
    if result.excluded:
        frame = preview_frame(result.excluded)
        frame["제외사유"] = [row.제외사유 for row in result.excluded]
        st.dataframe(frame, use_container_width=True, hide_index=True)
    else:
        st.caption("제외된 행이 없습니다.")

# ------------------------------------------------------------------ 4. 검토 패널

st.subheader("④ 검토")
if not result.issues:
    st.success("검토할 항목이 없습니다.")
else:
    open_count = len(result.open_issues)
    if open_count:
        st.warning(f"처리해야 할 항목 {open_count}건이 남았습니다.", icon="✋")
    else:
        st.success("검토를 모두 끝냈습니다.")

by_code: dict[str, list] = {}
for issue in result.issues:
    by_code.setdefault(issue.code, []).append(issue)

for code, issues in by_code.items():
    unresolved = [i for i in issues if i.blocking and not i.resolved]
    label = f"{conv.ISSUE_TITLES.get(code, code)} — {len(issues)}건"
    if unresolved:
        label += f" (미처리 {len(unresolved)})"
    with st.expander(label, expanded=bool(unresolved)):
        for issue in issues:
            existing = decisions.get(issue.key) or {}
            st.markdown(f"**{'✅' if issue.resolved else '⬜'} {issue.message}**")

            if code == conv.DUPLICATE_MONTH:
                choice = st.radio(
                    "어떻게 할까요?",
                    ["선택 안 함", "기존 행을 교체", "중단"],
                    index={None: 0, "replace": 1, "abort": 2}[existing.get("action")],
                    key=f"w_{issue.key}",
                    horizontal=True,
                )
                payload = {None: None, "기존 행을 교체": {"action": "replace"}, "중단": {"action": "abort"}}.get(
                    choice if choice != "선택 안 함" else None
                )
                sync(issue.key, payload)

            elif code == conv.PRICE_MISMATCH:
                law_price = issue.detail["lawdata단가"]
                rate_price = issue.detail["요율표약가"]
                options = ["선택 안 함", f"요율표 약가 {rate_price:,g}", f"lawdata 단가 {law_price:,g}", "직접 입력"]
                index = {None: 0, "rate": 1, "lawdata": 2, "custom": 3}[existing.get("choice")]
                choice = st.radio("쓸 단가", options, index=index, key=f"w_{issue.key}", horizontal=True)
                reason = reason_box(issue.key, existing)
                if choice == options[0]:
                    sync(issue.key, None)
                elif choice == options[1]:
                    sync(issue.key, {"choice": "rate", "reason": reason})
                elif choice == options[2]:
                    sync(issue.key, {"choice": "lawdata", "reason": reason})
                else:
                    value = st.number_input(
                        "직접 입력할 단가",
                        value=float(existing.get("value") or rate_price),
                        step=1.0,
                        key=f"v_{issue.key}",
                    )
                    sync(issue.key, {"choice": "custom", "value": value, "reason": reason})

            elif code == conv.PRODUCT_CODE_CHANGED:
                st.caption(
                    f"lawdata 약제명: {issue.detail['lawdata약제명']} · "
                    f"기존 코드 {issue.detail['기존코드']} → 새 코드 {issue.detail['새코드']}"
                )
                choice = st.radio(
                    "같은 제품인가요?",
                    ["선택 안 함", f"같은 제품 — '{issue.detail['추천제품']}' 에 코드 추가", "이 행 제외"],
                    index={None: 0, "link": 1, "exclude": 2}[existing.get("action")],
                    key=f"w_{issue.key}",
                )
                reason = reason_box(issue.key, existing)
                if choice.startswith("같은 제품"):
                    sync(issue.key, {"action": "link", "reason": reason})
                elif choice == "이 행 제외":
                    sync(issue.key, {"action": "exclude", "reason": reason})
                else:
                    sync(issue.key, None)

            elif code == conv.PRODUCT_RENAMED:
                후보 = issue.detail["후보"]
                st.caption(f"lawdata 약제명: {issue.detail['lawdata약제명']}")
                labels = ["선택 안 함"] + [f"{name} ({c}) 유사도 {s}" for name, c, s in 후보] + [
                    "신규 제품으로 등록",
                    "이 행 제외",
                ]
                choice = st.radio("어떻게 할까요?", labels, key=f"w_{issue.key}")
                reason = reason_box(issue.key, existing)
                if choice == labels[0]:
                    sync(issue.key, None)
                elif choice == "신규 제품으로 등록":
                    sync(issue.key, {"action": "new", "reason": reason})
                elif choice == "이 행 제외":
                    sync(issue.key, {"action": "exclude", "reason": reason})
                else:
                    target = 후보[labels.index(choice) - 1][1]
                    sync(issue.key, {"action": "link", "target": target, "reason": reason})

            elif code == conv.NEW_PRODUCT:
                if issue.detail["요율표있음"]:
                    st.caption(f"요율표 제품명: {issue.detail['요율표제품명']}")
                else:
                    st.caption("요율표에도 없는 코드입니다.")
                product = existing.get("product") or {}
                cols = st.columns([3, 1, 1])
                name = cols[0].text_input(
                    "최종 제품명",
                    value=product.get("최종제품명") or issue.detail["추천제품명"],
                    key=f"n_{issue.key}",
                )
                구간 = cols[1].number_input(
                    "구간인센%", value=float(product.get("구간인센") or 0.0), step=0.01,
                    format="%.4f", key=f"g_{issue.key}",
                )
                특별 = cols[2].number_input(
                    "특별인센%", value=float(product.get("특별인센") or 0.0), step=0.01,
                    format="%.4f", key=f"s_{issue.key}",
                )
                reason = reason_box(issue.key, existing)
                action_cols = st.columns(2)
                if action_cols[0].button("마스터에 등록", key=f"reg_{issue.key}"):
                    sync(
                        issue.key,
                        {
                            "action": "register",
                            "product": {"최종제품명": name, "구간인센": 구간, "특별인센": 특별},
                            "reason": reason,
                        },
                    )
                if action_cols[1].button("이 제품 제외", key=f"exc_{issue.key}"):
                    sync(issue.key, {"action": "exclude", "reason": reason})

            elif code == conv.NOT_IN_RATE_TABLE:
                values = existing.get("values") or {}
                cols = st.columns(4)
                제약사 = cols[0].text_input("제약사명", value=values.get("제약사명") or issue.detail.get("lawdata제조사", ""), key=f"c_{issue.key}")
                구분 = cols[1].text_input("구분", value=str(values.get("구분") or ""), key=f"k_{issue.key}")
                약가 = cols[2].number_input("약가", value=float(values.get("약가") or issue.detail.get("lawdata단가") or 0), step=1.0, key=f"p_{issue.key}")
                요율 = cols[3].number_input("요율", value=float(values.get("요율") or 0), step=0.01, format="%.4f", key=f"r_{issue.key}")
                reason = reason_box(issue.key, existing)
                action_cols = st.columns(2)
                if action_cols[0].button("이 값으로 정산", key=f"man_{issue.key}"):
                    sync(
                        issue.key,
                        {
                            "action": "manual",
                            "values": {"제약사명": 제약사, "구분": 구분, "약가": 약가, "요율": 요율},
                            "reason": reason,
                        },
                    )
                if action_cols[1].button("제외", key=f"nex_{issue.key}"):
                    sync(issue.key, {"action": "exclude", "reason": reason})

            elif code == conv.RATE_TABLE_DUP:
                frame = pd.DataFrame(issue.detail["행"])
                st.dataframe(frame, use_container_width=True, hide_index=True)
                rows = [r["row"] for r in issue.detail["행"]]
                labels = ["선택 안 함"] + [f"요율표 {r}행" for r in rows]
                index = labels.index(f"요율표 {existing.get('row')}행") if existing.get("row") in rows else 0
                choice = st.radio("쓸 행", labels, index=index, key=f"w_{issue.key}", horizontal=True)
                reason = reason_box(issue.key, existing)
                if choice == labels[0]:
                    sync(issue.key, None)
                else:
                    sync(issue.key, {"row": rows[labels.index(choice) - 1], "reason": reason})

            elif code in (conv.NOTE_RESTRICTION, conv.EXCLUDED_PRODUCT):
                if code == conv.NOTE_RESTRICTION:
                    st.caption(f"요율표 비고: {issue.detail['비고']}")
                labels = ["선택 안 함", "포함", "제외"]
                index = {None: 0, True: 1, False: 2}[existing.get("include")]
                choice = st.radio("어떻게 할까요?", labels, index=index, key=f"w_{issue.key}", horizontal=True)
                reason = reason_box(issue.key, existing)
                if choice == "선택 안 함":
                    sync(issue.key, None)
                else:
                    payload = {"include": choice == "포함", "reason": reason}
                    if st.button(
                        f"같은 제품({issue.제품명}) 전체에 적용", key=f"bulk_{issue.key}"
                    ):
                        same = [i for i in result.issues if i.code == code and i.제품명 == issue.제품명]
                        for other in same:
                            decisions[other.key] = payload
                        st.rerun()
                    sync(issue.key, payload)

            elif code == conv.VALUE_CHANGED:
                cols = st.columns(2)
                cols[0].metric(f"이전 {issue.detail['항목']} ({issue.detail['이전정산월']})", f"{issue.detail['이전값']:,g}")
                cols[1].metric(f"이번 {issue.detail['항목']}", f"{issue.detail['새값']:,g}")
                reason = reason_box(issue.key, existing)
                checked = st.checkbox(
                    "의도한 변경입니다", value=bool(existing.get("confirmed")), key=f"w_{issue.key}"
                )
                sync(issue.key, {"confirmed": True, "reason": reason} if checked else None)

            elif code == conv.NO_THRESHOLD:
                원문 = issue.detail.get("원문")
                if 원문:
                    st.caption(f"금액인정 시트 값: {원문}")
                value = st.number_input(
                    "최소 인정금액 (0 이면 판정하지 않음)",
                    value=float(existing.get("value") or 0),
                    step=10_000.0,
                    key=f"w_{issue.key}",
                )
                reason = reason_box(issue.key, existing)
                if st.button("저장하고 적용", key=f"th_{issue.key}"):
                    sync(issue.key, {"value": int(value) if value > 0 else None, "reason": reason})

            st.divider()

# ------------------------------------------------------------------ 5. 소액처

st.subheader("⑤ 소액처")
if result.small_groups:
    frame = pd.DataFrame(result.small_groups)
    frame["금액"] = frame["금액"].map(uihelp.money)
    frame["기준"] = frame["기준"].map(uihelp.money)
    st.dataframe(frame, use_container_width=True, hide_index=True)
    st.caption(
        f"{len(result.small_groups)}개 그룹 / "
        f"{sum(1 for r in result.rows if r.소액처)}행 → 확정금액 0, 정산내역확인 '소액처'"
    )
else:
    st.caption("소액처가 없습니다.")

# ------------------------------------------------------------------ 6. 생성

st.subheader("⑥ 최종 엑셀 만들기")
abort = (decisions.get(conv.DUPLICATE_MONTH) or {}).get("action") == "abort"
if abort:
    st.error("같은 정산월 항목에서 '중단' 을 골랐습니다. 교체로 바꾸거나 정산월을 다시 고르세요.")
elif not result.ready:
    st.button("최종 엑셀 생성", disabled=True)
    st.caption("검토 항목을 모두 처리하면 켜집니다.")
else:
    st.caption(
        f"① 고른 최종 엑셀(`{Path(final_path).name}`)에 이번 달 행을 추가하고 "
        f"② 바탕화면에 `{writer_mod.desktop_file_name(settlement_month)}` 를 만듭니다. "
        f"바탕화면 파일에는 {settlement_month.split('-')[0]}년 정산분이 모두 들어갑니다."
    )
    if st.button("최종 엑셀 생성", type="primary"):
        try:
            notes = apply_mod.apply_decisions(ctx, result, decisions, settlement_month=settlement_month)
            report = writer_mod.write_settlement(
                final_path,
                result,
                replace_month=(decisions.get(conv.DUPLICATE_MONTH) or {}).get("action") == "replace",
                vendor_name=ctx.settings.vendor_name,
            )
        except PermissionError:
            st.error(
                f"`{Path(final_path).name}` 을 저장하지 못했습니다. "
                "엑셀에서 그 파일을 열어 두었다면 닫고 다시 눌러 주세요."
            )
        except Exception as exc:  # noqa: BLE001
            st.exception(exc)
        else:
            uihelp.invalidate()
            st.success(f"바탕화면에 저장했습니다: {report.desktop_path.name}", icon="✅")
            st.caption(f"기존 최종 엑셀도 갱신했습니다: {report.final_path}")
            if report.backup_path:
                st.caption(f"갱신 전 백업: {report.backup_path}")

            cols = st.columns(4)
            cols[0].metric("추가 행", report.추가행수)
            cols[1].metric("교체 행", report.교체행수)
            cols[2].metric("금액 합계", uihelp.money(report.금액합계))
            cols[3].metric("확정금액 합계", uihelp.money(report.확정금액합계))
            st.caption(
                f"표 범위 {report.표범위} · 전체 {report.총행수}행 · "
                f"바탕화면 파일 {report.연도}년 {report.연도행수}행 · "
                f"슬라이서 {report.슬라이서}개 · "
                f"소액처 {report.소액처그룹}그룹/{report.소액처행수}행 · "
                f"종합 B18 = {report.확정금액합계:,.2f}"
            )
            if notes:
                st.write("기준정보에 반영한 내용:")
                for note in notes:
                    st.write(f"- {note}")
            with open(report.desktop_path, "rb") as fh:
                st.download_button(
                    "바탕화면 파일 내려받기",
                    fh.read(),
                    file_name=report.desktop_path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
