"""네오벤타 정산문서 — Streamlit 진입점."""
from __future__ import annotations

import streamlit as st

import uihelp
from core import rate_table as rate_mod
from core.config import CHANGE_LOG_PATH, DATA_DIR

uihelp.page_setup("네오벤타 정산문서")

settings = uihelp.load_settings()
master = uihelp.load_master()
current = rate_mod.current_version()

if not settings.initialized:
    st.info(
        "처음 실행입니다. **초기 설정** 페이지에서 변환엑셀·요율표·lawdata 로 "
        "제품 마스터를 만들고 나서 정산을 실행하세요.",
        icon="👋",
    )

left, right = st.columns(2)

with left:
    st.subheader("이번 달 정산")
    st.markdown(
        """
1. **정산 실행** 에서 lawdata 와 최종 엑셀을 고른다
2. 시트와 정산월을 고른다
3. 검토 항목을 모두 처리한다
4. 최종 엑셀을 만든다
"""
    )
    st.page_link("pages/1_정산_실행.py", label="정산 실행으로", icon="▶️")

with right:
    st.subheader("현재 기준정보")
    st.metric("제품 마스터", f"{len(master.products)}개")
    st.metric("현재 요율표", current.label if current else "없음")
    코드미확인 = [p for p in master.products if p.code_unknown]
    if 코드미확인:
        st.caption(f"보험코드 미확인 제품 {len(코드미확인)}개 — lawdata 에 처음 나올 때 연결됩니다")
    제외 = [p for p in master.products if p.제외]
    if 제외:
        st.caption(f"정산 제외로 표시된 제품 {len(제외)}개")

st.divider()
st.subheader("페이지")
cols = st.columns(4)
cols[0].page_link("pages/2_요율표_업데이트.py", label="요율표 업데이트", icon="📈")
cols[1].page_link("pages/3_기준정보_관리.py", label="기준정보 관리", icon="🗂️")
cols[2].page_link("pages/4_변경_이력.py", label="변경 이력", icon="📜")
cols[3].page_link("pages/5_초기_설정.py", label="초기 설정", icon="⚙️")

with st.expander("데이터 위치"):
    st.code(
        f"""기준정보 폴더 : {DATA_DIR}
제품 마스터   : {DATA_DIR / 'product_master.xlsx'}
제약사 설정   : {DATA_DIR / 'settings.json'}
변경 이력     : {CHANGE_LOG_PATH}
요율표 보관   : {DATA_DIR / 'rate_tables'}
백업          : {DATA_DIR / 'backup'}""",
        language="text",
    )
