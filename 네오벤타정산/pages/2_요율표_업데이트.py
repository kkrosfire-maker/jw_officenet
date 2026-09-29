"""요율표 업데이트: 새 요율표 추가 → 변경 알림 → 항목별 승인."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import uihelp
from core import changelog
from core import rate_table as rate_mod

uihelp.page_setup("요율표 업데이트")

master = uihelp.load_master()
versions = rate_mod.list_versions()
current = rate_mod.current_version()
pending = rate_mod.pending_version()

# ------------------------------------------------------------------ 보관 중인 버전

st.subheader("보관 중인 요율표")
if versions:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "파일": v.file,
                    "이름": v.title,
                    "추가": v.added.replace("T", " "),
                    "상태": "현재" if current and v.file == current.file else ("승인 대기" if not v.approved else "승인"),
                }
                for v in versions
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("아직 등록된 요율표가 없습니다. 아래에서 첫 요율표를 등록하세요.")

st.divider()

# ------------------------------------------------------------------ 새 요율표 추가

st.subheader("새 요율표 추가")
path = uihelp.path_input("요율표 엑셀", "rate_table", help_text="'제품별 수수료' 시트가 있는 파일")
label = st.text_input("버전 이름", value=path.stem if path else "", placeholder="예: 26.08")

if path is not None and st.button("등록하고 변경 확인", type="primary"):
    try:
        version = rate_mod.add_version(path, label=label, approved=current is None)
    except Exception as exc:  # noqa: BLE001
        st.exception(exc)
    else:
        uihelp.remember_path("rate_table", path)
        if current is None:
            changelog.log("요율표승인", "첫 요율표 등록", 새값=version.title)
            st.success(f"첫 요율표로 등록했습니다: {version.title}")
        else:
            st.success(f"등록했습니다: {version.title}. 아래에서 변경 내용을 확인하세요.")
        uihelp.invalidate()
        st.rerun()

# ------------------------------------------------------------------ 변경 알림

if pending is not None and current is not None:
    st.divider()
    st.subheader(f"변경 알림 — {pending.title}")
    st.caption("우리 제품 마스터에 있는 보험코드만 비교합니다.")

    old_table = rate_mod.load_rate_table(current.path)
    new_table = rate_mod.load_rate_table(pending.path)
    codes = master.all_codes()
    diffs = rate_mod.compare(old_table, new_table, codes)

    st.caption(f"비교한 보험코드 {len(set(codes))}개 · 변경 {len(diffs)}건")

    if not diffs:
        st.success("우리 제품에 영향을 주는 변경이 없습니다.")
        if st.button("이 요율표를 현재 버전으로", type="primary"):
            rate_mod.approve_version(pending.file)
            changelog.log("요율표승인", "변경 없음", 새값=pending.title)
            uihelp.invalidate()
            st.rerun()
    else:
        approvals = st.session_state.setdefault("rate_approvals", {})
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "보험코드": d.보험코드,
                        "제품명": d.제품명,
                        "항목": d.항목,
                        "이전값": d.이전값,
                        "새값": d.새값,
                    }
                    for d in diffs
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### 항목별 처리")
        for diff in diffs:
            existing = approvals.get(diff.key, {})
            with st.container(border=True):
                st.markdown(
                    f"**{diff.제품명}** ({diff.보험코드}) · {diff.항목}: "
                    f"`{diff.이전값}` → `{diff.새값}`"
                )
                cols = st.columns([2, 3])
                choice = cols[0].radio(
                    "처리",
                    ["승인 (새 값 사용)", "이전 값 유지"],
                    index=0 if existing.get("action", "approve") == "approve" else 1,
                    key=f"ra_{diff.key}",
                    horizontal=True,
                    label_visibility="collapsed",
                )
                reason = cols[1].text_input(
                    "사유", value=existing.get("reason", ""), key=f"rr_{diff.key}",
                    label_visibility="collapsed", placeholder="사유 (선택)",
                )
                approvals[diff.key] = {
                    "action": "approve" if choice.startswith("승인") else "keep",
                    "reason": reason,
                    "diff": diff,
                }

        st.caption(
            "'이전 값 유지' 는 이 변경을 적용하지 않는다는 뜻입니다. 기록만 남고 요율표 값은 "
            "새 값으로 바뀌므로, 계속 예전 값을 써야 한다면 **제품 마스터**를 직접 고치세요."
        )

        if st.button("승인 완료 — 이 요율표를 현재 버전으로", type="primary"):
            kept = 0
            entries = []
            for key, decision in approvals.items():
                diff = decision["diff"]
                if decision["action"] == "keep":
                    kept += 1
                entries.append(
                    changelog.LogEntry(
                        구분="요율표승인",
                        항목=diff.항목,
                        보험코드=diff.보험코드,
                        제품명=diff.제품명,
                        이전값=str(diff.이전값),
                        새값=str(diff.새값),
                        사유=("승인" if decision["action"] == "approve" else "이전 값 유지")
                        + (f" / {decision['reason']}" if decision["reason"] else ""),
                        적용EDI월="",
                    )
                )
            changelog.append(entries)
            rate_mod.approve_version(pending.file)
            st.session_state.pop("rate_approvals", None)
            uihelp.invalidate()
            st.success(f"{pending.title} 을 현재 요율표로 적용했습니다. (이전 값 유지 {kept}건은 기록만 남았습니다)")
            st.rerun()

    st.divider()
    if st.button("이 요율표 등록 취소 (파일 삭제)"):
        rate_mod.drop_version(pending.file)
        st.session_state.pop("rate_approvals", None)
        uihelp.invalidate()
        st.rerun()
