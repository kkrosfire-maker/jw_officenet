"""변경 이력 조회."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import uihelp
from core import changelog
from core.config import CHANGE_LOG_PATH

uihelp.page_setup("변경 이력")

records = changelog.read_all()
if not records:
    st.info("아직 기록된 변경이 없습니다.")
    st.stop()

frame = pd.DataFrame(records)[changelog.FIELDS]

cols = st.columns([2, 2, 3])
구분목록 = sorted(frame["구분"].dropna().unique())
선택구분 = cols[0].multiselect("구분", 구분목록, default=구분목록)
검색 = cols[1].text_input("검색 (제품명·보험코드·항목·사유)")
정렬 = cols[2].radio("정렬", ["최신순", "오래된순"], horizontal=True)

view = frame[frame["구분"].isin(선택구분)]
if 검색:
    needle = 검색.strip().lower()
    mask = False
    for column in ("보험코드", "제품명", "항목", "사유", "이전값", "새값"):
        mask = mask | view[column].astype(str).str.lower().str.contains(needle, na=False)
    view = view[mask]
view = view.sort_values("일시", ascending=(정렬 == "오래된순"))

st.caption(f"{len(view)}건 / 전체 {len(frame)}건")
st.dataframe(view, use_container_width=True, hide_index=True, height=520)

st.download_button(
    "CSV 내려받기",
    CHANGE_LOG_PATH.read_bytes(),
    file_name=CHANGE_LOG_PATH.name,
    mime="text/csv",
)
st.caption(f"파일: {CHANGE_LOG_PATH}")
