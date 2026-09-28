"""Airtable 스타일에서 가져온 디자인 토큰 (색/폰트). tkinter/ttk에 적용."""
import tkinter as tk
from tkinter import ttk

APP_BG = "#F7F8FC"
CARD_BG = "#FFFFFF"
BORDER = "#E1E4E8"
TEXT_PRIMARY = "#1D1F25"
TEXT_SECONDARY = "#6B7280"

ACCENT = "#2D7FF9"        # Airtable blue
ACCENT_HOVER = "#1966D6"
ACCENT_SOFT = "#E8F0FE"

SUCCESS = "#1F9D55"
SUCCESS_SOFT = "#E4F7EA"
WARNING = "#B8790A"
WARNING_SOFT = "#FFF3D6"
DANGER = "#D5265A"
DANGER_SOFT = "#FDE6ED"

TAG_COLORS = [
    ("#2D7FF9", "#E8F0FE"),  # blue
    ("#00A0A0", "#E1F7F5"),  # teal
    ("#8B46FF", "#F1E9FF"),  # purple
    ("#B8790A", "#FFF3D6"),  # orange
    ("#D5265A", "#FDE6ED"),  # pink
    ("#1F9D55", "#E4F7EA"),  # green
]

FONT_FAMILY = "맑은 고딕"
FONT_BASE = (FONT_FAMILY, 10)
FONT_BOLD = (FONT_FAMILY, 10, "bold")
FONT_HEADING = (FONT_FAMILY, 14, "bold")
FONT_SMALL = (FONT_FAMILY, 9)


def tag_color(seed: str):
    idx = sum(ord(c) for c in (seed or "")) % len(TAG_COLORS)
    return TAG_COLORS[idx]


def apply(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.configure(bg=APP_BG)

    style.configure("TFrame", background=APP_BG)
    style.configure("Card.TFrame", background=CARD_BG, relief="flat")
    style.configure("TLabel", background=APP_BG, foreground=TEXT_PRIMARY, font=FONT_BASE)
    style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT_PRIMARY, font=FONT_BASE)
    style.configure("Heading.TLabel", background=APP_BG, foreground=TEXT_PRIMARY, font=FONT_HEADING)
    style.configure("Secondary.TLabel", background=APP_BG, foreground=TEXT_SECONDARY, font=FONT_SMALL)
    style.configure("CardSecondary.TLabel", background=CARD_BG, foreground=TEXT_SECONDARY, font=FONT_SMALL)

    style.configure("TNotebook", background=APP_BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=APP_BG, foreground=TEXT_SECONDARY,
                    font=FONT_BASE, padding=(16, 8))
    style.map("TNotebook.Tab",
              background=[("selected", CARD_BG)],
              foreground=[("selected", ACCENT)])

    style.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF",
                    font=FONT_BOLD, padding=(14, 7), borderwidth=0)
    style.map("Accent.TButton", background=[("active", ACCENT_HOVER)])

    style.configure("Secondary.TButton", background=CARD_BG, foreground=TEXT_PRIMARY,
                    font=FONT_BASE, padding=(12, 6), borderwidth=1, relief="solid")
    style.map("Secondary.TButton", bordercolor=[("!disabled", BORDER)])

    style.configure("TEntry", fieldbackground="#FFFFFF", padding=6, font=FONT_BASE)
    style.configure("TCombobox", fieldbackground="#FFFFFF", padding=6, font=FONT_BASE)

    style.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF",
                    foreground=TEXT_PRIMARY, rowheight=26, font=FONT_BASE, borderwidth=0)
    style.configure("Treeview.Heading", background="#F0F2F6", foreground=TEXT_SECONDARY,
                    font=FONT_BOLD, relief="flat")
    style.map("Treeview", background=[("selected", ACCENT_SOFT)],
              foreground=[("selected", TEXT_PRIMARY)])


def card(parent, **kwargs) -> ttk.Frame:
    frame = ttk.Frame(parent, style="Card.TFrame", padding=16, **kwargs)
    return frame


MIN_COLUMN_WIDTH = 30


def setup_grid_columns(tree, columns, headings, widths, centered=frozenset(), on_sort=None) -> list:
    """헤더 텍스트/폭/정렬앵커 설정과 구분선 생성을 한 번에 처리한다.
    on_sort가 주어지면 헤더 클릭 시 on_sort(col)을 호출하도록 연결한다."""
    for col in columns:
        anchor = "center" if col in centered else "w"
        kwargs = {"text": headings[col], "anchor": anchor}
        if on_sort:
            kwargs["command"] = lambda c=col: on_sort(c)
        tree.heading(col, **kwargs)
        tree.column(col, width=widths[col], minwidth=min(MIN_COLUMN_WIDTH, widths[col]),
                    anchor=anchor, stretch=False)
    return add_column_dividers(tree, columns, widths)


def update_sort_headings(tree, columns, headings, sort_col, sort_reverse) -> None:
    """현재 정렬 컬럼에 ▲/▼ 표시를 붙여 헤더 텍스트를 갱신한다."""
    for col in columns:
        text = headings[col]
        if col == sort_col:
            text += " ▼" if sort_reverse else " ▲"
        tree.heading(col, text=text)


def add_column_dividers(tree, columns, widths) -> list:
    """컬럼 사이에 세로 구분선을 그린다. 컬럼 너비가 고정(resize 차단)이어야 정렬이 유지된다."""
    lines = []
    offset = 0
    for col in columns[:-1]:
        offset += widths[col]
        divider = tk.Frame(tree, bg=BORDER, width=1)
        divider.place(x=offset, y=0, relheight=1.0)
        lines.append(divider)
    return lines


def track_column_resize(tree, columns, dividers) -> None:
    """컬럼 폭 조절을 활성화한다.

    헤더 경계 드래그(ttk 기본 동작) 후 구분선을 실제 폭에 맞춰 다시 그리고,
    구분선 자체도 드래그 핸들로 동작시킨다. 구분선은 tree 위에 얹힌 별도 위젯이라
    선 위를 정확히 눌렀을 때는 ttk 헤더가 이벤트를 받지 못하기 때문이다.
    """
    def reposition(_event=None):
        offset = 0
        for divider, col in zip(dividers, columns[:-1]):
            offset += tree.column(col, "width")
            divider.place(x=offset, y=0, relheight=1.0)

    tree.bind("<B1-Motion>", reposition, add="+")
    tree.bind("<ButtonRelease-1>", reposition, add="+")

    for divider, col in zip(dividers, columns[:-1]):
        _bind_divider_drag(tree, divider, col, reposition)


def _bind_divider_drag(tree, divider, col, reposition) -> None:
    state = {"x": 0, "width": 0}

    def start(event):
        state["x"] = event.x_root
        state["width"] = tree.column(col, "width")

    def drag(event):
        width = max(MIN_COLUMN_WIDTH, state["width"] + event.x_root - state["x"])
        tree.column(col, width=width)
        reposition()

    divider.configure(cursor="sb_h_double_arrow")
    divider.bind("<Button-1>", start)
    divider.bind("<B1-Motion>", drag)


def autosize(win, min_w=0, min_h=0, pad=24) -> None:
    """실제 렌더링된 위젯 크기에 맞춰 창 크기를 정한다 (DPI/폰트 차이로 인한 잘림 방지)."""
    win.update_idletasks()
    w = max(min_w, win.winfo_reqwidth() + pad)
    h = max(min_h, win.winfo_reqheight() + pad)
    win.geometry(f"{w}x{h}")
    win.minsize(w, h)
