"""Notion 풍 밝은 테마: 흰 바탕, 따뜻한 회색 면·선, 파란 포인트 하나."""

BG = "#FFFFFF"
SURFACE = "#F7F6F3"
TEXT = "#37352F"
MUTED = "#787774"
BORDER = "#E9E9E7"
HOVER = "#EFEFED"
ACCENT = "#2383E2"
ACCENT_HOVER = "#0B6BCB"
NEW_BG = "#E7F3F8"
WARN_BG = "#FBF3DB"
WARN_TEXT = "#7A5A0B"
ERROR = "#E03E3E"

FONT_FAMILY = "맑은 고딕"

QSS = f"""
* {{ font-family: '{FONT_FAMILY}'; font-size: 10pt; color: {TEXT}; }}
QMainWindow, QDialog, QWidget#root {{ background: {BG}; }}
QLabel#title {{ font-size: 18pt; font-weight: bold; }}
QLabel#subtitle {{ color: {MUTED}; }}
QLabel#sectionTitle {{ font-weight: bold; color: {MUTED}; font-size: 9pt; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#stats {{ font-size: 11pt; font-weight: bold; }}
QLabel#warn {{ background: {WARN_BG}; color: {WARN_TEXT}; border-radius: 4px; padding: 8px 10px; }}
QFrame#card {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; }}
QFrame#drop {{ background: {SURFACE}; border: 1px dashed #CFCDC9; border-radius: 6px; }}
QFrame#drop[active="true"] {{ background: {NEW_BG}; border: 1px dashed {ACCENT}; }}
QLineEdit, QComboBox {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 4px; padding: 5px 8px;
    selection-background-color: {NEW_BG}; selection-color: {TEXT};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background: {BG}; border: 1px solid {BORDER}; selection-background-color: {HOVER}; }}
QPushButton {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 4px; padding: 6px 14px;
}}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:disabled {{ color: #B4B4B0; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: 1px solid {ACCENT}; font-weight: bold; padding: 8px 18px; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:disabled {{ background: #A9CDF2; border-color: #A9CDF2; color: white; }}
QPushButton#attention {{ background: {WARN_BG}; color: {WARN_TEXT}; border: 1px solid #F0DFA8; font-weight: bold; }}
QPushButton#link {{ border: none; color: {MUTED}; padding: 4px 6px; }}
QPushButton#link:hover {{ color: {TEXT}; background: {HOVER}; }}
QCheckBox, QRadioButton {{ spacing: 6px; }}
QTableWidget {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 4px; gridline-color: {BORDER};
    selection-background-color: {HOVER}; selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {SURFACE}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER}; padding: 6px; font-weight: bold;
}}
QPlainTextEdit {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 4px; font-family: 'Consolas', '{FONT_FAMILY}'; font-size: 9pt; }}
QFrame#gcard {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; }}
QFrame#gcard[candidate="true"] {{ border: 2px solid #F0C85A; }}
QFrame#gcard[hover="true"] {{ background: {NEW_BG}; border: 2px solid {ACCENT}; }}
QFrame#chip {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 4px; }}
QFrame#chip:hover {{ background: {HOVER}; border-color: #CFCDC9; }}
QFrame#chip[rep="true"] {{ background: {BG}; }}
QLabel#repTag {{ background: {NEW_BG}; color: {ACCENT_HOVER}; border-radius: 3px; padding: 0 5px; font-size: 8pt; font-weight: bold; }}
QFrame#splitZone {{ background: {SURFACE}; border: 1px dashed #CFCDC9; border-radius: 6px; }}
QFrame#splitZone[hover="true"] {{ background: #FDEBEC; border: 1px dashed {ERROR}; }}
QFrame#candBox {{ background: {WARN_BG}; border-radius: 6px; }}
QFrame#candBox QLabel {{ color: {WARN_TEXT}; }}
QTabWidget::pane {{ border: none; border-top: 1px solid {BORDER}; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 6px 14px; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {TEXT}; font-weight: bold; }}
QMenu {{ background: {BG}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 5px 18px; border-radius: 3px; }}
QMenu::item:selected {{ background: {HOVER}; }}
QMenu::item:disabled {{ color: #B4B4B0; }}
QScrollArea {{ border: none; background: {BG}; }}
QSplitter::handle {{ background: {BG}; }}
"""
