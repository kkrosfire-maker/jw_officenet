"""메인 창: ① 로그인 ② 정산월 ③ 파일 입력 ④ 미리보기 ⑤ 실행 ⑥ 로그."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QRadioButton, QScrollArea, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import engine, paths, theme
from .downloader import Cancelled, HanjinDownloader, LoginError, NoDataError, StepError
from .engine import KIND_RETURN, KIND_SEND, KIND_UNKNOWN, DataError
from .grouping import GroupingDialog
from .master import Master, MasterLockedError
from .report import OutputLockedError, default_filename, write_report
from .settings import Settings

log = logging.getLogger("hanjin")
FILE_EXTS = (".xlsx", ".xls", ".csv")


def won(v) -> str:
    return f"{int(v):,}" if Decimal(v) == Decimal(v).to_integral_value() else f"{float(v):,.2f}"


def card(title: str) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame(objectName="card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 10, 14, 12)
    lay.setSpacing(8)
    lay.addWidget(QLabel(title, objectName="sectionTitle"))
    return f, lay


# ── 자동 다운로드 스레드 ─────────────────────────────────────

class DownloadWorker(QThread):
    log = Signal(str)
    done = Signal(object)
    failed = Signal(str, str)   # (종류, 메시지)

    def __init__(self, downloader_args: dict):
        super().__init__()
        self.downloader = HanjinDownloader(log=self.log.emit, **downloader_args)

    def run(self):
        try:
            self.done.emit(self.downloader.run())
        except LoginError as e:
            self.failed.emit("login", str(e))
        except NoDataError as e:
            self.failed.emit("nodata", str(e))
        except Cancelled:
            self.failed.emit("cancel", "자동 다운로드를 중지했습니다.")
        except StepError as e:
            self.failed.emit("error", f"자동 다운로드가 {e}\n화면 캡처를 logs 폴더에 남겼습니다.\n"
                                      "한진 사이트에서 직접 받은 파일을 [파일 선택]으로 지정하거나 끌어다 놓으세요.")
        except Exception as e:
            log.exception("download")
            self.failed.emit("error", f"자동 다운로드 실패: {e}\n직접 받은 파일을 [파일 선택]으로 지정하세요.")


# ── 드래그앤드롭 영역 ────────────────────────────────────────

class DropArea(QFrame):
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__(objectName="drop")
        self.setAcceptDrops(True)
        self.setMinimumHeight(64)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        self.label = QLabel("여기로 운임정산 세부내역 파일을 끌어다 놓으세요  ·  .xlsx .xls .csv, 여러 개 가능",
                            objectName="muted")
        self.label.setWordWrap(True)
        self.pick = QPushButton("파일 선택")
        lay.addWidget(self.label, 1)
        lay.addWidget(self.pick)

    def _set_active(self, on: bool):
        self.setProperty("active", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, e):
        self._set_active(False)

    def dropEvent(self, e):
        self._set_active(False)
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if files:
            self.files_dropped.emit(files)


# ── 메인 창 ─────────────────────────────────────────────────

COL_NAME, COL_ROOM, COL_PHONE, COL_SEND_N, COL_SEND_A, COL_RET_N, COL_RET_A, COL_TOTAL, COL_NOTE = range(9)
HEADERS = ["송하인명", "호실", "전화번호", "발송", "발송 금액", "착신(반품)", "착신 금액", "합계 금액", "비고"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        paths.ensure_dirs()
        self.settings = Settings(paths.CONFIG_FILE)
        self.master: Master | None = None
        self.df = None
        self.files: list[str] = []
        self.dup_removed = 0
        self.settlement: engine.Settlement | None = None
        self.worker: DownloadWorker | None = None
        self.unconfirmed: list[str] = []
        self._filling = False

        self.setWindowTitle("한진택배정산")
        self.setMinimumSize(1024, 720)
        self.resize(1180, 860)
        self._build()
        self._load_master()
        self.log("프로그램 시작. 자동 다운로드 또는 파일 입력으로 자료를 불러오세요.")

    # ── 화면 구성 ──
    def _build(self):
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        root.setAcceptDrops(True)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 16, 22, 14)
        outer.setSpacing(10)

        head = QHBoxLayout()
        head.addWidget(QLabel("한진택배정산", objectName="title"))
        sub = QLabel("운임정산 세부내역 → 송하인별 발송·착신 정산 엑셀", objectName="subtitle")
        head.addWidget(sub, 0, Qt.AlignBottom)
        head.addStretch(1)
        open_master = QPushButton("송하인마스터 열기", objectName="link")
        open_master.clicked.connect(lambda: self._open_path(paths.MASTER_FILE))
        open_out = QPushButton("결과 폴더", objectName="link")
        open_out.clicked.connect(lambda: self._open_path(paths.OUTPUT_DIR))
        head.addWidget(open_master)
        head.addWidget(open_out)
        outer.addLayout(head)

        # ① 로그인 + ② 정산월
        top = QHBoxLayout()
        top.setSpacing(10)
        login, ll = card("① 로그인 (focus.hanjin.com)")
        g = QGridLayout()
        g.setHorizontalSpacing(8)
        self.id_edit = QLineEdit(self.settings.user_id)
        self.pw_edit = QLineEdit(self.settings.password)
        self.pw_edit.setEchoMode(QLineEdit.Password)
        self.pw_edit.setPlaceholderText("비밀번호")
        show = QPushButton("보기", checkable=True)
        show.setFixedWidth(56)
        show.toggled.connect(lambda on: (self.pw_edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password),
                                         show.setText("숨기기" if on else "보기")))
        self.remember = QCheckBox("ID/PW 기억하기")
        self.remember.setChecked(self.settings.remember)
        self.remember.toggled.connect(self._remember_toggled)
        g.addWidget(QLabel("ID"), 0, 0)
        g.addWidget(self.id_edit, 0, 1)
        g.addWidget(QLabel("PW"), 0, 2)
        g.addWidget(self.pw_edit, 0, 3)
        g.addWidget(show, 0, 4)
        g.addWidget(self.remember, 0, 5)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)
        ll.addLayout(g)
        top.addWidget(login, 3)

        month, ml = card("② 정산월")
        h = QHBoxLayout()
        prev = date.today().replace(day=1)
        prev = date(prev.year - (prev.month == 1), 12 if prev.month == 1 else prev.month - 1, 1)
        self.year_box = QComboBox()
        for y in range(prev.year - 3, prev.year + 2):
            self.year_box.addItem(f"{y}년", y)
        self.year_box.setCurrentIndex(self.year_box.findData(prev.year))
        self.month_box = QComboBox()
        for m in range(1, 13):
            self.month_box.addItem(f"{m}월", m)
        self.month_box.setCurrentIndex(prev.month - 1)
        self.year_box.currentIndexChanged.connect(self._month_changed)
        self.month_box.currentIndexChanged.connect(self._month_changed)
        self.download_btn = QPushButton("자동 다운로드", objectName="primary")
        self.download_btn.clicked.connect(self._start_download)
        h.addWidget(self.year_box)
        h.addWidget(self.month_box)
        h.addStretch(1)
        h.addWidget(self.download_btn)
        ml.addLayout(h)
        top.addWidget(month, 2)
        outer.addLayout(top)

        # ③ 파일 입력
        files, fl = card("③ 파일 입력")
        self.drop = DropArea()
        self.drop.files_dropped.connect(self.load_files)
        self.drop.pick.clicked.connect(self._pick_files)
        fl.addWidget(self.drop)
        self.file_label = QLabel("불러온 파일 없음", objectName="muted")
        self.file_label.setWordWrap(True)
        fl.addWidget(self.file_label)
        outer.addWidget(files)

        # ④ 미리보기 + ⑥ 로그
        preview, pl = card("④ 미리보기")
        self.stats = QLabel("—", objectName="stats")
        pl.addWidget(self.stats)
        self.warn = QLabel(objectName="warn", wordWrap=True)
        self.warn.hide()
        pl.addWidget(self.warn)
        self.include_out = QCheckBox()
        self.include_out.setChecked(True)
        self.include_out.hide()
        self.include_out.toggled.connect(self.refresh)
        pl.addWidget(self.include_out)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
                                   | QAbstractItemView.AnyKeyPressed)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_NOTE, QHeaderView.Stretch)
        self.table.itemChanged.connect(self._cell_edited)
        pl.addWidget(self.table, 1)
        hint = QLabel("호실·전화번호 칸을 더블클릭해 입력하면 송하인 마스터에 바로 저장됩니다. 파란 행은 이번에 처음 나온 송하인입니다.",
                      objectName="muted")
        pl.addWidget(hint)

        logbox, lgl = card("⑥ 로그")
        self.log_view = QPlainTextEdit(readOnly=True)
        lgl.addWidget(self.log_view)

        split = QSplitter(Qt.Vertical)
        split.addWidget(preview)
        split.addWidget(logbox)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 1)
        split.setSizes([520, 120])
        split.setChildrenCollapsible(False)
        outer.addWidget(split, 1)

        # ⑤ 실행
        run = QHBoxLayout()
        self.cand_btn = QPushButton("동일인 정리")
        self.cand_btn.setToolTip("이름을 끌어다 놓아 같은 사람을 묶거나, 잘못 묶은 것을 다시 지정합니다.")
        self.cand_btn.clicked.connect(self._review_candidates)
        self.make_btn = QPushButton("정산 엑셀 생성", objectName="primary")
        self.make_btn.clicked.connect(self._generate)
        self.make_btn.setEnabled(False)
        run.addStretch(1)
        run.addWidget(self.cand_btn)
        run.addWidget(self.make_btn)
        outer.addLayout(run)

    # ── 창 전체 드래그앤드롭 ──
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if files:
            self.load_files(files)

    # ── 로그 ──
    def log(self, msg: str):
        self.log_view.appendPlainText(f"{datetime.now():%H:%M:%S}  {msg}")
        log.info(msg)

    def error(self, msg: str, title="확인 필요"):
        self.log("⚠ " + msg)
        QMessageBox.warning(self, title, msg)

    # ── 설정 ──
    def _remember_toggled(self, on: bool):
        self._save_settings()
        if not on:
            self.log("저장된 ID/PW를 지웠습니다.")

    def _save_settings(self):
        self.settings.remember = self.remember.isChecked()
        self.settings.user_id = self.id_edit.text().strip()
        self.settings.password = self.pw_edit.text()
        self.settings.save()

    def closeEvent(self, e):
        self._save_settings()
        if self.worker and self.worker.isRunning():
            self.worker.downloader.cancel()
            self.worker.wait(5000)
        super().closeEvent(e)

    @property
    def year_month(self) -> tuple[int, int]:
        return self.year_box.currentData(), self.month_box.currentData()

    # ── 마스터 ──
    def _load_master(self) -> bool:
        try:
            self.master = Master(paths.MASTER_FILE, paths.BACKUP_DIR)
            return True
        except MasterLockedError as e:
            self.error(str(e))
            if self.master is None:
                self.master = Master.__new__(Master)
                self.master.path, self.master.backup_dir = paths.MASTER_FILE, paths.BACKUP_DIR
                self.master.senders, self.master.aliases = {}, []
            return False

    def _save_master(self) -> bool:
        try:
            self.master.save()
            return True
        except MasterLockedError as e:
            self.error(str(e))
            return False

    # ── 파일 입력 ──
    def _pick_files(self):
        start = str(paths.DOWNLOAD_DIR)
        files, _ = QFileDialog.getOpenFileNames(self, "운임정산 세부내역 파일 선택", start,
                                                "엑셀/CSV (*.xlsx *.xls *.csv)")
        if files:
            self.load_files(files)

    def load_files(self, files: list[str]) -> bool:
        files = [f for f in files if Path(f).suffix.lower() in FILE_EXTS]
        if not files:
            self.error("지원하지 않는 형식입니다. .xlsx, .xls, .csv 파일을 넣어주세요.")
            return False
        try:
            df, dup = engine.load_files(files)
        except DataError as e:
            self.error(str(e), "파일 오류")
            return False
        self._load_master()  # 엑셀에서 직접 고친 내용 반영
        self.df, self.files, self.dup_removed = df, files, dup
        self.unconfirmed = []
        names = ", ".join(Path(f).name for f in files)
        self.file_label.setText(f"불러온 파일: {names}")
        self.log(f"파일 {len(files)}개 불러옴: {names} ({len(df)}건" + (f", 중복 {dup}건 제거)" if dup else ")"))

        # 고른 정산월에 해당하는 자료가 하나도 없으면 자료의 달로 맞춘다
        y, m = self.year_month
        if engine.out_of_month_count(df, y, m) == len(df):
            ym = df["출고일"].str[:7].value_counts().idxmax()
            yy, mm = int(ym[:4]), int(ym[5:7])
            if self.year_box.findData(yy) >= 0:
                self.log(f"정산월을 자료 기준 {yy}년 {mm}월로 바꿨습니다.")
                self._filling = True
                self.year_box.setCurrentIndex(self.year_box.findData(yy))
                self.month_box.setCurrentIndex(mm - 1)
                self._filling = False
        self.include_out.setChecked(True)
        self.refresh()
        return self.settlement is not None

    def _month_changed(self):
        if not self._filling and self.df is not None:
            self.refresh()

    # ── 미리보기 ──
    def refresh(self):
        if self.df is None:
            return
        y, m = self.year_month
        try:
            s = engine.settle(self.df, self.master.alias_map(), self.master.different_pairs(),
                              (y, m), self.include_out.isChecked())
        except DataError as e:
            self.error(str(e), "자료 오류")
            self.settlement = None
            self.make_btn.setEnabled(False)
            return
        self.settlement = s

        out_n = engine.out_of_month_count(self.df, y, m)
        self.include_out.setVisible(out_n > 0)
        self.include_out.setText(f"출고일이 {y}년 {m}월이 아닌 {out_n}건도 정산에 포함")

        p0, p1 = engine.data_period(self.df)
        new = [g.name for g in s.sorted_groups() if g.name not in self.master.senders]
        self.stats.setText(f"총 {s.total_count:,}건  ·  {won(s.total_amount)}원  ·  기간 {p0} ~ {p1}  ·  "
                           f"송하인 {len(s.groups)}명 (신규 {len(new)}명)")

        warns = []
        if self.unconfirmed:
            warns.append(f"아직 확정 전입니다: 인보이스 {', '.join(self.unconfirmed)} (확정=N). 금액이 바뀔 수 있습니다.")
        if out_n:
            warns.append(f"출고일이 정산월({y}-{m:02d})이 아닌 건이 {out_n}건 있습니다.")
        for n in s.multi_phone_names():
            warns.append(f"번호 2개: '{n}'의 전화번호가 여러 개입니다 ({', '.join(s.groups[n].phones)}). 같은 사람으로 계산했습니다.")
        unk = s.unknown_terms()
        if unk:
            amt = sum((x.amount for x in s.shipments if x.kind == KIND_UNKNOWN), Decimal(0))
            terms = ", ".join(f"'{k or '빈칸'}' {v}건" for k, v in unk.items())
            warns.append(f"미분류: 지불조건이 발신·착신이 아닌 건 {terms} (금액 {won(amt)}원) → '미분류' 행으로 따로 표시됩니다.")
        if s.candidates:
            warns.append(f"동일인 후보 {len(s.candidates)}건이 판정을 기다립니다. 승인 전에는 별도 송하인으로 계산합니다.")
        self.warn.setText("\n".join("• " + w for w in warns))
        self.warn.setVisible(bool(warns))

        self.cand_btn.setText(f"동일인 정리 (후보 {len(s.candidates)}건)" if s.candidates else "동일인 정리")
        self.cand_btn.setObjectName("attention" if s.candidates else "")
        self.cand_btn.style().unpolish(self.cand_btn)
        self.cand_btn.style().polish(self.cand_btn)
        self.make_btn.setEnabled(s.total_count > 0)
        self._fill_table(s, set(new))

    def _fill_table(self, s: engine.Settlement, new: set[str]):
        self._filling = True
        self.table.setRowCount(0)
        groups = s.sorted_groups()
        self.table.setRowCount(len(groups))
        new_brush = QBrush(QColor(theme.NEW_BG))
        muted = QBrush(QColor(theme.MUTED))
        for r, g in enumerate(groups):
            info = self.master.senders.get(g.name, {})
            notes = []
            if g.name in new:
                notes.append("신규")
            if len(g.phones) > 1:
                notes.append("번호 2개")
            if len(g.raw_names) > 1 or g.raw_names != {g.name}:
                notes.append("묶음: " + ", ".join(sorted(g.raw_names)))
            if g.count[KIND_UNKNOWN]:
                notes.append(f"미분류 {g.count[KIND_UNKNOWN]}건 {won(g.amount[KIND_UNKNOWN])}원")
            vals = [
                g.name, info.get("호실", ""), info.get("전화번호", "") or g.main_phone,
                g.count[KIND_SEND] or "", won(g.amount[KIND_SEND]) if g.count[KIND_SEND] else "",
                g.count[KIND_RETURN] or "", won(g.amount[KIND_RETURN]) if g.count[KIND_RETURN] else "",
                won(g.total_amount), " · ".join(notes),
            ]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if c not in (COL_ROOM, COL_PHONE):
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if c in (COL_SEND_N, COL_SEND_A, COL_RET_N, COL_RET_A, COL_TOTAL):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if c == COL_PHONE and not info.get("전화번호"):
                    it.setForeground(muted)
                    it.setToolTip("자료의 마스킹 번호입니다. 전체 번호를 입력하면 정산 엑셀에 그 번호가 들어갑니다.")
                if g.name in new:
                    it.setBackground(new_brush)
                self.table.setItem(r, c, it)
        self.table.setRowCount(len(groups) + 1)
        total = [("합계", COL_NAME), (str(sum(g.count[KIND_SEND] for g in groups)), COL_SEND_N),
                 (won(sum((g.amount[KIND_SEND] for g in groups), Decimal(0))), COL_SEND_A),
                 (str(sum(g.count[KIND_RETURN] for g in groups)), COL_RET_N),
                 (won(sum((g.amount[KIND_RETURN] for g in groups), Decimal(0))), COL_RET_A),
                 (won(s.total_amount), COL_TOTAL)]
        bold = QFont()
        bold.setBold(True)
        for c in range(len(HEADERS)):
            it = QTableWidgetItem("")
            it.setFlags(Qt.ItemIsEnabled)
            it.setBackground(QBrush(QColor(theme.SURFACE)))
            self.table.setItem(len(groups), c, it)
        for text, c in total:
            it = self.table.item(len(groups), c)
            it.setText(text)
            it.setFont(bold)
            if c != COL_NAME:
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._filling = False

    def _cell_edited(self, item: QTableWidgetItem):
        if self._filling or item.column() not in (COL_ROOM, COL_PHONE) or not self.settlement:
            return
        groups = self.settlement.sorted_groups()
        if item.row() >= len(groups):
            return
        g = groups[item.row()]
        col = "호실" if item.column() == COL_ROOM else "전화번호"
        value = item.text().strip()
        old = self.master.senders.get(g.name, {}).get(col, "")
        if col == "전화번호" and not old and value == g.main_phone:
            return  # 마스킹 번호를 그대로 둔 경우
        if value == old:
            return
        self.master.set_sender_field(g.name, col, value)
        if self._save_master():
            self.log(f"송하인 마스터 저장: {g.name} {col} = {value or '(비움)'}")
        else:
            self.master.set_sender_field(g.name, col, old)
        self.refresh()

    # ── 동일인 승인 ──
    def _review_candidates(self) -> bool:
        """동일인 정리 창. 판정을 저장했으면 True."""
        dlg = GroupingDialog(self, self.master, self.df, self.year_month, self.include_out.isChecked())
        if dlg.exec() != QDialog.Accepted or not dlg.changes:
            return False
        backup = (self.master.aliases, self.master.senders)
        self.master.aliases, self.master.senders = dlg.work.aliases, dlg.work.senders
        if not self._save_master():
            self.master.aliases, self.master.senders = backup  # 저장 못 한 판정은 버린다
            return False
        for c in dlg.changes:
            self.log("동일인 정리: " + c)
        self.refresh()
        return True

    # ── 정산 엑셀 생성 ──
    def _generate(self):
        if not self.settlement:
            return
        if self.settlement.candidates:
            self._review_candidates()
            if self.settlement and self.settlement.candidates:
                ans = QMessageBox.question(
                    self, "동일인 후보 남음",
                    f"판정하지 않은 동일인 후보 {len(self.settlement.candidates)}건은 별도 송하인으로 계산합니다.\n계속할까요?")
                if ans != QMessageBox.Yes:
                    return
        s = self.settlement
        y, m = self.year_month
        rows = s.summary_rows(self.master.senders)
        try:
            s.verify(rows)
        except DataError as e:
            self.error(str(e), "검증 실패")
            return

        start_dir = Path(self.settings.last_save_dir) if self.settings.last_save_dir and \
            Path(self.settings.last_save_dir).is_dir() else paths.OUTPUT_DIR
        target, _ = QFileDialog.getSaveFileName(self, "정산 엑셀 저장", str(start_dir / default_filename(y, m)),
                                                "엑셀 파일 (*.xlsx)")
        if not target:
            return
        target = Path(target)
        if target.suffix.lower() != ".xlsx":
            target = target.with_suffix(".xlsx")
        try:
            write_report(target, s, rows)
        except OutputLockedError as e:
            self.error(str(e))
            return
        self.settings.last_save_dir = str(target.parent)
        self._save_settings()
        self.log(f"정산 엑셀 저장: {target}  (검증 OK: {s.total_count}건 · {won(s.total_amount)}원)")

        self.master.touch_senders(s.groups.keys(), f"{y:04d}-{m:02d}")
        if self._save_master():
            self.log("송하인 마스터 갱신(신규 등록·최근정산월)")
        self.refresh()
        self._done_dialog(target)

    def _done_dialog(self, target: Path):
        box = QMessageBox(self)
        box.setWindowTitle("완료")
        box.setText(f"정산 엑셀을 저장했습니다.\n{target}")
        open_file = box.addButton("파일 열기", QMessageBox.AcceptRole)
        open_dir = box.addButton("폴더 열기", QMessageBox.ActionRole)
        box.addButton("닫기", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_file:
            self._open_path(target)
        elif box.clickedButton() is open_dir:
            self._open_path(target.parent)

    def _open_path(self, p: Path):
        if not Path(p).exists():
            self.error(f"아직 파일이 없습니다: {Path(p).name}")
            return
        os.startfile(str(p))

    # ── 자동 다운로드 ──
    def _start_download(self):
        if self.worker and self.worker.isRunning():
            self.worker.downloader.cancel()
            self.log("자동 다운로드 중지 요청…")
            return
        uid, pw = self.id_edit.text().strip(), self.pw_edit.text()
        if not uid or not pw:
            self.error("ID와 PW를 입력하세요.")
            (self.pw_edit if uid else self.id_edit).setFocus()
            return
        self._save_settings()
        y, m = self.year_month
        self.worker = DownloadWorker(dict(user_id=uid, password=pw, year=y, month=m,
                                          download_dir=paths.DOWNLOAD_DIR, log_dir=paths.LOG_DIR))
        self.worker.log.connect(self.log)
        self.worker.done.connect(self._download_done)
        self.worker.failed.connect(self._download_failed)
        self.worker.finished.connect(lambda: self.download_btn.setText("자동 다운로드"))
        self.download_btn.setText("중지")
        self.log(f"자동 다운로드 시작: {y}년 {m}월")
        self.worker.start()

    def _download_done(self, result):
        """받은 파일을 불러와 [정산 엑셀 생성] 직전까지 진행: 미리보기 → 확정 경고 → 동일인 후보 판정."""
        self.log("자동 다운로드 완료")
        self._bring_to_front()
        if not self.load_files([str(result.path)]):
            return
        self.unconfirmed = result.unconfirmed
        if self.unconfirmed:
            self.refresh()
            QMessageBox.warning(self, "확정 전",
                                f"아직 확정 전입니다.\n인보이스 {', '.join(self.unconfirmed)}의 확정 값이 N입니다. "
                                "정산 금액이 바뀔 수 있습니다.")
        if self.settlement and self.settlement.candidates:
            self.log(f"동일인 후보 {len(self.settlement.candidates)}건 확인 창을 엽니다.")
            self._review_candidates()
        self.make_btn.setFocus()
        self.log("준비 완료. 미리보기를 확인하고 [정산 엑셀 생성]을 누르세요.")

    def _bring_to_front(self):
        """Edge 창 뒤에 가려 있던 프로그램 창을 앞으로."""
        if self.isMinimized():
            self.showNormal()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.show()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.show()
        self.raise_()
        self.activateWindow()

    def _download_failed(self, kind: str, msg: str):
        if kind == "login":
            self.error(msg, "로그인 실패")
            self.pw_edit.setFocus()
            self.pw_edit.selectAll()
        elif kind == "cancel":
            self.log(msg)
        else:
            self.error(msg, "자동 다운로드")
