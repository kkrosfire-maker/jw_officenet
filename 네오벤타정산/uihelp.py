"""Streamlit 페이지 공통 도우미."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit as st

from core import master as master_mod
from core import rate_table as rate_mod
from core.config import ensure_dirs

PAGE_ICON = "🧾"


def page_setup(title: str) -> None:
    st.set_page_config(page_title=f"네오벤타 정산 · {title}", page_icon=PAGE_ICON, layout="wide")
    ensure_dirs()
    _dropzone_css()
    st.title(f"{PAGE_ICON} {title}")
    _status_bar()


def _dropzone_css() -> None:
    """파일 올리는 칸을 한글로 바꾸고 눈에 띄게 만든다.

    Streamlit 기본 문구가 영어라서 가린 뒤 우리 문구를 넣는다. 선택자가 바뀌면
    원래 영어 문구가 그대로 보일 뿐이라 동작에는 지장이 없다.
    """
    st.markdown(
        """
        <style>
        [data-testid="stFileUploaderDropzone"] {
            border: 2px dashed #b9c0ca;
            background: #fafbfc;
            padding: 0.6rem 1rem;
        }
        [data-testid="stFileUploaderDropzone"]:hover {
            border-color: #ff4b4b;
            background: #fff7f7;
        }
        [data-testid="stFileUploaderDropzoneInstructions"] span,
        [data-testid="stFileUploaderDropzoneInstructions"] small {
            display: none;
        }
        [data-testid="stFileUploaderDropzoneInstructions"] > div::before {
            content: "엑셀 파일을 여기로 끌어다 놓으세요";
            font-size: 0.95rem;
            font-weight: 600;
            color: #31333f;
            display: block;
        }
        [data-testid="stFileUploaderDropzoneInstructions"] > div::after {
            content: "또는 오른쪽 버튼으로 찾아보기 · .xlsx";
            font-size: 0.78rem;
            color: #808495;
            display: block;
            margin-top: 2px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _status_bar() -> None:
    """상단 상태: 현재 요율표, 승인 대기 알림, 초기화 여부."""
    settings = load_settings()
    current = rate_mod.current_version()
    pending = rate_mod.pending_version()

    cols = st.columns([4, 2, 3])
    cols[0].caption(
        f"현재 요율표: **{current.title}**" if current else "현재 요율표: **없음**"
    )
    master = load_master()
    cols[1].caption(f"제품 마스터: **{len(master.products)}개**")
    if pending is not None:
        cols[2].warning(f"승인 대기 중인 요율표: {pending.title} → '요율표 업데이트' 에서 확인", icon="🔔")
    elif not settings.initialized:
        cols[2].warning("아직 초기 설정을 하지 않았습니다 → '초기 설정' 페이지", icon="⚠️")
    st.divider()


# ---------------------------------------------------------------- 상태 로딩

def load_master(refresh: bool = False) -> master_mod.ProductMaster:
    if refresh or "master" not in st.session_state:
        st.session_state["master"] = master_mod.ProductMaster.load()
    return st.session_state["master"]


def load_settings(refresh: bool = False) -> master_mod.Settings:
    if refresh or "settings" not in st.session_state:
        st.session_state["settings"] = master_mod.Settings.load()
    return st.session_state["settings"]


def load_rate_table(refresh: bool = False):
    if refresh or "rate_table" not in st.session_state:
        st.session_state["rate_table"] = rate_mod.load_current()
    return st.session_state["rate_table"]


@st.cache_data(show_spinner=False)
def _rate_name_index_cached(version_file: str) -> dict:
    """요율표 제품명 색인. 11,000행짜리라 버전마다 한 번만 만든다."""
    from core.master import build_rate_name_index
    from core.rate_table import load_rate_table

    version = rate_mod.current_version()
    if version is None:
        return {}
    return build_rate_name_index(load_rate_table(version.path))


def rate_name_index() -> dict:
    version = rate_mod.current_version()
    return _rate_name_index_cached(version.file) if version else {}


def invalidate() -> None:
    for key in ("master", "settings", "rate_table"):
        st.session_state.pop(key, None)
    _rate_name_index_cached.clear()


def require_ready() -> bool:
    """요율표와 마스터가 준비됐는지 확인한다."""
    if rate_mod.current_version() is None:
        st.error("승인된 요율표가 없습니다. '요율표 업데이트' 에서 요율표를 먼저 등록하세요.")
        return False
    if not load_master().products:
        st.error("제품 마스터가 비어 있습니다. '초기 설정' 을 먼저 하세요.")
        return False
    return True


# ---------------------------------------------------------------- 입력 위젯

def path_input(
    label: str,
    key: str,
    *,
    extensions=(".xlsx",),
    help_text: str = "",
    remember: bool = True,
) -> Optional[Path]:
    """파일을 끌어다 놓아 고른다. 지난번에 쓴 파일은 기억해서 그대로 다시 쓴다.

    우선순위: 이번에 끌어다 놓은 파일 → 지난번 파일 → 직접 적은 경로
    remember=False 면 지난번 파일을 다시 쓰지 않고 늘 새로 올린다.
    """
    from core.config import UPLOAD_DIR

    settings = load_settings()
    remembered = settings.last_paths.get(key, "") if remember else ""
    remembered_path = Path(remembered) if remembered else None
    has_remembered = bool(remembered_path and remembered_path.exists())

    st.markdown(f"**{label}**" + (f" &nbsp;<small>{help_text}</small>" if help_text else ""),
                unsafe_allow_html=True)

    # 지난번 파일을 그대로 쓸 수 있으면 먼저 보여준다.
    if has_remembered and not st.session_state.get(f"change_{key}"):
        col1, col2 = st.columns([5, 1])
        col1.success(f"{remembered_path.name}", icon="📄")
        col1.caption(str(remembered_path))
        if col2.button("다른 파일", key=f"btn_change_{key}", use_container_width=True):
            st.session_state[f"change_{key}"] = True
            st.rerun()
        return remembered_path

    uploaded = st.file_uploader(
        label,
        type=[e.lstrip(".") for e in extensions],
        key=f"up_{key}",
        label_visibility="collapsed",
    )
    if uploaded is not None:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        target = UPLOAD_DIR / uploaded.name
        target.write_bytes(uploaded.getbuffer())
        st.session_state.pop(f"change_{key}", None)
        return target

    with st.expander("파일 경로를 직접 적기"):
        text = st.text_input(
            "전체 경로", value=remembered, key=f"path_{key}", label_visibility="collapsed",
            placeholder=r"예: C:\Users\...\lawdata.xlsx",
        )
    if has_remembered and st.session_state.get(f"change_{key}"):
        if st.button("취소하고 지난번 파일 쓰기", key=f"btn_cancel_{key}"):
            st.session_state.pop(f"change_{key}", None)
            st.rerun()

    if not text:
        return None
    path = Path(text)
    if not path.exists():
        st.error(f"파일이 없습니다: {path}")
        return None
    st.session_state.pop(f"change_{key}", None)
    return path


def remember_path(key: str, path: Path) -> None:
    settings = load_settings()
    if settings.last_paths.get(key) != str(path):
        settings.last_paths[key] = str(path)
        settings.save()


def money(value) -> str:
    if value is None:
        return ""
    return f"{value:,.0f}"


def percent(value) -> str:
    """0.03 → '3%'"""
    from core.utils import percent_text

    return percent_text(value)


def red_none(frame, columns):
    """표에서 'none' 을 빨갛게 보여준다."""
    from core.master import NO_CODE_TEXT

    def style(value):
        return "color:#d32f2f; font-weight:700" if value == NO_CODE_TEXT else ""

    return frame.style.map(style, subset=list(columns))
