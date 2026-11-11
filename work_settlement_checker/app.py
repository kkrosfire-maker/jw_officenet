"""정산 알림 프로그램 — 제약사별 통계 마감일을 담당자·병원 단위로 보여주고, 처리 여부는 작업 엑셀에서 읽는다.

실행:  pythonw run.pyw            창(pywebview)
       python app.py --serve 8765 개발용: 브라우저/Playwright로 화면 확인
       python app.py --notify     창 없이 오늘 마감·지난 미처리가 있으면 윈도우 알림만 띄우고 종료
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import core
import ledger_read
import names
import schedule
import store

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
UI = BASE / "ui.html"


def default_month(today):
    months = store.saved_months()
    if (today.year, today.month) in months or not months:
        return today.year, today.month
    return months[-1]


class Api:
    def __init__(self):
        self._window = None
        self._cur = None             # 화면에 열려 있는 (연, 월) — 끌어다 놓은 파일의 달을 정할 때 쓴다

    # ---- 화면용 ----
    def state(self, year=None, month=None):
        today = dt.date.today()
        if not year:
            year, month = default_month(today)
        self._cur = (year, month)
        months = sorted(set(store.saved_months()) | {(today.year, today.month)})
        out = dict(year=year, month=month, months=[list(m) for m in months], today=today.isoformat(),
                   hour=dt.datetime.now().hour, has_deadlines=False, work_file=None, error=None)
        deadlines = store.load_month(year, month)
        out["has_deadlines"] = deadlines is not None
        wf = self._work_file(year, month)
        out["work_file"] = str(wf) if wf else None
        if wf is None:
            out["error"] = f"{year % 100:02d}{month:02d} 작업 엑셀(1.통계입력_{year % 100:02d}{month:02d}.xlsx)을 찾지 못했습니다."
        try:
            rows = ledger_read.read_rows(wf, month) if wf else []
        except Exception as e:                      # 엑셀 파일 손상·잠김 등
            rows, out["error"] = [], f"작업 엑셀을 읽지 못했습니다: {e}"
        out["view"] = core.build_view(year, month, deadlines or [], rows, store.load_aliases(), today)
        return out

    def import_image(self, year=None, month=None):
        """마감일정 이미지를 골라 읽고 저장한다. 제목에서 연·월을 읽고, 못 읽으면 인자를 쓴다."""
        import webview
        import deadline_ocr
        sel = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("이미지 (*.png;*.jpg;*.jpeg)",))
        if not sel:
            return dict(ok=False, cancelled=True)
        path = sel[0] if isinstance(sel, (list, tuple)) else sel
        return self.import_path(path, year, month)

    def import_path(self, path, year=None, month=None):
        import deadline_ocr
        try:
            ym = deadline_ocr.read_title(path)
            if ym:
                year, month = ym
            if not year:
                today = dt.date.today()
                year, month = today.year, today.month
            entries = deadline_ocr.read_image(path)
        except Exception as e:
            return dict(ok=False, error=str(e))
        wf = self._work_file(year, month)
        rows = ledger_read.read_rows(wf, month) if wf else []
        book = names.NameBook.from_names([r.pharma for r in rows])
        deadlines = schedule.from_entries(entries, book, deadline_ocr.reread_variants)
        store.save_month(year, month, deadlines, source=str(path))
        try:
            store.save_source_image(year, month, path)          # '마감표 이미지 내보내기'용 원본 보관
        except OSError:
            pass
        return dict(ok=True, year=year, month=month, count=len(deadlines))

    def export_schedule_image(self, year, month):
        """보관해 둔 원본 마감표 이미지의 제목 '지에스파마'를 '정원유니어스(주)'로 바꿔 저장하고 클립보드에도 넣는다."""
        import title_render
        src = store.source_image(year, month)
        if not src:
            return dict(ok=False, error=f"{month}월 마감표 이미지가 없습니다. 먼저 마감표 이미지를 불러와 주세요.")
        try:
            im = title_render.render(src, year, month)
        except Exception as e:
            return dict(ok=False, error=f"제목을 바꾸지 못했습니다: {e}")
        try:
            folder = self._image_dir()
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{month}월_마감표_({dt.datetime.now():%y%m%d_%H%M%S}).png"
            im.save(path)
        except OSError as e:
            return dict(ok=False, error=f"이미지를 저장하지 못했습니다: {e}")
        return dict(ok=True, path=str(path), clip=self._clipboard_image(path))

    def save_image(self, data_url, name):
        """상세 패널 이미지를 바탕화면의 정산알림_이미지 폴더에 저장하고 클립보드에도 넣는다(카톡 입력창에 Ctrl+V)."""
        import base64
        import re
        try:
            folder = self._image_dir()
            folder.mkdir(parents=True, exist_ok=True)
            safe = re.sub(r'[\\/:*?"<>|\s]+', "_", name)
            path = folder / f"{safe}_({dt.datetime.now():%y%m%d_%H%M%S}).png"
            path.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
            return dict(ok=True, path=str(path), clip=self._clipboard_image(path))
        except Exception as e:
            return dict(ok=False, error=str(e))

    @staticmethod
    def _image_dir():
        return Path(os.environ.get("SETTLEMENT_IMAGE_DIR") or Path.home() / "Desktop" / "정산알림_이미지")

    @staticmethod
    def _clipboard_image(path):
        """이미지 파일을 클립보드에 넣는다(카톡 입력창에 Ctrl+V). 성공하면 True."""
        if os.environ.get("SETTLEMENT_NO_CLIP"):
            return False
        ps = ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
              "$i=[System.Drawing.Image]::FromFile($env:SC_IMG);[System.Windows.Forms.Clipboard]::SetImage($i);$i.Dispose()")
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-WindowStyle", "Hidden", "-Command", ps],
                           env=dict(os.environ, SC_IMG=str(path)), creationflags=0x08000000, capture_output=True)
        return r.returncode == 0

    def carry_over(self, year, month, manager, hospital, pharma):
        """통계를 이번 달에 내지 않고 다음 달로 넘긴다 → 작업 엑셀 상태=통계이월, 특이사항='mm월 통계 다음달로 이월'."""
        import ledger_write
        wf = self._work_file(year, month)
        if wf is None:
            return dict(ok=False, error="작업 엑셀을 찾지 못했습니다.")
        try:
            n = ledger_write.carry_over(wf, month, manager, hospital, pharma)
        except PermissionError:
            return dict(ok=False, error="엑셀 파일이 열려 있어 저장하지 못했습니다. 엑셀을 닫고 다시 눌러 주세요.")
        except Exception as e:
            return dict(ok=False, error=f"엑셀에 쓰지 못했습니다: {e}")
        if not n:
            return dict(ok=False, error="바꿀 줄을 찾지 못했습니다(이미 처리됐거나 엑셀이 바뀌었습니다). 새로고침해 주세요.")
        return dict(ok=True, count=n)

    def link(self, raw, pharma):
        """마감표의 이름(raw)을 엑셀 제약사(pharma)에 연결해 기억한다. pharma가 '-'면 '우리 거래 없음'으로 무시."""
        store.save_alias(names.norm(raw), pharma)
        return True

    def pick_work_file(self, year, month):
        import webview
        sel = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("엑셀 (*.xlsx)",))
        if not sel:
            return dict(ok=False, cancelled=True)
        return self.set_work_file(sel[0], year, month)

    def set_work_file(self, path, year=None, month=None):
        """그 달 작업 엑셀로 이 파일을 기억한다(끌어다 놓기·찾아보기 공용). 파일명이 1.통계입력_yymm.xlsx 이면 그 달로 정한다.
        열리는지·그 달 줄이 있는지 확인한 뒤에만 저장한다."""
        p = Path(path)
        if p.suffix.lower() != ".xlsx":
            return dict(ok=False, error=f"엑셀(.xlsx) 파일이 아닙니다: {p.name}")
        m = re.search(r"통계입력_(\d{2})(\d{2})", p.name)
        if m:
            year, month = 2000 + int(m.group(1)), int(m.group(2))
        elif not year:
            year, month = self._cur or default_month(dt.date.today())
        try:
            rows = ledger_read.read_rows(p, month)
        except Exception as e:
            return dict(ok=False, error=f"엑셀을 읽지 못했습니다: {e}")
        if not rows:
            return dict(ok=False, error=f"{p.name} 에 입력월 {month}월 줄이 없습니다. 파일을 확인해 주세요.")
        cfg = store.load_config()
        cfg[f"work_{year % 100:02d}{month:02d}"] = str(p)
        store.save_config(cfg)
        return dict(ok=True, year=year, month=month, count=len(rows), name=p.name)

    # ---- 내부 ----
    def _work_file(self, year, month):
        p = store.load_config().get(f"work_{year % 100:02d}{month:02d}")
        if p and Path(p).exists():
            return Path(p)
        return ledger_read.find_work_file(year, month)


def notify_text(state):
    s = state["view"]["summary"]
    if not s["overdue"] and not s["today"]:
        return None
    parts = []
    if s["today"]:
        parts.append(f"오늘 마감 미처리 {s['today']}건")
    if s["overdue"]:
        parts.append(f"기한 지난 미처리 {s['overdue']}건")
    return " · ".join(parts)


def toast(title, body):
    ps = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent('ToastText02')
$n = $t.GetElementsByTagName('text')
$n.Item(0).AppendChild($t.CreateTextNode($env:TOAST_TITLE)) | Out-Null
$n.Item(1).AppendChild($t.CreateTextNode($env:TOAST_BODY)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($t)
$id = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($id).Show($toast)
"""
    env = dict(os.environ, TOAST_TITLE=title, TOAST_BODY=body)
    subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps], env=env,
                   creationflags=0x08000000, check=False)


def serve(port):
    """개발용: ui.html 을 띄우고 /api/<메서드> 로 Api를 부른다(브라우저에서 화면 확인용)."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    api = Api()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = UI.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            args = json.loads(self.rfile.read(n) or b"[]")
            name = self.path.rsplit("/", 1)[-1]
            try:
                res = getattr(api, name)(*args)
            except Exception as e:
                res = dict(ok=False, error=str(e))
            data = json.dumps(res, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(data)

    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


def classify_drop(path):
    """끌어다 놓은 파일 종류: 엑셀 → 작업 엑셀, 이미지 → 마감표 이미지, 그 밖 → None."""
    ext = Path(path).suffix.lower()
    return "excel" if ext == ".xlsx" else "image" if ext in (".png", ".jpg", ".jpeg") else None


def _bind_drop(window, api):
    """창에 파일을 끌어다 놓으면(엑셀) 그 달 작업 엑셀로 등록하고 화면을 다시 읽는다. 마감표 이미지는 여기서 받지 않는다."""
    from webview.dom import DOMEventHandler

    def js(fn, arg=None):
        window.evaluate_js(f"{fn}({json.dumps(arg, ensure_ascii=False)})" if arg is not None else f"{fn}()")

    def on_drop(event):
        files = (event.get("dataTransfer") or {}).get("files", [])
        paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
        if not paths:
            js("onWorkFileDropped", dict(ok=False, error="파일 위치를 알 수 없습니다. 위쪽 버튼으로 직접 선택해 주세요."))
            return
        for p in sorted(paths, key=lambda p: Path(p).suffix.lower() != ".xlsx"):      # 엑셀을 먼저(이미지를 읽을 때 새 작업 엑셀을 쓰도록)
            kind = classify_drop(p)
            if kind == "excel":
                js("onWorkFileDropped", api.set_work_file(p))
            elif kind == "image":
                js("onImageDropStart")
                y, m = api._cur or (None, None)
                js("onImageDropped", api.import_path(p, y, m))
            else:
                js("onWorkFileDropped", dict(ok=False, error=f"지원하지 않는 파일입니다: {Path(p).name} (엑셀 또는 png·jpg 이미지만)"))

    window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)


def main():
    if "--serve" in sys.argv:
        serve(int(sys.argv[sys.argv.index("--serve") + 1]))
        return
    if "--notify" in sys.argv:
        text = notify_text(Api().state())
        if text:
            toast("정산 마감 알림", text)
        return
    import webview
    api = Api()
    api._window = webview.create_window("정산 알림", str(UI), js_api=api, width=1180, height=860, min_size=(900, 600))
    webview.start(_bind_drop, (api._window, api))


if __name__ == "__main__":
    main()
