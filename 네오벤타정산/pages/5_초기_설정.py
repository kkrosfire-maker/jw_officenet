"""초기 설정: 변환엑셀·요율표·lawdata 로 제품 마스터를 만든다 (첫 실행 한 번)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import uihelp
from core import changelog
from core import master as master_mod
from core import rate_table as rate_mod

uihelp.page_setup("초기 설정")

settings = uihelp.load_settings()
master = uihelp.load_master()

if settings.initialized:
    st.success(
        f"이미 초기화되어 있습니다. 제품 {len(master.products)}개. "
        "다시 하면 현재 마스터를 덮어씁니다 (이전 파일은 백업됩니다)."
    )

st.markdown(
    """
초기화는 세 파일을 씁니다.

1. **lawdata** — 전체 시트에서 `제품 ↔ 보험코드` 쌍을 모읍니다
2. **변환엑셀** — `변환자료` 의 `변경명` → 최종 제품명, 구간인센, 특별인센 / `금액인정` → 최소 인정금액
3. **요율표** — 약가·요율·구분·제약사명·비고의 기준
"""
)

col1, col2, col3 = st.columns(3)
with col1:
    lawdata_path = uihelp.path_input("lawdata 엑셀", "lawdata")
with col2:
    conversion_path = uihelp.path_input("변환엑셀", "conversion")
with col3:
    current = rate_mod.current_version()
    if current is not None:
        st.markdown("**요율표**")
        st.success(current.title, icon="📄")
        st.caption("지금 쓰는 요율표입니다. 바꾸려면 아래에서 새로 올리세요.")
    rate_upload = uihelp.path_input(
        "요율표 엑셀" if current is None else "요율표 새로 올리기",
        "rate_table",
        help_text="'제품별 수수료' 시트가 있는 파일",
        remember=False,
    )
    if rate_upload is not None and st.button("이 요율표 쓰기", type="primary", key="use_rate"):
        try:
            version = rate_mod.add_version(rate_upload, approved=True)
        except Exception as exc:  # noqa: BLE001
            st.exception(exc)
        else:
            changelog.log("요율표승인", "요율표 등록 (초기 설정)", 새값=version.title)
            st.session_state.pop("init_result", None)
            uihelp.invalidate()
            st.success(f"요율표를 바꿨습니다: {version.title}")
            st.rerun()

current = rate_mod.current_version()
if current is None:
    st.warning("요율표를 올려야 다음으로 넘어갑니다.", icon="⚠️")
    st.stop()

if lawdata_path is None or conversion_path is None:
    st.info("lawdata 와 변환엑셀을 올리면 미리보기가 나옵니다.")
    st.stop()

uihelp.remember_path("lawdata", lawdata_path)
uihelp.remember_path("conversion", conversion_path)

if st.button("미리보기 만들기", type="primary"):
    try:
        st.session_state["init_result"] = master_mod.initialize(
            conversion_path=conversion_path,
            lawdata_path=lawdata_path,
            rate_table=uihelp.load_rate_table(),
        )
    except Exception as exc:  # noqa: BLE001
        st.exception(exc)

result = st.session_state.get("init_result")
if result is None:
    st.stop()

st.divider()
cols = st.columns(5)
cols[0].metric("제품", len(result.master.products))
cols[1].metric("lawdata 코드쌍", result.pair_count)
cols[2].metric("요율표에서 되찾은 코드", len(result.recovered))
cols[3].metric("보험코드 none", len(result.unmatched))
cols[4].metric("대조 차이", len(result.diffs))

st.subheader("보험코드 채우기")
st.caption(
    "변환엑셀에만 있고 lawdata 에 없던 제품은 보험코드를 모릅니다. "
    "요율표를 거꾸로 뒤져서 **제품명이 정확히 같을 때만** 코드를 채웁니다."
)
tab_ok, tab_check, tab_none = st.tabs(
    [
        f"자동으로 채움 {len(result.recovered)}",
        f"확인 필요 {len(result.suggestions)}",
        f"none {len(result.unmatched)}",
    ]
)
with tab_ok:
    if result.recovered:
        st.dataframe(
            pd.DataFrame(
                [
                    {"제품명": n, "보험코드": c, "요율표 제품명": rn}
                    for n, c, rn, _ in result.recovered
                ]
            ),
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("없음")
with tab_check:
    st.caption(
        "이름이 **비슷하기만** 해서 자동으로 넣지 않았습니다. 용량이 다른 제품이 섞일 수 있습니다. "
        "기준정보 관리에서 확인하고 직접 넣어 주세요."
    )
    if result.suggestions:
        st.dataframe(
            pd.DataFrame(
                [
                    {"제품명": n, "요율표 추천 코드": c, "요율표 제품명": rn, "유사도": s}
                    for n, c, rn, s in result.suggestions
                ]
            ),
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("없음")
with tab_none:
    st.caption("요율표에서도 찾지 못했습니다. 기준정보 관리에서 직접 넣어 주세요.")
    if result.unmatched:
        st.dataframe(
            uihelp.red_none(
                pd.DataFrame([{"보험코드": "none", "제품명": n} for n in result.unmatched]),
                ["보험코드"],
            ),
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("없음")

st.subheader("초기화 대조 리포트")
st.caption(
    "변환엑셀 값과 요율표 값이 다른 항목입니다. **이후 계산에는 요율표 값을 씁니다.** "
    "변환엑셀 쪽이 맞다면 기준정보 관리에서 제품 마스터를 고치세요."
)
if result.diffs:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "보험코드": d.보험코드,
                    "제품명": d.제품명,
                    "항목": d.항목,
                    "변환엑셀 값": d.변환엑셀값,
                    "요율표 값 (적용)": d.요율표값,
                }
                for d in result.diffs
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.success("차이가 없습니다.")

with st.expander("만들어질 제품 마스터 보기"):
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "보험코드": p.code_display,
                    "최종제품명": p.최종제품명,
                    "별칭": " | ".join(p.별칭),
                    "구간인센%": p.구간인센,
                    "특별인센%": p.특별인센,
                    "제외": p.제외,
                    "메모": p.메모,
                }
                for p in result.master.products
            ]
        ),
        use_container_width=True,
        hide_index=True,
        height=400,
    )

with st.expander("최소 인정금액 (확인 필요 항목)"):
    need = {
        name: entry for name, entry in result.settings.thresholds.items() if entry.get("needs_input")
    }
    st.caption(
        f"{len(need)}개 항목은 표기가 애매해서 숫자를 직접 넣어야 합니다. "
        "기준정보 관리 → 제약사 설정에서 고칠 수 있습니다."
    )
    if need:
        st.dataframe(
            pd.DataFrame(
                [{"제약사명": n, "원문": e.get("raw"), "추정값": e.get("value")} for n, e in need.items()]
            ),
            use_container_width=True,
            hide_index=True,
        )

st.divider()
if st.button("이 내용으로 기준정보 저장", type="primary"):
    master_mod.commit_initialize(result)
    st.session_state.pop("init_result", None)
    uihelp.invalidate()
    st.success("저장했습니다. '정산 실행' 으로 넘어가세요.")
    st.page_link("pages/1_정산_실행.py", label="정산 실행으로", icon="▶️")
