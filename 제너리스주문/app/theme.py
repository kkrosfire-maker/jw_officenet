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


def block_column_resize(tree, event) -> str | None:
    """구분선이 어긋나지 않도록 헤더 드래그로 컬럼 폭을 바꾸는 것을 막는다."""
    if tree.identify_region(event.x, event.y) == "separator":
        return "break"
    return None


def autosize(win, min_w=0, min_h=0, pad=24) -> None:
    """실제 렌더링된 위젯 크기에 맞춰 창 크기를 정한다 (DPI/폰트 차이로 인한 잘림 방지)."""
    win.update_idletasks()
    w = max(min_w, win.winfo_reqwidth() + pad)
    h = max(min_h, win.winfo_reqheight() + pad)
    win.geometry(f"{w}x{h}")
    win.minsize(w, h)
