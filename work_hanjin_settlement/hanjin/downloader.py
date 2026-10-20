"""focus.hanjin.com 운임정산 세부내역 자동 다운로드 (Playwright + Edge).

화면에 창을 띄우지 않고(headless) 백그라운드에서 진행하며, 성공·실패와 관계없이 끝나면 Edge를 닫는다.
어느 단계에서 막히면 그 단계 이름과 화면 캡처(logs/)를 남기고 수동 파일 입력을 안내한다.
"""
from __future__ import annotations

import calendar
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

LOGIN_URL = "http://focus.hanjin.com"
CALCFEE_URL = "https://focus.hanjin.com/result/calcfee"
STEP_TIMEOUT_MS = 30_000


class LoginError(Exception):
    pass


class NoDataError(Exception):
    pass


class StepError(Exception):
    def __init__(self, step: str, cause: Exception | str):
        super().__init__(f"[{step}] 단계에서 멈췄습니다: {cause}")
        self.step = step


class Cancelled(Exception):
    pass


@dataclass
class DownloadResult:
    path: Path
    invoices: list[dict] = field(default_factory=list)
    unconfirmed: list[str] = field(default_factory=list)


class HanjinDownloader:
    def __init__(self, user_id: str, password: str, year: int, month: int,
                 download_dir: Path, log_dir: Path, log: Callable[[str], None]):
        self.user_id, self.password = user_id, password
        self.year, self.month = year, month
        self.download_dir, self.log_dir = Path(download_dir), Path(log_dir)
        self.log = log
        self.cancel_event = threading.Event()

    # ── 진입점 ──
    def run(self) -> DownloadResult:
        from playwright.sync_api import sync_playwright

        self.download_dir.mkdir(exist_ok=True)
        with sync_playwright() as p:
            self.log("백그라운드에서 Edge 시작…")
            browser = p.chromium.launch(channel="msedge", headless=True)
            context = browser.new_context(accept_downloads=True, viewport={"width": 1400, "height": 900})
            context.set_default_timeout(STEP_TIMEOUT_MS)
            page = context.new_page()
            try:
                self._login(page)
                invoices = self._query(page)
                path = self._download(page)
                unconfirmed = [i["인보이스"] for i in invoices if i.get("확정", "").upper() == "N"]
                return DownloadResult(path, invoices, unconfirmed)
            except (LoginError, NoDataError, Cancelled):
                raise
            except StepError as e:
                self._screenshot(page, e.step)
                raise
            finally:
                try:
                    browser.close()
                    self.log("Edge 종료")
                except Exception:
                    pass

    def cancel(self):
        self.cancel_event.set()

    # ── 단계 ──
    def _step(self, name: str, fn):
        if self.cancel_event.is_set():
            raise Cancelled()
        self.log(f"▶ {name}")
        try:
            return fn()
        except (LoginError, NoDataError, Cancelled):
            raise
        except Exception as e:
            raise StepError(name, _short(e)) from e

    def _login(self, page):
        def go():
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.get_by_placeholder("아이디를 입력해주세요").fill(self.user_id)
            page.get_by_placeholder("비밀번호를 입력해주세요").fill(self.password)
            page.locator("button", has_text=re.compile(r"^\s*로그인\s*$")).first.click()
            deadline = time.time() + STEP_TIMEOUT_MS / 1000
            while time.time() < deadline:
                if "/login" not in page.url:
                    return
                if self._visible_text(page, ".el-message-box__message, .el-message__content, .el-dialog__body"):
                    break
                page.wait_for_timeout(300)
            raise LoginError("로그인에 실패했습니다. ID/PW를 확인하세요.")
        self._step("로그인", go)
        page.wait_for_load_state("networkidle")
        self._close_popups(page)

    def _query(self, page) -> list[dict]:
        def open_menu():
            page.goto(CALCFEE_URL, wait_until="networkidle")
            self._close_popups(page)
            page.get_by_placeholder("시작일").first.wait_for(state="visible")
        self._step("운임 정산 현황 화면 열기", open_menu)

        last_day = calendar.monthrange(self.year, self.month)[1]

        def set_dates():
            start = page.get_by_placeholder("시작일").first
            end = page.get_by_placeholder("종료일").first
            sep = "." if "." in (start.input_value() or "") else "-"
            fmt = lambda d: f"{self.year:04d}{sep}{self.month:02d}{sep}{d:02d}"
            for box, value in ((start, fmt(1)), (end, fmt(last_day))):
                box.click()
                box.press("Control+A")
                box.type(value, delay=20)
                box.press("Enter")
            page.keyboard.press("Escape")
            got = (start.input_value(), end.input_value())
            self.log(f"   기간: {got[0]} ~ {got[1]}")
            if got != (fmt(1), fmt(last_day)):
                raise RuntimeError(f"기간 입력이 반영되지 않았습니다({got[0]}~{got[1]})")
        self._step(f"기간 설정 {self.year}-{self.month:02d}", set_dates)

        def search():
            page.locator(".button-condition-form__search").first.click()
            self._wait_loading(page)
        self._step("검색(돋보기)", search)

        def read_invoices():
            table = page.locator(".el-table", has_text="인보이스").first
            table.wait_for(state="visible")
            deadline = time.time() + STEP_TIMEOUT_MS / 1000
            rows = table.locator(".el-table__body-wrapper tr.el-table__row")
            while rows.count() == 0 and time.time() < deadline:
                if table.locator(".el-table__empty-block").is_visible():
                    break
                page.wait_for_timeout(300)
            if rows.count() == 0:
                raise NoDataError(f"{self.year}년 {self.month}월 자료가 없습니다.")
            headers = [h.strip() for h in table.locator(".el-table__header-wrapper th").all_inner_texts()]
            invoices = []
            for i in range(rows.count()):
                cells = [c.strip() for c in rows.nth(i).locator("td").all_inner_texts()]
                rec = dict(zip(headers, cells))
                inv = next((v for v in cells if re.match(r"^[A-Z]{2}\d{6,}$", v)), rec.get("인보이스", ""))
                rec["인보이스"] = inv
                rec["확정"] = next((v for k, v in rec.items() if "확정" in k), "")
                invoices.append(rec)
                self.log(f"   인보이스 {inv}  확정={rec['확정'] or '?'}")
            return table, invoices
        table, invoices = self._step("인보이스 목록 읽기", read_invoices)

        def check_all():
            # 클릭 후 화면 반영이 늦으면 같은 칸을 두 번 눌러 도로 해제되므로, 누를 때마다 반영을 기다린다
            head = table.locator(".el-table__header-wrapper .el-checkbox").first
            boxes = table.locator(".el-table__body-wrapper tr.el-table__row .el-checkbox")
            checked = lambda b: "is-checked" in (b.get_attribute("class") or "")
            unchecked = lambda: [i for i in range(boxes.count()) if not checked(boxes.nth(i))]

            def settle_until_checked(ms=3000):
                deadline = time.time() + ms / 1000
                while unchecked() and time.time() < deadline:
                    page.wait_for_timeout(200)

            if unchecked() and head.count() and not checked(head):
                head.click()
                settle_until_checked()
            for i in unchecked():
                boxes.nth(i).click()
                deadline = time.time() + 3
                while not checked(boxes.nth(i)) and time.time() < deadline:
                    page.wait_for_timeout(200)
            if unchecked():
                raise RuntimeError(f"체크되지 않은 행 {len(unchecked())}개")
            self.log(f"   {boxes.count()}개 행 체크됨")
        self._step("인보이스 전체 체크", check_all)

        def select_query():
            page.locator("button", has_text=re.compile(r"선택\s*조회")).first.click()
            self._wait_loading(page)
        self._step("선택 조회", select_query)
        return invoices

    def _download(self, page) -> Path:
        def go():
            btn = page.locator("button, a", has_text=re.compile(r"세부\s*내역\s*엑셀"))
            btn.first.wait_for(state="visible")
            with page.expect_download(timeout=60_000) as info:
                btn.first.click()
                self._confirm_popup(page)
            return self._save(info.value)
        return self._step("세부내역 엑셀다운", go)

    # ── 도우미 ──
    def _save(self, download) -> Path:
        ext = Path(download.suggested_filename).suffix or ".xlsx"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self.download_dir / f"한진세부내역_{self.year:04d}{self.month:02d}_{stamp}{ext}"
        download.save_as(dest)
        self.log(f"   저장: downloads/{dest.name}")
        return dest

    def _wait_loading(self, page):
        page.wait_for_timeout(500)
        mask = page.locator(".el-loading-mask")
        deadline = time.time() + STEP_TIMEOUT_MS / 1000
        while time.time() < deadline:
            if not any(mask.nth(i).is_visible() for i in range(mask.count())):
                return
            page.wait_for_timeout(300)
        raise RuntimeError("조회가 30초 안에 끝나지 않았습니다")

    def _confirm_popup(self, page, wait_ms: int = 5000):
        """다운로드 전 확인창('5,000건 이상의 데이터는 csv파일로…')이 뜨면 [확인]을 누른다."""
        ok = page.get_by_text("확인", exact=True).filter(visible=True)
        deadline = time.time() + wait_ms / 1000
        while time.time() < deadline:
            if ok.count():
                ok.last.click()
                self.log("   확인창 [확인] 누름")
                return
            page.wait_for_timeout(200)

    @staticmethod
    def _visible_text(page, selector) -> str:
        loc = page.locator(selector)
        for i in range(loc.count()):
            if loc.nth(i).is_visible():
                return loc.nth(i).inner_text()
        return ""

    def _close_popups(self, page):
        """공지 팝업 등을 닫는다. 실패해도 진행."""
        try:
            page.wait_for_timeout(800)
            for sel in (".el-message-box__headerbtn", ".el-dialog__headerbtn"):
                loc = page.locator(sel)
                for i in range(loc.count()):
                    if loc.nth(i).is_visible():
                        loc.nth(i).click(timeout=2000)
                        self.log("   팝업 닫음")
            for p in page.context.pages:
                if p is not page:
                    p.close()
        except Exception:
            pass

    def _screenshot(self, page, step: str):
        try:
            self.log_dir.mkdir(exist_ok=True)
            name = f"실패_{datetime.now():%Y%m%d_%H%M%S}_{re.sub(r'[^0-9A-Za-z가-힣]+', '_', step)}.png"
            page.screenshot(path=str(self.log_dir / name), full_page=True)
            self.log(f"   화면 캡처: logs/{name}")
        except Exception:
            pass


def _short(e) -> str:
    s = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
    return s[:200]
