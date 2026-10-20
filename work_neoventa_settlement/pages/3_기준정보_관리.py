"""기준정보 관리: 제품 마스터, 제약사별 최소금액."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import uihelp
from core import changelog
from core.master import LIST_SEP, NO_CODE_PREFIX, NO_CODE_TEXT, Product, find_code_by_name
from core.utils import code_key, to_number

uihelp.page_setup("기준정보 관리")

master = uihelp.load_master()
settings = uihelp.load_settings()
rate_table = uihelp.load_rate_table()

tab_master, tab_company = st.tabs(["제품 마스터", "제약사별 최소금액"])

# ------------------------------------------------------------------ 제품 마스터

with tab_master:
    코드없음 = [p for p in master.products if p.code_unknown]
    if 코드없음:
        st.error(
            f"보험코드를 모르는 제품이 **{len(코드없음)}개** 있습니다 (`none`). "
            "요율표에서 찾지 못한 제품이니 보험코드를 직접 넣어 주세요.",
            icon="🚫",
        )
        with st.expander(f"보험코드 없는 제품 {len(코드없음)}개 보기", expanded=True):
            name_index = uihelp.rate_name_index()
            추천 = []
            for product in 코드없음:
                code, rate_name, score = find_code_by_name(
                    product.최종제품명, rate_table, name_index
                )
                추천.append(
                    {
                        "보험코드": NO_CODE_TEXT,
                        "최종제품명": product.최종제품명,
                        "요율표 추천 코드": code or "",
                        "요율표 제품명": rate_name or "",
                        # 문자열로 통일한다. 실수와 빈 값을 섞으면 표로 못 그린다.
                        "유사도": f"{score:.3f}" if code else "",
                    }
                )
            frame = pd.DataFrame(추천)
            st.dataframe(
                uihelp.red_none(frame, ["보험코드"]),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "추천은 이름이 비슷할 뿐이라 자동으로 넣지 않습니다 "
                "(용량이 다른 제품이 섞일 수 있습니다). 아래 표에서 직접 확인하고 넣어 주세요."
            )

    cols = st.columns([3, 2, 2])
    query = cols[0].text_input("검색 (제품명·보험코드·별칭)", key="master_query")
    sort_key = cols[1].selectbox("정렬", ["최종제품명", "보험코드", "구간인센(%)", "특별인센(%)"])
    only_flagged = cols[2].checkbox("보험코드 없음·제외만 보기")

    rows = []
    for product in master.products:
        entry = rate_table.first(product.보험코드) if rate_table else None
        rows.append(
            {
                "보험코드": product.code_display,
                "최종제품명": product.최종제품명,
                "lawdata약제명별칭": LIST_SEP.join(product.별칭),
                "이전보험코드": LIST_SEP.join(product.이전보험코드),
                "구간인센(%)": None if product.구간인센 is None else product.구간인센 * 100,
                "특별인센(%)": None if product.특별인센 is None else product.특별인센 * 100,
                "제외여부": product.제외,
                "메모": product.메모,
                "요율표 제약사": entry.제약사명 if entry else "",
                "요율표 약가": entry.약가 if entry else None,
                "요율표 요율(%)": None if not entry or entry.요율 is None else entry.요율 * 100,
                "요율표 비고": entry.비고 if entry else "",
                "_key": product.보험코드,        # 원래 키 (none 이어도 구분된다)
            }
        )
    frame = pd.DataFrame(rows)

    if query:
        needle = query.strip().lower()
        mask = (
            frame["보험코드"].str.lower().str.contains(needle, na=False)
            | frame["최종제품명"].str.lower().str.contains(needle, na=False)
            | frame["lawdata약제명별칭"].str.lower().str.contains(needle, na=False)
        )
        frame = frame[mask]
    if only_flagged:
        frame = frame[(frame["보험코드"] == NO_CODE_TEXT) | frame["제외여부"]]
    frame = frame.sort_values(sort_key, na_position="last").reset_index(drop=True)

    st.caption(
        f"{len(frame)}개 표시 / 전체 {len(master.products)}개. "
        "인센티브는 **%** 로 넣습니다 (3 = 3%). 요율표 열은 참고용이라 고쳐도 저장되지 않습니다."
    )
    edited = st.data_editor(
        frame,
        use_container_width=True,
        hide_index=True,
        height=420,
        num_rows="dynamic",
        disabled=["요율표 제약사", "요율표 약가", "요율표 요율(%)", "요율표 비고", "_key"],
        column_config={
            "보험코드": st.column_config.TextColumn(
                help="모르면 none. 요율표에서 찾아 직접 넣어 주세요."
            ),
            "구간인센(%)": st.column_config.NumberColumn(format="%.2f", help="3 = 3%"),
            "특별인센(%)": st.column_config.NumberColumn(format="%.2f", help="3 = 3%"),
            "요율표 요율(%)": st.column_config.NumberColumn(format="%.2f"),
            "제외여부": st.column_config.CheckboxColumn(),
            "_key": None,
        },
        key="master_editor",
    )

    if st.button("제품 마스터 저장", type="primary"):
        before = {p.보험코드: p for p in master.products}
        entries: list[changelog.LogEntry] = []
        touched: set[str] = set()
        오류: list[str] = []

        for record in edited.to_dict("records"):
            원래키 = code_key(record.get("_key") or "")
            입력코드 = code_key(record["보험코드"])
            if 입력코드.lower() in ("", NO_CODE_TEXT):
                # 아직 모르는 코드. 원래 임시 키를 유지한다.
                code = 원래키 if 원래키.startswith(NO_CODE_PREFIX) else f"{NO_CODE_PREFIX}{abs(hash(record['최종제품명'])) % 1000:03d}"
            else:
                code = 입력코드
            if not record["최종제품명"]:
                continue
            if code in touched:
                오류.append(f"보험코드 {code} 가 여러 줄에 있습니다.")
                continue
            touched.add(code)

            product = Product(
                보험코드=code,
                최종제품명=str(record["최종제품명"] or "").strip(),
                별칭=[a.strip() for a in str(record["lawdata약제명별칭"] or "").split("|") if a.strip()],
                이전보험코드=[c.strip() for c in str(record["이전보험코드"] or "").split("|") if c.strip()],
                구간인센=None if to_number(record["구간인센(%)"]) is None else to_number(record["구간인센(%)"]) / 100,
                특별인센=None if to_number(record["특별인센(%)"]) is None else to_number(record["특별인센(%)"]) / 100,
                제외=bool(record["제외여부"]),
                메모=str(record["메모"] or "").strip(),
            )
            origin = before.get(원래키) or before.get(code)
            if origin is None:
                entries.append(
                    changelog.LogEntry(
                        구분="마스터편집", 항목="제품 추가", 보험코드=product.code_display,
                        제품명=product.최종제품명, 새값=product.최종제품명,
                    )
                )
            else:
                for label, old, new in (
                    ("보험코드", origin.code_display, product.code_display),
                    ("최종제품명", origin.최종제품명, product.최종제품명),
                    ("별칭", LIST_SEP.join(origin.별칭), LIST_SEP.join(product.별칭)),
                    ("이전보험코드", LIST_SEP.join(origin.이전보험코드), LIST_SEP.join(product.이전보험코드)),
                    ("구간인센%", origin.구간인센, product.구간인센),
                    ("특별인센%", origin.특별인센, product.특별인센),
                    ("제외여부", origin.제외, product.제외),
                    ("메모", origin.메모, product.메모),
                ):
                    if old != new:
                        entries.append(
                            changelog.LogEntry(
                                구분="마스터편집", 항목=label, 보험코드=product.code_display,
                                제품명=product.최종제품명, 이전값=old, 새값=new,
                            )
                        )
                if 원래키 != code:
                    master.remove(원래키)
            master.upsert(product)

        # 검색·필터를 걸었을 때 화면에 없던 행은 지우지 않는다.
        shown = {code_key(k) for k in frame["_key"]}
        for code in shown - touched:
            origin = before.get(code)
            master.remove(code)
            entries.append(
                changelog.LogEntry(
                    구분="마스터편집", 항목="제품 삭제", 보험코드=code,
                    제품명=origin.최종제품명 if origin else "",
                    이전값=origin.최종제품명 if origin else "",
                )
            )

        if 오류:
            for message in 오류:
                st.error(message)
        else:
            master.save()
            changelog.append(entries)
            uihelp.invalidate()
            st.success(f"저장했습니다. 변경 {len(entries)}건 (이전 파일은 data/backup/ 에 백업).")
            st.rerun()

# ------------------------------------------------------------------ 제약사별 최소금액

with tab_company:
    st.markdown("#### 제약사별 최소금액")
    st.caption(
        "같은 정산월 안에서 (병원 × 제약사) 금액 합계가 이 금액보다 작으면 소액처로 봅니다. "
        "비워 두면(없음) 소액처 판정을 하지 않습니다."
    )
    th_frame = pd.DataFrame(
        [
            {
                "제약사명": name,
                "최소금액": entry.get("value"),
                "원문": entry.get("raw", ""),
                "확인 필요": bool(entry.get("needs_input")),
            }
            for name, entry in sorted(settings.thresholds.items())
        ]
    )
    only_need = st.checkbox("확인 필요만 보기")
    view = th_frame[th_frame["확인 필요"]] if only_need else th_frame
    th_edited = st.data_editor(
        view,
        use_container_width=True,
        hide_index=True,
        height=380,
        num_rows="dynamic",
        disabled=["원문"],
        column_config={"최소금액": st.column_config.NumberColumn(format="%d")},
        key="threshold_editor",
    )

    st.markdown("#### 제약사명 별칭")
    st.caption("요율표 이름 → 최종파일 표기. 예: 유니메드제약 → 유니메드")
    alias_frame = pd.DataFrame(
        [{"요율표 제약사명": k, "최종파일 표기": v} for k, v in sorted(settings.company_aliases.items())]
        or [{"요율표 제약사명": "", "최종파일 표기": ""}]
    )
    alias_edited = st.data_editor(
        alias_frame, use_container_width=True, hide_index=True, num_rows="dynamic", key="alias_editor"
    )

    if st.button("저장", type="primary", key="save_company"):
        entries: list[changelog.LogEntry] = []

        for record in th_edited.to_dict("records"):
            name = str(record["제약사명"] or "").strip()
            if not name:
                continue
            value = to_number(record["최소금액"])
            before = settings.thresholds.get(name, {})
            marked = bool(record["확인 필요"]) and value is None
            if before.get("value") != value or before.get("needs_input") != marked:
                entries.append(
                    changelog.LogEntry(
                        구분="설정변경", 항목="최소금액", 제품명=name,
                        이전값=before.get("raw", ""),
                        새값="없음" if value is None else str(int(value)),
                    )
                )
            settings.thresholds[name] = {
                "value": int(value) if value is not None else None,
                "raw": before.get("raw", "") or ("없음" if value is None else f"{int(value):,}원"),
                "needs_input": marked,
            }

        new_aliases = {}
        for record in alias_edited.to_dict("records"):
            key = str(record["요율표 제약사명"] or "").strip()
            value = str(record["최종파일 표기"] or "").strip()
            if key and value:
                new_aliases[key] = value
        for key, value in new_aliases.items():
            if settings.company_aliases.get(key) != value:
                entries.append(
                    changelog.LogEntry(
                        구분="설정변경", 항목="제약사명 별칭", 제품명=key,
                        이전값=settings.company_aliases.get(key, ""), 새값=value,
                    )
                )
        for key in set(settings.company_aliases) - set(new_aliases):
            entries.append(
                changelog.LogEntry(
                    구분="설정변경", 항목="제약사명 별칭 삭제", 제품명=key,
                    이전값=settings.company_aliases[key],
                )
            )
        settings.company_aliases = new_aliases

        settings.save()
        changelog.append(entries)
        uihelp.invalidate()
        st.success(f"저장했습니다. 변경 {len(entries)}건.")
        st.rerun()
