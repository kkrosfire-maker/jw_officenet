"""정원유니어스 프로그램 보드 - 로컬 실행기.
index.html 을 서빙하고, 카드 클릭 시 programs.json 에 등록된 프로그램만 실행한다."""
import json, os, subprocess, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

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
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         encoding="utf-8", creationflags=0x08000000).stdout.strip()
    return out.replace("/", "\\")


def clean(p):
    """화면에서 받은 항목을 저장 가능한 형태로 정리한다."""
    out = {"id": p.get("id", ""), "name": p["name"].strip(), "desc": p.get("desc", "").strip(),
           "group": p.get("group", "").strip() or "기타", "icon": p.get("icon", ""),
           "type": "url" if p.get("type") == "url" else "exe"}
    if out["type"] == "url":
        out["url"] = p.get("url", "").strip()
    else:
        out["path"] = p.get("path", "").strip()
        out["args"] = p.get("args", "")
        out["cwd"] = p.get("cwd", "") or os.path.dirname(out["path"])
    return out


def fetch_icon(p):
    """웹 항목의 대표 아이콘을 사이트에서 찾아 assets/icons/<id>.png (256px 정사각)로 저장하고 상대경로를 돌려준다.
    후보 중 가장 해상도 높은 정사각에 가까운 이미지를 고르고, 투명 여백은 잘라 카드를 꽉 채운다."""
    import html as htmlmod, io, re
    from urllib.parse import urljoin
    from urllib.request import Request, urlopen
    from PIL import Image
    url = p["url"] if "//" in p["url"] else "https://" + p["url"]
    host = urlparse(url).netloc
    if not host:
        return ""

    def get(u):
        return urlopen(Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=8).read()

    cands = []
    try:  # 페이지의 apple-touch-icon / icon / og:image
        page = get(url).decode("utf-8", "ignore")
        for m in re.finditer(r"<(?:link|meta)[^>]+>", page):
            tag = m.group(0)
            ref = re.search(r"""(?:href|content)=["']([^"']+)""", tag)
            if ref and re.search(r"""rel=["'][^"']*icon|og:image|twitter:image""", tag):
                cands.append(urljoin(url, htmlmod.unescape(ref.group(1))))
    except Exception:
        pass
    root = ".".join(host.split(".")[-2:])
    cands += [f"https://{host}/favicon.ico", f"https://www.google.com/s2/favicons?domain={host}&sz=64",
              f"https://www.google.com/s2/favicons?domain={root}&sz=64"]
    best = None  # (점수, 이미지)
    for c in dict.fromkeys(cands):
        try:
            img = Image.open(io.BytesIO(get(c))).convert("RGBA")
        except Exception:
            continue
        box = img.getchannel("A").getbbox()  # 투명 여백 제거
        if box:
            img = img.crop(box)
        w, h = img.size
        ratio = max(w, h) / max(1, min(w, h))
        score = min(w, h) / (1 if ratio <= 1.3 else ratio * 2)  # 정사각에 가까울수록, 클수록 우선
        if best is None or score > best[0]:
            best = (score, img)
    if best is None:
        return ""
    img = best[1]
    w, h = img.size
    if max(w, h) / min(w, h) <= 1.3:  # 거의 정사각: 꽉 채워서 자르기
        side = min(w, h)
        img = img.crop(((w - side) // 2, (h - side) // 2, (w - side) // 2 + side, (h - side) // 2 + side))
        img = img.resize((256, 256), Image.LANCZOS)
    else:  # 가로로 긴 이미지: 모서리 색을 배경으로 깔고 가운데에 맞춰 넣기
        bg = img.getpixel((0, 0))
        img.thumbnail((256, 256), Image.LANCZOS)
        out = Image.new("RGBA", (256, 256), bg if bg[3] else (255, 255, 255, 255))
        out.paste(img, ((256 - img.width) // 2, (256 - img.height) // 2), img)
        img = out
    img.save(os.path.join(HERE, "assets", "icons", p["id"] + ".png"))
    return f"icons/{p['id']}.png"


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
            return self.send(200, json.dumps({"path": browse()}, ensure_ascii=False).encode())
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
        """{action: add|update|delete, program|id} 로 programs.json 을 고친다."""
        try:
            req = json.loads(body)
            cfg = load()
            progs = cfg["programs"]
            act = req["action"]
            if act == "delete":
                cfg["programs"] = [p for p in progs if p["id"] != req["id"]]
            else:
                p = clean(req["program"])
                if not p["name"] or not (p.get("url") or p.get("path")):
                    return self.send(400, '{"ok":false,"error":"이름과 경로(주소)는 필수예요"}'.encode())
                if act == "add":
                    n = 1
                    while f"custom{n}" in {x["id"] for x in progs}:
                        n += 1
                    p["id"] = f"custom{n}"
                    if p["type"] == "url":
                        p["icon"] = fetch_icon(p)
                    progs.append(p)
                else:
                    i = next(i for i, x in enumerate(progs) if x["id"] == p["id"])
                    p["icon"] = progs[i].get("icon", "")
                    if p["type"] == "url" and (not p["icon"] or progs[i].get("url") != p["url"]) and p["id"].startswith("custom"):
                        p["icon"] = fetch_icon(p) or p["icon"]
                    progs[i] = p
            save(cfg)
            self.send(200, b'{"ok":true}')
        except Exception as e:
            self.send(500, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode())


APP_ID = "JW.ProgramBoard"


def open_board():
    """전용 창(pywebview)으로 연다. board.ico 를 창 아이콘으로 써서 작업표시줄에서 선명하게 보인다."""
    url = f"http://127.0.0.1:{PORT}/"
    try:
        import ctypes, webview
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        webview.create_window("정원유니어스 프로그램 보드", url, width=903, height=1008)
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
