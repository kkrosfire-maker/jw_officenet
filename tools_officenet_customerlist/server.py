# 로컬 도우미 서버: 화면(index.html) 제공 + docx를 바탕화면에 저장 + Word로 PDF 변환
import os, re, sys, subprocess, json, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import roomlib
import officeboard
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("JW_PORT", "8771"))
def real_desktop():
    """이 PC의 실제 바탕화면 경로 (OneDrive 로 옮겨진 PC 도 처리)"""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0 and os.path.isdir(buf.value): return buf.value
    except Exception: pass
    d = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
    return d if os.path.isdir(d) else os.path.expanduser("~")
DESKTOP = real_desktop()
LOCK = threading.Lock()   # Word 변환은 한 번에 하나씩

def safe(name):
    name = re.sub(r'[\/:*?"<>|\r\n]+', "", name).strip().rstrip(".")
    return name or "전대차계약서"

def free_path(base, ext):
    p = os.path.join(DESKTOP, base + ext); n = 2
    while True:
        try:
            if not os.path.exists(p): return p
            with open(p, "ab"): pass          # 다른 프로그램이 열어둔 파일이면 PermissionError
            return p
        except PermissionError:
            p = os.path.join(DESKTOP, f"{base}({n}){ext}"); n += 1

ThreadingHTTPServer.allow_reuse_address = False   # Windows에서 중복 실행(포트 공유) 방지
class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=HERE, **k)
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header("Cache-Control", "no-store"); super().end_headers()
    def reply(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/api/ping": return self.reply(200, {"ok": True, "desktop": DESKTOP, "dir": HERE})
        if u.path == "/api/quit":      # 다른 폴더(옛 버전)의 서버가 새 서버에게 자리를 비켜줄 때 사용
            self.reply(200, {"ok": True}); threading.Timer(0.3, lambda: os._exit(0)).start(); return
        if u.path == "/api/pick":
            try:
                kind = "pdf" if q.get("kind", ["pdf"])[0] == "pdf" else "docx"
                r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(HERE, "pick_save.py"), DESKTOP, safe(q.get("name", [""])[0]), kind],
                                   capture_output=True, timeout=600, creationflags=0x08000000)
                path = r.stdout.decode("utf-8", "replace").strip()
                if r.returncode != 0: return self.reply(200, {"ok": False, "error": (r.stderr or b"").decode("utf-8", "replace")[-200:]})
                return self.reply(200, {"ok": True, "path": path})
            except Exception as e:
                return self.reply(200, {"ok": False, "error": str(e)})
        if u.path == "/api/open-xlsx":
            try:
                if not os.path.exists(roomlib.XLSX): return self.reply(200, {"ok": False, "error": "엑셀 파일을 찾을 수 없어요: " + roomlib.XLSX})
                os.startfile(roomlib.XLSX)
                return self.reply(200, {"ok": True, "path": roomlib.XLSX})
            except Exception as e:
                return self.reply(200, {"ok": False, "error": str(e)})
        if u.path in ("/api/room", "/api/room-check"):
            try:
                st = roomlib.read_master()
                if u.path == "/api/room": return self.reply(200, {"ok": True, "room": roomlib.next_room(st["rooms"], q.get("corp", ["0"])[0] == "1")})
                return self.reply(200, {"ok": True, "room": roomlib.resolve_room(q.get("room", [""])[0], st["active"])})
            except Exception as e:
                return self.reply(200, {"ok": False, "error": "고객list 엑셀을 읽지 못했어요: " + str(e)})
        return super().do_GET()
    def do_POST(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/api/register":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
                act = body.pop("action", "check")
                with LOCK: res = {"check": roomlib.check, "insert": roomlib.insert, "update": roomlib.update, "remove": roomlib.remove}[act](body)
                return self.reply(200, dict(res, ok=True))
            except Exception as e:
                return self.reply(500, {"ok": False, "error": "고객list 처리 실패: " + str(e)})
        if u.path in ("/api/ob", "/api/ob-password"):
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
                if u.path == "/api/ob-password":
                    officeboard.save_password(body.get("password", ""))
                    officeboard.Client().login(wake_secs=100)           # 맞는 비밀번호인지 바로 확인
                    return self.reply(200, {"ok": True})
                act = body.pop("action", "check")
                with LOCK: res = {"check": officeboard.check, "insert": officeboard.insert, "update": officeboard.update, "remove": officeboard.remove}[act](body)
                return self.reply(200, dict(res, ok=True))
            except officeboard.NeedPassword as e:
                return self.reply(200, {"ok": False, "needPassword": True, "error": str(e)})
            except Exception as e:
                return self.reply(200, {"ok": False, "error": "officeboard 처리 실패: " + str(e)})
        if u.path not in ("/api/docx", "/api/pdf"): return self.reply(404, {"ok": False, "error": "없는 주소"})
        try:
            data = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            base = safe(unquote(q.get("name", [""])[0]))
            chosen = q.get("path", [""])[0]
            if chosen:
                chosen = os.path.normpath(chosen)
                if not os.path.isdir(os.path.dirname(chosen)): return self.reply(500, {"ok": False, "error": "저장 폴더가 없어요: " + os.path.dirname(chosen)})
                docx = os.path.splitext(chosen)[0] + ".docx"
            else:
                docx = free_path(base, ".docx")
            with open(docx, "wb") as f: f.write(data)
            res = {"ok": True, "docx": docx}
            if u.path == "/api/pdf":
                with LOCK:
                    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                        os.path.join(HERE, "docx_to_pdf.ps1"), docx],
                                       capture_output=True, timeout=180, creationflags=0x08000000)
                pdf = os.path.splitext(docx)[0] + ".pdf"
                if r.returncode != 0 or not os.path.exists(pdf):
                    err = (r.stderr or r.stdout).decode("utf-8", "replace")[-300:]
                    return self.reply(500, {"ok": False, "docx": docx, "error": "Word PDF 변환 실패: " + err})
                res["pdf"] = pdf
            self.reply(200, res)
        except Exception as e:
            self.reply(500, {"ok": False, "error": str(e)})

def _stop_old():
    """같은 포트에 다른 폴더의 서버가 떠 있으면(옛 버전) 종료시킨다. 같은 폴더면 False."""
    import urllib.request, time
    try:
        j = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ping", timeout=2))
        if os.path.normcase(j.get("dir", "")) == os.path.normcase(HERE): return False
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/quit", timeout=2).read(); time.sleep(1.2); return True
    except Exception:
        return False

if __name__ == "__main__":
    for attempt in range(2):
        try:
            ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
        except OSError:
            if attempt == 0 and _stop_old(): continue
            sys.exit(0)   # 이미 실행 중
