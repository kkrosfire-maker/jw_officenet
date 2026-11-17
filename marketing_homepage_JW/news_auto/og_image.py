"""원문 기사의 대표 이미지(og:image)를 찾아 Supabase Storage(news-thumbs)에 올린다. (자동 등록용)

api/_og.js 와 같은 방식이다: 구글 뉴스 중계 주소는 실제 기사 주소로 풀고, 사설 IP 는 막는다.
Pillow 가 있으면 가로 1000px JPEG 로 줄여 올리고, 없으면 원본이 1.5MB 이하일 때만 그대로 올린다.
실패하면 None 을 돌려주므로 호출하는 쪽이 기본 썸네일로 대신하면 된다.
"""
import html as htmllib
import io
import ipaddress
import json
import random
import re
import socket
import string
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
MAX_HTML = 2 * 1024 * 1024
MAX_IMG = 6 * 1024 * 1024
RAW_LIMIT = 1_500_000  # Pillow 없이 올릴 때 허용하는 원본 크기


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _assert_public(url):
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("http/https 주소만 가능")
    for info in socket.getaddrinfo(u.hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("허용되지 않는 주소")


def _get(url, accept, limit, headers=None):
    """리다이렉트를 한 단계씩 따라가며 가져온다. (최종주소, 응답헤더, 본문) 반환."""
    for _ in range(5):
        _assert_public(url)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept,
                                                   "Accept-Language": "ko,en;q=0.8", **(headers or {})})
        try:
            with _opener.open(req, timeout=15) as r:
                data = r.read(limit + 1)
                if len(data) > limit:
                    raise ValueError("파일이 너무 큼")
                return url, r.headers, data
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location")
            if 300 <= e.code < 400 and loc:
                url = urllib.parse.urljoin(url, loc)
                continue
            raise
    raise ValueError("리다이렉트가 너무 많음")


def resolve_google_news(url):
    """news.google.com/rss/articles/... -> 실제 기사 주소. 못 풀면 ValueError."""
    gid = urllib.parse.urlparse(url).path.split("/articles/")[1].split("/")[0]
    _, _, page = _get("https://news.google.com/articles/" + urllib.parse.quote(gid), "text/html", MAX_HTML)
    page = page.decode("utf-8", "replace")
    sg = re.search(r'data-n-a-sg="([^"]+)"', page)
    ts = re.search(r'data-n-a-ts="([^"]+)"', page)
    if not sg or not ts:
        raise ValueError("구글 뉴스 서명을 찾지 못함")
    inner = json.dumps(["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None,
                                         None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                        gid, int(ts.group(1)), sg.group(1)])
    body = urllib.parse.urlencode({"f.req": json.dumps([[["Fbv4je", inner, None, "generic"]]])}).encode()
    req = urllib.request.Request("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body, headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    with urllib.request.urlopen(req, timeout=15) as r:
        text = r.read().decode("utf-8", "replace")
    try:
        outer = json.loads(text[text.index("["):].split("\n")[0])
        real = json.loads(next(x for x in outer if x[1] == "Fbv4je")[2])[1]
    except Exception:
        real = ""
    if not re.match(r"https?://", real or ""):
        raise ValueError("실제 기사 주소를 찾지 못함")
    return real


def _find_images(page_html, base):
    want = ["og:image:secure_url", "og:image", "twitter:image", "twitter:image:src"]
    found = {}
    for m in re.findall(r"<meta\b[^>]*>", page_html, re.I):
        k = re.search(r'\b(?:property|name)\s*=\s*["\']([^"\']+)["\']', m, re.I)
        v = re.search(r'\bcontent\s*=\s*["\']([^"\']*)["\']', m, re.I)
        if k and v and k.group(1).lower() in want:
            found.setdefault(k.group(1).lower(), v.group(1))
    out = [found[k] for k in want if k in found]
    link = re.search(r'<link\b[^>]*\brel\s*=\s*["\']image_src["\'][^>]*\bhref\s*=\s*["\']([^"\']+)["\']', page_html, re.I)
    if link:
        out.append(link.group(1))
    return [urllib.parse.urljoin(base, htmllib.unescape(v.strip())) for v in out]


def fetch_article_image(link):
    """(바이트, content-type) 반환. 실패 시 예외."""
    if urllib.parse.urlparse(link).hostname == "news.google.com":
        link = resolve_google_news(link)
    page_url, _, page = _get(link, "text/html,application/xhtml+xml", MAX_HTML)
    if urllib.parse.urlparse(page_url).hostname == "news.google.com":
        raise ValueError("구글 뉴스 페이지에 머물러 이미지를 찾지 못함")
    last = None
    for cand in _find_images(page.decode("utf-8", "replace"), page_url):
        try:
            _, hdr, data = _get(cand, "image/*,*/*;q=0.5", MAX_IMG)
            ctype = (hdr.get("Content-Type") or "").split(";")[0].strip().lower()
            if re.match(r"^image/(jpeg|png|webp|gif)$", ctype):
                return data, ctype
            last = ValueError("이미지 형식이 아님")
        except Exception as e:  # 다음 후보
            last = e
    raise last or ValueError("대표 이미지가 없음")


def _to_jpeg(data, ctype):
    """(바이트, 'image/jpeg'). Pillow 없으면 작은 jpeg/png 만 원본 그대로."""
    try:
        from PIL import Image
    except ImportError:
        if len(data) <= RAW_LIMIT:
            return data, ctype
        raise ValueError("Pillow 없이 올리기엔 이미지가 큼")
    im = Image.open(io.BytesIO(data))
    im = im.convert("RGB")
    if im.width > 1000:
        im = im.resize((1000, round(im.height * 1000 / im.width)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=86)
    return buf.getvalue(), "image/jpeg"


def upload_thumb(link, supabase_url, secret_key):
    """원문 이미지를 받아 news-thumbs 에 올리고 공개 URL 을 돌려준다. 실패하면 None."""
    try:
        data, ctype = _to_jpeg(*fetch_article_image(link))
        ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}[ctype]
        name = f"{int(time.time() * 1000)}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}.{ext}"
        req = urllib.request.Request(f"{supabase_url}/storage/v1/object/news-thumbs/{name}", data=data, method="POST",
                                     headers={"apikey": secret_key, "Authorization": f"Bearer {secret_key}",
                                              "Content-Type": ctype, "x-upsert": "true"})
        with urllib.request.urlopen(req, timeout=30):
            pass
        return f"{supabase_url}/storage/v1/object/public/news-thumbs/{name}"
    except Exception as e:
        print(f"  (이미지 가져오기 실패, 기본 썸네일 사용) {type(e).__name__}: {e}")
        return None


def check_image(link):
    """dry-run 용: 업로드 없이 가져올 수 있는지만 확인. (바이트 수, 형식) 또는 None."""
    try:
        data, ctype = _to_jpeg(*fetch_article_image(link))
        return len(data), ctype
    except Exception as e:
        print(f"  (이미지 가져오기 실패) {type(e).__name__}: {e}")
        return None
