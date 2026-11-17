"""정원유니어스 프로그램 보드 - 로컬 실행기.
index.html 을 서빙하고, 카드 클릭 시 programs.json 에 등록된 프로그램만 실행한다."""
import json, os, subprocess, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from icons import icon_for, save_custom, suggest
from store import StoreError, apply

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765
ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
TODO_DIR = os.path.join(os.path.dirname(HERE), "work_daily_todo")  # 오늘의 할 일 - 보드 오른쪽 접이식 패널로 합쳐 둔다
TODO_W = 371  # work_daily_todo/docking.py FIXED_WIDTH 와 같은 패널 너비(CSS px)


def load():
    with open(os.path.join(HERE, "programs.json"), encoding="utf-8") as f:
        return json.load(f)


UI_STATE = os.path.join(HERE, "ui_state.json")  # 창 상태(할 일 패널 펼침 여부) - 사용자별 값이라 git 에 올리지 않는다


def load_ui():
    try:
        with open(UI_STATE, encoding="utf-8") as f:
            return {"todo_open": bool(json.load(f).get("todo_open"))}
    except (OSError, ValueError, AttributeError):
        return {"todo_open": False}


def save(cfg):
    tmp = os.path.join(HERE, "programs.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(HERE, "programs.json"))


def browse():
    """exe 파일 선택 창(tkinter)을 별도 프로세스로 띄우고 고른 경로를 돌려준다."""
    code = ("import tkinter as tk, tkinter.filedialog as fd;r=tk.Tk();r.withdraw();r.attributes('-topmost',True);"
            "print(fd.askopenfilename(filetypes=[('프로그램','*.exe *.bat *.lnk'),('모든 파일','*.*')]))")
    out = subprocess.run([sys.executable, "-X", "utf8", "-c", code], capture_output=True, text=True,  # 파이프 출력이 cp949라 한글 경로가 깨지던 문제
                         encoding="utf-8", creationflags=0x08000000).stdout.strip()
    return out.replace("/", "\\")


def launch(p):
    if p.get("type") == "url":
        webbrowser.open(p["url"])
        return
    path = p["path"]
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    cmd = f'"{path}" {p.get("args", "")}'.strip()
    before = _visible_windows()
    subprocess.Popen(cmd, cwd=p.get("cwd") or os.path.dirname(path),
                     creationflags=0x00000008 | 0x00000200, close_fds=True)  # DETACHED | NEW_GROUP
    threading.Thread(target=_raise_new_window, args=(before,), daemon=True).start()


def _visible_windows():
    """제목 있는 보이는 최상위 창 핸들 집합."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    found = set()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        if u.IsWindowVisible(h) and u.GetWindowTextLengthW(h) > 0 and not u.GetWindow(h, 4):  # GW_OWNER
            found.add(h)
        return True
    u.EnumWindows(cb, 0)
    return found


def _raise_new_window(before, timeout=30):
    """서버는 포그라운드 권한이 없어 새로 뜬 앱 창이 다른 창 뒤에 깔림 → 새 창을 앞으로 올린다."""
    import ctypes, time
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.3)
        new = _visible_windows() - before
        if not new:
            continue
        time.sleep(0.4)  # 창이 다 그려진 뒤
        h = max(new)
        fg = u.GetForegroundWindow()
        me, other = k.GetCurrentThreadId(), u.GetWindowThreadProcessId(fg, None)
        u.AttachThreadInput(me, other, True)
        try:
            u.ShowWindow(h, 6)  # SW_MINIMIZE 후 복원하면 포그라운드 제한을 우회해 맨 앞으로 나옴
            u.ShowWindow(h, 9)  # SW_RESTORE
            u.BringWindowToTop(h)
            u.SetForegroundWindow(h)
            if u.GetForegroundWindow() != h:
                u.SwitchToThisWindow(h, True)
        finally:
            u.AttachThreadInput(me, other, False)
        return


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body=b"", ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/ui":
            return self.send(200, json.dumps(load_ui()).encode())
        if path == "/api/programs":
            return self.send(200, json.dumps(load(), ensure_ascii=False).encode())
        if path == "/":
            path = "/index.html"
        elif path == "/favicon.ico":
            path = "/assets/icons/officeboard.png"
        root = HERE
        if path.startswith("/todo/"):  # 오늘의 할 일 화면(iframe)과 그 아이콘
            root, path = TODO_DIR, path[len("/todo"):]
        full = os.path.normpath(os.path.join(root, path.lstrip("/")))
        allowed = path in ("/index.html", "/manifest.json") or path.startswith("/assets/")
        if not (allowed and full.startswith(root) and os.path.isfile(full)):
            return self.send(404)
        ext = os.path.splitext(full)[1].lower()
        ctype = {".html": "text/html; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg", ".json": "application/manifest+json"}.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            self.send(200, f.read(), ctype)

    def do_POST(self):
        route = urlparse(self.path).path
        if route == "/api/ui" and self.headers.get("Origin") in ORIGINS:
            try:
                st = {"todo_open": bool(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()).get("todo_open"))}
                with open(UI_STATE, "w", encoding="utf-8") as f:
                    json.dump(st, f)
                return self.send(200, b'{"ok":true}')
            except (ValueError, OSError, AttributeError):
                return self.send(400)
        if route not in ("/api/launch", "/api/save", "/api/browse") or self.headers.get("Origin") not in ORIGINS:
            return self.send(403)
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        if route == "/api/browse":
            path = browse()
            name, desc = suggest(path) if path else ("", "")
            return self.send(200, json.dumps({"path": path, "name": name, "desc": desc}, ensure_ascii=False).encode())
        if route == "/api/save":
            return self.do_save(body)
        pid = body
        prog = next((p for p in load()["programs"] if p["id"] == pid), None)
        if not prog:
            return self.send(404, b'{"ok":false,"error":"unknown"}')
        try:
            launch(prog)
            self.send(200, b'{"ok":true}')
        except Exception as e:
            self.send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode())


    def do_save(self, body):
        """{action: add|update|delete|reorder, ...} 를 store.apply 로 적용해 programs.json 에 저장한다."""
        try:
            req = json.loads(body)
            prog = req.get("program") or {}
            data = prog.pop("icon_data", None)  # 사용자가 고른 이미지(dataURL). 있으면 자동 아이콘 가져오기는 건너뛴다
            reset = prog.pop("icon_reset", False) and req["action"] == "update" and not data  # 직접 고른 이미지를 버리고 자동 아이콘으로
            base = load()
            if reset:
                old = next((p for p in base["programs"] if p["id"] == prog.get("id")), None)
                if old:
                    old.pop("icon_custom", None)
            cfg = apply(base, req, (lambda p: "") if data else icon_for)
            if reset:
                target = next(p for p in cfg["programs"] if p["id"] == prog.get("id"))
                try:
                    target["icon"] = icon_for(target) or ""
                except Exception:
                    target["icon"] = ""
                target.pop("icon_custom", None)
            if data:
                import base64
                target = next(p for p in cfg["programs"] if p["id"] == (prog.get("id") if req["action"] == "update" else cfg["programs"][-1]["id"]))
                try:
                    target["icon"] = save_custom(target["id"], base64.b64decode(data.split(",", 1)[-1]))
                except ValueError as e:
                    raise StoreError(str(e))
                target["icon_custom"] = True
            save(cfg)
            self.send(200, b'{"ok":true}')
        except StoreError as e:
            self.send(400, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode())
        except Exception as e:
            self.send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode())


APP_ID = "JW.ProgramBoard"


def center_on_display(n, w, h):
    r"""\\.\DISPLAY<n> 모니터의 작업영역 가운데에 w×h 창을 놓을 좌표를 돌려준다. 없으면 None."""
    import ctypes
    from ctypes import wintypes as wt

    class MI(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("rc", wt.RECT), ("wk", wt.RECT), ("fl", wt.DWORD), ("dev", wt.WCHAR * 32)]

    found = []

    def cb(hmon, dc, rc, lp):
        m = MI()
        m.cb = ctypes.sizeof(m)
        ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(m))
        if m.dev.endswith(f"DISPLAY{n}"):
            found.append(m.wk)
        return 1

    proc = ctypes.WINFUNCTYPE(ctypes.c_int, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)
    ctypes.windll.user32.EnumDisplayMonitors(None, None, proc(cb), 0)
    if not found:
        return None
    k = found[0]
    return (k.left + (k.right - k.left - w) // 2, k.top + (k.bottom - k.top - h) // 2)


class WinApi:
    TITLE = "정원유니어스 프로그램 보드"
    _shift = 0  # 패널을 펼치며 창을 왼쪽으로 민 만큼(접을 때 되돌린다)

    def set_pin(self, on):
        """항상 위 고정. pywebview 의 on_top 대신 윈도우 API 로 직접 바꾼다."""
        import ctypes
        u = ctypes.windll.user32
        u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        hwnd = u.FindWindowW(None, self.TITLE)
        if hwnd:
            u.SetWindowPos(hwnd, -1 if on else -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # NOSIZE|NOMOVE|NOACTIVATE
        return bool(on)

    def pick_image(self):
        """대표 이미지 파일 선택 창(바탕화면에서 시작). 고른 파일을 dataURL 로 돌려주고, 취소하면 빈 문자열."""
        import base64, mimetypes, webview
        win = getattr(self, "_window", None)
        if not win:
            return ""
        got = win.create_file_dialog(webview.OPEN_DIALOG, directory=os.path.join(os.path.expanduser("~"), "Desktop"),
                                     file_types=("이미지 파일 (*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp;*.ico)",))
        if not got:
            return ""
        path = got if isinstance(got, str) else got[0]
        with open(path, "rb") as f:
            return f"data:{mimetypes.guess_type(path)[0] or 'image/png'};base64," + base64.b64encode(f.read()).decode()

    def set_todo(self, on):
        """오늘의 할 일 패널을 펼치거나 접을 때 창을 패널 너비만큼 오른쪽으로 늘이고 줄인다.
        오른쪽에 자리가 없으면 왼쪽으로 밀어 화면 안에 둔다."""
        import ctypes
        from ctypes import wintypes as wt

        class MI(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("rc", wt.RECT), ("wk", wt.RECT), ("fl", wt.DWORD), ("dev", wt.WCHAR * 32)]

        u = ctypes.windll.user32
        u.FindWindowW.restype = ctypes.c_void_p
        u.MonitorFromWindow.restype = ctypes.c_void_p
        u.MonitorFromWindow.argtypes = [ctypes.c_void_p, wt.DWORD]
        u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        u.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        u.GetDpiForWindow.argtypes = [ctypes.c_void_p]
        u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        hwnd = u.FindWindowW(None, self.TITLE)
        if not hwnd:
            return False
        r = wt.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        dw = round(TODO_W * (u.GetDpiForWindow(hwnd) or 96) / 96)
        w, h = r.right - r.left, r.bottom - r.top
        flags = 0x0004 | 0x0010  # NOZORDER|NOACTIVATE
        if on:
            mi = MI()
            mi.cb = ctypes.sizeof(mi)
            u.GetMonitorInfoW(u.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))
            self._shift = max(0, min(r.right + dw - mi.wk.right, r.left - mi.wk.left))
            u.SetWindowPos(hwnd, None, r.left - self._shift, r.top, w + dw, h, flags)
        else:
            u.SetWindowPos(hwnd, None, r.left + self._shift, r.top, max(w - dw, 300), h, flags)
            self._shift = 0
        return bool(on)


def _board_api():
    """보드 창이 부르는 함수 모음. 오늘의 할 일(work_daily_todo)이 있으면 그 함수도 같은 창에서 부를 수 있게 합친다."""
    sys.path.insert(0, TODO_DIR)
    try:
        from app import Api as TodoApi
    except Exception:
        return WinApi()

    class BoardApi(WinApi, TodoApi):  # set_pin 은 보드 것이 우선
        def __init__(self):
            TodoApi.__init__(self)

        def _close(self):  # 할 일 앱의 창 위치 저장은 보드에서는 쓰지 않는다
            pass

        def quit(self):  # 할 일 패널의 '종료' 는 쓰지 않는다
            pass

    api = BoardApi()
    return api


def open_board():
    """전용 창(pywebview)으로 연다. board.ico 를 창 아이콘으로 써서 작업표시줄에서 선명하게 보인다."""
    url = f"http://127.0.0.1:{PORT}/"
    try:
        import ctypes, webview
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        pos = center_on_display(1, 903, 1008) or (None, None)  # 1번 모니터 가운데
        api = _board_api()
        api._window = win = webview.create_window("정원유니어스 프로그램 보드", url, width=903, height=1008, x=pos[0], y=pos[1], js_api=api)
        webview.start(icon=os.path.join(HERE, "board.ico"))
    except Exception:
        webbrowser.open(url)


if __name__ == "__main__":
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError:  # 이미 실행 중이면 창만 연다
        open_board()
        sys.exit(0)
    if "--no-open" in sys.argv:
        srv.serve_forever()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    open_board()  # 창을 닫으면 서버도 함께 종료
