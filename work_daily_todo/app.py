"""오늘의 할 일 - 프로그램 보드 옆에 붙여두는 세로형 할 일 체크 프로그램.
데이터는 data/todos.json 에 자동 저장되고, '저장' 버튼으로 기간별 엑셀 분석 파일을 만든다.
규칙은 ledger.py, 내보내기는 report.py, 창 배치는 docking.py 에 있고 이 파일은 화면(JS)과 그 셋을 잇는다."""
import json
import os
import sys
from datetime import date

import webview

import docking
from ledger import WEEKDAY, JsonStore, Ledger
from report import build_excel, build_image

FROZEN = getattr(sys, "frozen", False)
HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))  # 화면 파일 위치
BASE = os.path.dirname(sys.executable) if FROZEN else HERE  # exe 옆에 data 폴더를 둔다
DATA_DIR = os.path.join(BASE, "data")
DATA = os.path.join(DATA_DIR, "todos.json")
WIN = os.path.join(DATA_DIR, "window.json")


class Api:
    """JS 에서 호출하는 함수 모음. 상태는 _ 로 시작하는 속성에만 둔다(pywebview 가 공개 속성을 훑기 때문).
    할 일을 바꾸는 함수는 모두 바뀐 뒤의 화면용 상태를 돌려준다."""

    def __init__(self):
        self._ledger = Ledger(JsonStore(DATA))
        self._window = None

    def _do(self, change, *args):
        change(*args)
        return self._ledger.view()

    # ---- 화면용 API ----
    def get_state(self):
        return self._ledger.view()

    def add(self, text, parent=None, due=None, daily=False):
        return self._do(self._ledger.add, text, parent, due, daily)

    def toggle(self, tid):
        return self._do(self._ledger.toggle, tid)

    def edit(self, tid, text):
        return self._do(self._ledger.edit, tid, text)

    def set_note(self, tid, note):
        return self._do(self._ledger.set_note, tid, note)

    def remove(self, tid):
        return self._do(self._ledger.remove_many, [tid])

    def remove_many(self, ids):
        return self._do(self._ledger.remove_many, ids)

    def set_due(self, tid, due):
        return self._do(self._ledger.set_due, tid, due)

    def set_daily(self, tid, on):
        return self._do(self._ledger.set_daily, tid, on)

    def set_pin(self, on):
        return docking.set_pin(on)

    def quit(self):
        self._close()
        if self._window:
            self._window.destroy()

    def _close(self):
        w = self._window
        if w:
            try:
                with open(WIN, "w", encoding="utf-8") as f:
                    json.dump({"x": w.x, "y": w.y, "width": w.width, "height": w.height}, f)
            except Exception:
                pass

    # ---- 내보내기 ----
    def _ask_path(self, name, file_type, ext_ok, ext_add):
        dest = self._window.create_file_dialog(webview.SAVE_DIALOG, save_filename=name, file_types=(file_type,))
        if not dest:
            return None
        dest = dest if isinstance(dest, str) else dest[0]
        return dest if dest.lower().endswith(ext_ok) else dest + ext_add

    @staticmethod
    def _open(path):
        try:
            os.startfile(path)
        except OSError:
            pass

    def export_image(self):
        """오늘 화면의 목록을 JPG 이미지로 저장한다(목록은 그대로 둔다)."""
        st = self._ledger.view()
        if not st["tasks"]:
            return {"ok": False, "error": "저장할 할 일이 없어요."}
        d = date.today()
        dest = self._ask_path(f"오늘의할일_{d:%y%m%d}.jpg", "JPG 이미지 (*.jpg)", (".jpg", ".jpeg"), ".jpg")
        if not dest:
            return {"ok": False, "cancel": True}
        try:
            build_image(st["tasks"], dest, f"{d:%Y.%m.%d}({WEEKDAY[d.weekday()]})")
        except PermissionError:
            return {"ok": False, "error": "같은 이름의 파일이 열려 있어요."}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}
        self._open(dest)
        return {"ok": True, "count": len(st["tasks"])}

    def export_excel(self, start, end):
        """start~end(YYYY-MM-DD, 빈 값이면 전체) 동안 등록되었거나 완료된 일을 엑셀로 저장한다."""
        dest = self._ask_path(f"할일기록_{date.today():%y%m%d}.xlsx", "Excel 파일 (*.xlsx)", ".xlsx", ".xlsx")
        if not dest:
            return {"ok": False, "cancel": True}
        try:
            n, done_ids = build_excel(self._ledger.tasks, start, end, dest, date.fromisoformat(self._ledger.today()))
        except PermissionError:
            return {"ok": False, "error": "엑셀 파일이 열려 있어요. 닫고 다시 저장해 주세요."}
        except Exception as e:  # noqa: BLE001 - 사용자에게 그대로 보여준다
            return {"ok": False, "error": str(e)}
        self._open(dest)
        self._ledger.archive(done_ids)
        return {"ok": True, "count": n, "path": dest, "state": self._ledger.view()}


def main():
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("JWUnius.DailyTodo")  # 작업표시줄에서 python 이 아닌 이 앱 아이콘으로 묶이게
    if "--dock" in sys.argv and docking.is_open():
        docking.dock_next_to_board(5)  # 이미 떠 있으면 위치만 다시 맞춘다
        return
    api = Api()
    x, y, w, h = docking.start_geometry(WIN)
    win = webview.create_window(docking.TITLE, os.path.join(HERE, "index.html"), js_api=api, x=x, y=y, width=w, height=h,
                                min_size=(300, 420), on_top=False, background_color="#FFFFFF")
    api._window = win
    win.events.closing += api._close
    dock = "--dock" in sys.argv
    icon = os.path.join(HERE, "app.ico")
    webview.start(lambda: docking.follow_board(30 if dock else 1), icon=icon if os.path.exists(icon) else None)


if __name__ == "__main__":
    sys.exit(main())
