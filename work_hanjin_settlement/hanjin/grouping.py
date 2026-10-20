"""동일인 정리 창: 이름 칩을 대표 카드에 끌어다 놓아 묶고, 잘못 묶은 것은 다시 옮기거나 떼어낸다.

마스터 사본(Master.clone)에서 작업하고 [저장]을 눌러야 원본에 반영된다.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from PySide6.QtCore import QMimeData, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDrag
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QMenu, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from . import engine, theme
from .master import SAME, Master

MIME = "application/x-hanjin-name"
COLUMNS = 3


def won(v) -> str:
    return f"{int(v):,}"


def _repolish(w: QWidget, **props):
    for k, v in props.items():
        w.setProperty(k, v)
    w.style().unpolish(w)
    w.style().polish(w)


class Chip(QFrame):
    """끌 수 있는 이름 하나."""
    menu_requested = Signal(str, QPoint)

    def __init__(self, name: str, detail: str, is_rep: bool):
        super().__init__(objectName="chip")
        self.name = name
        self.setProperty("rep", "true" if is_rep else "false")
        self.setCursor(Qt.OpenHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)
        grip = QLabel("⠿", objectName="muted")
        lay.addWidget(grip)
        title = QLabel(name)
        if is_rep:
            title.setStyleSheet("font-weight: bold;")
        lay.addWidget(title)
        if is_rep:
            lay.addWidget(QLabel("대표", objectName="repTag"))
        lay.addStretch(1)
        lay.addWidget(QLabel(detail, objectName="muted"))
        self.setToolTip("다른 카드에 끌어다 놓으면 그 대표명으로 묶입니다. 우클릭: 대표명 지정·따로 떼기"
                        + ("\n대표 칩을 옮기면 이 묶음 전체가 함께 옮겨갑니다." if is_rep else ""))
        self._press: QPoint | None = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._press is None or (e.position().toPoint() - self._press).manhattanLength() \
                < QApplication.startDragDistance():
            return
        self._press = None
        mime = QMimeData()
        mime.setData(MIME, self.name.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(e.position().toPoint())
        drag.exec(Qt.MoveAction)

    def contextMenuEvent(self, e):
        self.menu_requested.emit(self.name, e.globalPos())


class DropTarget(QFrame):
    """칩을 받는 곳(대표 카드 또는 '따로 떼기' 칸)."""
    dropped = Signal(str, str)   # (끌어온 이름, 이 칸의 key)

    def __init__(self, key: str, object_name: str):
        super().__init__(objectName=object_name)
        self.key = key
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(MIME):
            e.acceptProposedAction()
            _repolish(self, hover="true")

    def dragLeaveEvent(self, e):
        _repolish(self, hover="false")

    def dropEvent(self, e):
        _repolish(self, hover="false")
        name = bytes(e.mimeData().data(MIME)).decode("utf-8")
        e.acceptProposedAction()
        # 드롭 처리 중에 위젯을 다시 그리면 안 되므로 이벤트가 끝난 뒤 처리
        QTimer.singleShot(0, lambda: self.dropped.emit(name, self.key))


class GroupingDialog(QDialog):
    def __init__(self, parent, master: Master, df=None, month=None, include_out=True):
        super().__init__(parent)
        self.setWindowTitle("동일인 정리")
        self.resize(1000, 720)
        self.work = master.clone()
        self.df, self.month, self.include_out = df, month, include_out
        self.changes: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.addWidget(QLabel("동일인 정리", objectName="title"))
        root.addWidget(QLabel(
            "같은 사람이면 이름을 끌어서 대표로 쓸 카드에 놓으세요. 잘못 묶었으면 다른 카드로 다시 옮기거나 "
            "'따로 떼기' 칸에 놓으면 됩니다. 칩을 우클릭하면 대표명을 바꿀 수 있습니다. [저장]을 눌러야 반영됩니다.",
            objectName="subtitle", wordWrap=True))

        self.tabs = QTabWidget()
        self.board = QWidget(objectName="root")
        self.board_lay = QVBoxLayout(self.board)
        self.board_lay.setContentsMargins(0, 8, 0, 0)
        self.tabs.addTab(self.board, "묶기")
        self.judgments = QTableWidget(0, 5)
        self.judgments.setHorizontalHeaderLabels(["원본이름", "대표명/상대", "판정", "판정일", ""])
        self.judgments.verticalHeader().hide()
        self.judgments.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.judgments.setSelectionMode(QAbstractItemView.NoSelection)
        self.judgments.setMouseTracking(True)
        self.judgments.cellClicked.connect(self._judgment_clicked)
        hh = self.judgments.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        jw = QWidget(objectName="root")
        jl = QVBoxLayout(jw)
        jl.setContentsMargins(0, 8, 0, 0)
        jl.addWidget(QLabel("지금까지 저장한 판정입니다. '판정 취소'를 누르면 그 판정이 지워지고, 해당 이름은 다시 따로 계산되거나 후보로 다시 올라옵니다.",
                            objectName="muted", wordWrap=True))
        jl.addWidget(self.judgments, 1)
        self.tabs.addTab(jw, "저장된 판정")
        root.addWidget(self.tabs, 1)

        self.status = QLabel("", objectName="muted")
        root.addWidget(self.status)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        save = QPushButton("저장", objectName="primary")
        save.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(save)
        root.addLayout(btns)
        self.rebuild()

    # ── 계산 ──
    def _settle(self):
        if self.df is None:
            return None
        return engine.settle(self.df, self.work.alias_map(), self.work.different_pairs(),
                             self.month, self.include_out)

    def _name_stats(self, s) -> dict[str, tuple[str, int, int]]:
        """원본이름별 (대표 전화, 건수, 금액)."""
        phones, count, amount = defaultdict(Counter), Counter(), Counter()
        for x in s.shipments:
            if x.phone:
                phones[x.name][x.phone] += 1
            count[x.name] += 1
            amount[x.name] += int(x.amount)
        return {n: (phones[n].most_common(1)[0][0] if phones[n] else "", count[n], amount[n]) for n in count}

    # ── 화면 다시 그리기 ──
    def rebuild(self):
        while self.board_lay.count():
            item = self.board_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._fill_judgments()
        s = self.settlement = self._settle()
        if s is None:
            self.board_lay.addWidget(QLabel("불러온 자료가 없습니다. '저장된 판정' 탭에서 판정을 취소할 수 있습니다.",
                                            objectName="muted"))
            self.board_lay.addStretch(1)
            self.tabs.setCurrentIndex(1)
            return
        self.stats = self._name_stats(s)

        # 확인할 후보
        cand_names = []
        if s.candidates:
            box = QFrame(objectName="candBox")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(12, 8, 12, 8)
            bl.setSpacing(4)
            bl.addWidget(QLabel(f"확인할 후보 {len(s.candidates)}건 — 같은 사람이면 끌어서 묶고, 아니면 [다른 사람]",
                                objectName="sectionTitle"))
            for c in s.candidates:
                row = QHBoxLayout()
                row.addWidget(QLabel(f"{c.base}  ↔  {c.other}   ·  {c.reason} ({c.phone})"))
                row.addStretch(1)
                diff = QPushButton("다른 사람")
                diff.clicked.connect(lambda _=False, c=c: self._different(c))
                row.addWidget(diff)
                bl.addLayout(row)
                cand_names += [c.base, c.other]
            self.board_lay.addWidget(box)

        split = DropTarget("", "splitZone")
        sl = QHBoxLayout(split)
        sl.setContentsMargins(12, 10, 12, 10)
        sl.addWidget(QLabel("↥  여기에 놓으면 묶음에서 따로 떼어냅니다", objectName="muted"), 0, Qt.AlignCenter)
        split.dropped.connect(self._drop_split)
        self.board_lay.addWidget(split)

        order = list(dict.fromkeys(n for n in cand_names if n in s.groups))
        order += [n for n in sorted(s.groups) if n not in order]
        grid_w = QWidget(objectName="root")
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        for i, name in enumerate(order):
            grid.addWidget(self._card(s.groups[name], name in cand_names), i // COLUMNS, i % COLUMNS)
        for c in range(COLUMNS):
            grid.setColumnStretch(c, 1)
        wrap = QWidget(objectName="root")
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(grid_w)
        wl.addStretch(1)
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(wrap)
        self.board_lay.addWidget(scroll, 1)

    def _card(self, g: engine.Group, is_candidate: bool) -> DropTarget:
        card = DropTarget(g.name, "gcard")
        card.setProperty("candidate", "true" if is_candidate else "false")
        card.dropped.connect(self._drop_on_card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(4)
        title = QLabel(g.name)
        title.setStyleSheet("font-size: 12pt; font-weight: bold;")
        lay.addWidget(title)
        lay.addWidget(QLabel(f"{g.total_count}건 · {won(g.total_amount)}원", objectName="muted"))
        names = [g.name] + sorted(n for n in g.raw_names if n != g.name)
        for n in names:
            phone, cnt, amt = self.stats.get(n, ("", 0, 0))
            chip = Chip(n, f"{phone}  {cnt}건" if cnt else "이번 달 자료 없음", is_rep=(n == g.name))
            chip.menu_requested.connect(self._chip_menu)
            lay.addWidget(chip)
        lay.addStretch(1)
        return card

    def _fill_judgments(self):
        """마지막 칸의 '판정 취소'를 클릭하면 취소(셀 위젯을 쓰지 않아 다시 그려도 겹치지 않는다)."""
        self._judgment_rows = sorted(self.work.aliases, key=lambda a: (a["판정"], a["대표명"], a["원본이름"]))
        self.judgments.setRowCount(len(self._judgment_rows))
        for r, a in enumerate(self._judgment_rows):
            for c, v in enumerate((a["원본이름"], a["대표명"],
                                   "같은 사람" if a["판정"] == SAME else "다른 사람", a["판정일"], "판정 취소")):
                self.judgments.setItem(r, c, QTableWidgetItem(v))
            undo = self.judgments.item(r, 4)
            undo.setForeground(QColor(theme.ERROR))
            undo.setTextAlignment(Qt.AlignCenter)
            undo.setToolTip("클릭하면 이 판정을 지웁니다")

    def _judgment_clicked(self, row: int, col: int):
        if col == 4 and row < len(self._judgment_rows):
            self._undo(self._judgment_rows[row])

    # ── 동작 ──
    def _note(self, msg: str):
        self.changes.append(msg)
        self.status.setText("✓ " + msg)

    def _root(self, name: str) -> str:
        return engine.resolve(name, self.work.alias_map())

    def _drop_on_card(self, name: str, rep: str):
        if self._root(name) == rep:
            return
        members = [a["원본이름"] for a in self.work.aliases if a["판정"] == SAME and a["대표명"] == name]
        phone = self.stats.get(name, ("",))[0] if hasattr(self, "stats") else ""
        self.work.assign(name, rep, phone)
        self._note(f"{name}" + (f" 묶음({len(members) + 1}명)" if members else "") + f" → '{rep}'로 묶음")
        QTimer.singleShot(0, self.rebuild)

    def _drop_split(self, name: str, _key: str = ""):
        if self._root(name) == name:
            members = [a for a in self.work.aliases if a["판정"] == SAME and a["대표명"] == name]
            self.status.setText(f"'{name}'은(는) 대표명이라 떼어낼 수 없습니다. "
                                "다른 이름을 대표로 지정한 뒤 떼어내세요." if members else f"'{name}'은(는) 이미 따로입니다.")
            return
        self.work.split(name)
        self._note(f"{name} → 따로 떼어냄")
        QTimer.singleShot(0, self.rebuild)

    def _chip_menu(self, name: str, pos: QPoint):
        menu = QMenu(self)
        is_root = self._root(name) == name
        rep_act = menu.addAction("대표명으로 지정")
        split_act = menu.addAction("따로 떼기")
        rep_act.setEnabled(not is_root)
        split_act.setEnabled(not is_root)
        act = menu.exec(pos)
        if act is rep_act:
            self.work.make_rep(name)
            self._note(f"대표명을 '{name}'(으)로 변경")
            QTimer.singleShot(0, self.rebuild)
        elif act is split_act:
            self._drop_split(name)

    def _different(self, c: engine.Candidate):
        self.work.record_different(c.other, c.base, c.phone)
        self._note(f"{c.base} / {c.other} → 다른 사람")
        QTimer.singleShot(0, self.rebuild)

    def _undo(self, a: dict):
        self.work.remove_alias(a)
        what = "같은 사람" if a["판정"] == SAME else "다른 사람"
        self._note(f"판정 취소: {a['원본이름']} / {a['대표명']} ({what})")
        QTimer.singleShot(0, self.rebuild)
