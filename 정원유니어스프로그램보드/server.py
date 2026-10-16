"""정원유니어스 프로그램 보드 - 로컬 실행기.
index.html 을 서빙하고, 카드 클릭 시 programs.json 에 등록된 프로그램만 실행한다."""
import json, os, subprocess, sys, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765
ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}


def load():
    with open(os.path.join(HERE, "programs.json"), encoding="utf-8") as f:
        return json.load(f)


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
        allowed = path == "/index.html" or path.startswith("/assets/")
        if not (allowed and full.startswith(HERE) and os.path.isfile(full)):
            return self.send(404)
        ext = os.path.splitext(full)[1].lower()
        ctype = {".html": "text/html; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg"}.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            self.send(200, f.read(), ctype)

    def do_POST(self):
        if urlparse(self.path).path != "/api/launch" or self.headers.get("Origin") not in ORIGINS:
            return self.send(403)
        pid = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        prog = next((p for p in load()["programs"] if p["id"] == pid), None)
        if not prog:
            return self.send(404, b'{"ok":false,"error":"unknown"}')
        try:
            launch(prog)
            self.send(200, b'{"ok":true}')
        except Exception as e:
            self.send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode())


def open_board():
    url = f"http://127.0.0.1:{PORT}/"
    for chrome in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                   r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"):
        if os.path.exists(chrome):
            subprocess.Popen([chrome, f"--app={url}", "--window-size=1180,860"])
            return
    webbrowser.open(url)


if __name__ == "__main__":
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError:  # 이미 실행 중이면 창만 연다
        open_board()
        sys.exit(0)
    if "--no-open" not in sys.argv:
        open_board()
    srv.serve_forever()
