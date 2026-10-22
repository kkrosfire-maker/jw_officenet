"""정원유니어스 프로그램 보드 - 로컬 실행기.
index.html 을 서빙하고, 카드 클릭 시 programs.json 에 등록된 프로그램만 실행한다."""
import json, os, subprocess, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from icons import icon_for, suggest
from store import StoreError, apply

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765
ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}


def load():
    with open(os.path.join(HERE, "programs.json"), encoding="utf-8") as f:
        return json.load(f)


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
    subprocess.Popen(cmd, cwd=p.get("cwd") or os.path.dirname(path),
                     creationflags=0x00000008 | 0x00000200, close_fds=True)  # DETACHED | NEW_GROUP


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
        if path == "/api/programs":
            return self.send(200, json.dumps(load(), ensure_ascii=False).encode())
        if path == "/":
            path = "/index.html"
        elif path == "/favicon.ico":
            path = "/assets/icons/officeboard.png"
        full = os.path.normpath(os.path.join(HERE, path.lstrip("/")))
        allowed = path in ("/index.html", "/manifest.json") or path.startswith("/assets/")
        if not (allowed and full.startswith(HERE) and os.path.isfile(full)):
            return self.send(404)
        ext = os.path.splitext(full)[1].lower()
        ctype = {".html": "text/html; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg", ".json": "application/manifest+json"}.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            self.send(200, f.read(), ctype)

    def do_POST(self):
        route = urlparse(self.path).path
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
            save(apply(load(), json.loads(body), icon_for))
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

    def set_pin(self, on):
        """항상 위 고정. pywebview 의 on_top 대신 윈도우 API 로 직접 바꾼다."""
        import ctypes
        u = ctypes.windll.user32
        u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        hwnd = u.FindWindowW(None, self.TITLE)
        if hwnd:
            u.SetWindowPos(hwnd, -1 if on else -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # NOSIZE|NOMOVE|NOACTIVATE
        return bool(on)


def open_board():
    """전용 창(pywebview)으로 연다. board.ico 를 창 아이콘으로 써서 작업표시줄에서 선명하게 보인다."""
    url = f"http://127.0.0.1:{PORT}/"
    todo = os.path.join(os.path.dirname(HERE), "work_daily_todo", "app.py")
    if os.path.exists(todo):  # 오늘의 할 일 앱을 보드 옆에 같이 띄운다
        subprocess.Popen([sys.executable, todo, "--dock"], cwd=os.path.dirname(todo), creationflags=0x08000000)
    try:
        import ctypes, webview
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        pos = center_on_display(1, 903, 1008) or (None, None)  # 1번 모니터 가운데
        webview.create_window("정원유니어스 프로그램 보드", url, width=903, height=1008, x=pos[0], y=pos[1], js_api=WinApi())
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
