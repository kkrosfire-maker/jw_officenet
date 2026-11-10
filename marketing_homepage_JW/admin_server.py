"""정원유니어스 홈페이지 관리자 서버 (내 PC 전용, 127.0.0.1)

실행: admin_start.bat  ->  http://127.0.0.1:8787/admin.html
- 글 등록/수정/삭제 -> news/posts.json 저장, news/posts.js 자동 재생성
- 썸네일 -> assets/news/<id>_<시각>.jpg|png 로 저장 (교체 시 이전 파일 삭제, 브라우저 캐시 방지)
"""
import base64
import http.server
import json
import os
import re
import socketserver
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
NEWS = os.path.join(ROOT, "news")
IMG_DIR = os.path.join(ROOT, "assets", "news")
PJSON = os.path.join(NEWS, "posts.json")
PJS = os.path.join(NEWS, "posts.js")
PORT = 8787
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATA_URL_RE = re.compile(r"^data:image/(jpeg|png|webp);base64,(.+)$", re.S)


def load():
    if not os.path.exists(PJSON):
        return []
    with open(PJSON, encoding="utf-8") as f:
        return json.load(f)


def save(posts):
    os.makedirs(NEWS, exist_ok=True)
    with open(PJSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    with open(PJS, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.POSTS = " + json.dumps(posts, ensure_ascii=False) + ";\n")


def save_image(pid, data_url):
    m = DATA_URL_RE.match(data_url or "")
    if not m:
        raise ValueError("썸네일 이미지 형식이 올바르지 않습니다(jpg/png/webp).")
    raw = base64.b64decode(m.group(2))
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("썸네일이 너무 큽니다(8MB 초과).")
    ext = "png" if m.group(1) == "png" else ("webp" if m.group(1) == "webp" else "jpg")
    os.makedirs(IMG_DIR, exist_ok=True)
    for old in os.listdir(IMG_DIR):  # 같은 id의 이전 썸네일 정리
        if old.startswith(f"{pid}.") or old.startswith(f"{pid}_"):
            os.remove(os.path.join(IMG_DIR, old))
    name = f"{pid}_{int(time.time())}.{ext}"
    with open(os.path.join(IMG_DIR, name), "wb") as f:
        f.write(raw)
    return f"assets/news/{name}"


def clean(d):
    title = str(d.get("title", "")).strip()
    date = str(d.get("date", "")).strip()
    summary = str(d.get("summary", "")).strip()
    body = str(d.get("body", "")).strip()
    link = str(d.get("link", "")).strip()
    if not title or len(title) > 200:
        raise ValueError("제목은 1~200자로 입력해 주세요.")
    if not DATE_RE.match(date):
        raise ValueError("날짜 형식이 올바르지 않습니다(YYYY-MM-DD).")
    if len(summary) > 500:
        raise ValueError("요약은 500자 이내로 입력해 주세요.")
    if len(body) > 20000:
        raise ValueError("본문이 너무 깁니다(20000자 초과).")
    if link and not re.match(r"^https?://", link, re.I):
        raise ValueError("원문 링크는 http:// 또는 https:// 로 시작해야 합니다.")
    return dict(title=title, date=date, summary=summary, body=body, link=link)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 12 * 1024 * 1024:
            raise ValueError("요청이 너무 큽니다.")
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def _pid(self):
        m = re.fullmatch(r"/api/posts/(\d+)", self.path.split("?")[0])
        return int(m.group(1)) if m else None

    def do_GET(self):
        if self.path.split("?")[0] == "/api/posts":
            return self._json(200, load())
        super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/posts":
            return self._json(404, {"error": "not found"})
        try:
            d = self._body()
            post = clean(d)
            posts = load()
            pid = max([p["id"] for p in posts], default=0) + 1
            post["thumb"] = save_image(pid, d.get("thumb_data"))
            post["id"] = pid
            posts.append(post)
            save(posts)
            self._json(200, post)
        except Exception as e:  # noqa: BLE001
            self._json(400, {"error": str(e)})

    def do_PUT(self):
        pid = self._pid()
        if pid is None:
            return self._json(404, {"error": "not found"})
        try:
            d = self._body()
            fields = clean(d)
            posts = load()
            cur = next((p for p in posts if p["id"] == pid), None)
            if not cur:
                return self._json(404, {"error": "글을 찾을 수 없습니다."})
            cur.update(fields)
            if d.get("thumb_data"):
                cur["thumb"] = save_image(pid, d["thumb_data"])
            save(posts)
            self._json(200, cur)
        except Exception as e:  # noqa: BLE001
            self._json(400, {"error": str(e)})

    def do_DELETE(self):
        pid = self._pid()
        if pid is None:
            return self._json(404, {"error": "not found"})
        posts = load()
        cur = next((p for p in posts if p["id"] == pid), None)
        if not cur:
            return self._json(404, {"error": "글을 찾을 수 없습니다."})
        posts = [p for p in posts if p["id"] != pid]
        if cur.get("thumb", "").startswith("assets/news/"):  # 관리자가 올린 이미지만 삭제
            fp = os.path.join(ROOT, cur["thumb"].replace("/", os.sep))
            if os.path.isfile(fp):
                os.remove(fp)
        save(posts)
        self._json(200, {"ok": True})


if __name__ == "__main__":
    if "--build" in sys.argv:  # posts.json -> posts.js 만 재생성
        save(load())
        print("built news/posts.js")
        sys.exit(0)
    socketserver.ThreadingTCPServer.allow_reuse_address = False  # Windows 에서 포트 겹침 방지
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler) as srv:
        print(f"Admin server: http://127.0.0.1:{PORT}/admin.html  (Ctrl+C to stop)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
