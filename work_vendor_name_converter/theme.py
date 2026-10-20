"""색상 팔레트 - "Ocean Depths" 톤 (Acrobat_ICCOAnr9CL.png 참고).

레이아웃/패딩/폰트/위젯 종류는 절대 건드리지 않고 배경·전경색만 입힌다.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

NAVY = "#1a2332"
NAVY_MUTED = "#5c6b78"
TEAL = "#2d8b8b"
TEAL_ACTIVE = "#256f6f"
SEAFOAM = "#a8dadc"
SEAFOAM_ACTIVE = "#8fc9cc"
CREAM = "#f1faee"
ROW_EVEN = "#ffffff"
ROW_ODD = "#dcecec"


def apply(root: tk.Tk):
    """색상만 적용한다 - padding/font/위젯 타입은 그대로 둔다."""
    root.configure(bg=CREAM)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(".", background=CREAM, foreground=NAVY)
    style.configure("TFrame", background=CREAM)
    style.configure("TLabel", background=CREAM, foreground=NAVY)
    style.configure("Muted.TLabel", background=CREAM, foreground=NAVY_MUTED)

    style.configure("TLabelframe", background=CREAM, bordercolor=TEAL)
    style.configure("TLabelframe.Label", background=CREAM, foreground=NAVY)

    style.configure("TRadiobutton", background=CREAM, foreground=NAVY)
    style.map("TRadiobutton", background=[("active", CREAM)])

    style.configure("TButton", background=SEAFOAM, foreground=NAVY)
    style.map("TButton", background=[("active", SEAFOAM_ACTIVE)])

    style.configure("Accent.TButton", background=TEAL, foreground="#ffffff")
    style.map("Accent.TButton", background=[("active", TEAL_ACTIVE)])

    style.configure("TEntry", fieldbackground="#ffffff", foreground=NAVY)
    style.configure("TCombobox", fieldbackground="#ffffff", foreground=NAVY)
    root.option_add("*TCombobox*Listbox.background", "#ffffff")
    root.option_add("*TCombobox*Listbox.foreground", NAVY)
    root.option_add("*TCombobox*Listbox.selectBackground", SEAFOAM)

    style.configure("Treeview", background=ROW_EVEN, fieldbackground=ROW_EVEN, foreground=NAVY,
                    bordercolor=TEAL, borderwidth=1, relief="solid")
    style.configure("Treeview.Heading", background=SEAFOAM, foreground=NAVY,
                    bordercolor=TEAL, borderwidth=1, relief="solid")
    style.map("Treeview.Heading", background=[("active", SEAFOAM_ACTIVE)])
    style.map("Treeview", background=[("selected", TEAL)], foreground=[("selected", "#ffffff")])

    style.configure("TNotebook", background=CREAM)
    style.configure("TNotebook.Tab", background=SEAFOAM, foreground=NAVY)
    style.map("TNotebook.Tab", background=[("selected", "#ffffff")])

    style.configure("Vertical.TScrollbar", background=SEAFOAM, troughcolor=CREAM, bordercolor=CREAM)


def style_toplevel(win: tk.Toplevel):
    win.configure(bg=CREAM)


def drop_box(parent, text: str = "") -> tk.Label:
    """드래그앤드롭 가능한 입력창처럼 보이는 라벨 (테두리 있는 흰 박스)."""
    return tk.Label(
        parent, text=text, bg="#ffffff", fg=NAVY_MUTED, anchor="w",
        relief="solid", bd=1, highlightthickness=0, padx=8, pady=6,
    )
