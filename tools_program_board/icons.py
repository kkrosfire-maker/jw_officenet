"""프로그램 아이콘·이름 후보 만들기. 웹은 사이트에서, PC 프로그램(exe·lnk·bat)은 파일 자체 아이콘에서 가져온다.
store.apply 에는 icon_for 를 아이콘 어댑터로 넘긴다."""
import os, subprocess
from urllib.parse import urlparse

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons")


def suggest(path):
    """고른 파일에서 이름·설명 후보를 만든다. exe 의 버전 정보(제품명·파일 설명)를 쓰고, 없으면 파일명."""
    import ctypes
    stem = os.path.splitext(os.path.basename(path))[0]
    target = path
    if path.lower().endswith(".lnk"):  # 바로가기는 가리키는 프로그램의 정보를 본다
        try:
            ps = ("(New-Object -ComObject WScript.Shell).CreateShortcut($env:PB_LNK).TargetPath")
            t = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                               encoding="utf-8", env={**os.environ, "PB_LNK": path}, creationflags=0x08000000,
                               timeout=10).stdout.strip()
            if t and os.path.exists(t):
                target = t
        except Exception:
            pass
    info = {}
    try:
        ver = ctypes.windll.version
        ver.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p]
        ver.GetFileVersionInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
        ver.VerQueryValueW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p]
        size = ver.GetFileVersionInfoSizeW(target, None)
        if size:
            buf = ctypes.create_string_buffer(size)
            ver.GetFileVersionInfoW(target, 0, size, buf)
            tr, n = ctypes.c_void_p(), ctypes.c_uint()
            if ver.VerQueryValueW(buf, r"\VarFileInfo\Translation", ctypes.byref(tr), ctypes.byref(n)) and n.value >= 4:
                lang, cp = ctypes.cast(tr, ctypes.POINTER(ctypes.c_ushort * 2)).contents
                for key in ("ProductName", "FileDescription"):
                    v, m = ctypes.c_void_p(), ctypes.c_uint()
                    if ver.VerQueryValueW(buf, rf"\StringFileInfo\{lang:04x}{cp:04x}\{key}", ctypes.byref(v), ctypes.byref(m)) and m.value:
                        info[key] = ctypes.wstring_at(v.value).strip()
    except Exception:
        pass
    name = info.get("FileDescription") or info.get("ProductName") or stem
    desc = info.get("ProductName", "")
    if "operating system" in desc.lower() or name.lower() in desc.lower() or desc.lower() in name.lower():
        desc = ""  # 윈도우 기본 프로그램의 'Microsoft Windows Operating System' 같은 군더더기, 이름과 겹치는 설명은 뺀다
    return name, desc


def icon_for(p):
    """store.apply 에 주입하는 아이콘 어댑터: 웹은 사이트에서, PC 프로그램은 파일 자체 아이콘에서."""
    return fetch_icon(p) if p["type"] == "url" else fetch_exe_icon(p)


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
    img.save(os.path.join(ICON_DIR, p["id"] + ".png"))
    return f"icons/{p['id']}.png"


SCRIPT_EXTS = (".bat", ".cmd", ".ps1", ".vbs", ".py", ".pyw")
_SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "env", "__pycache__", "site-packages", ".idea", ".vscode"}


def _script_refs(path):
    """스크립트 본문과, 그 스크립트가 실행하는 .py 본문에서 언급된 파일 이름들(소문자)을 모은다."""
    import re
    names, texts, folder = set(), [], os.path.dirname(path)
    try:
        # bat 의 %~dp0(자기 폴더)는 경로 구분자로 바꿔 둔다: "%~dp0app.py" → "\app.py"
        texts.append(re.sub(r"%~dp0", "\\\\", open(path, encoding="utf-8", errors="ignore").read(), flags=re.I))
    except OSError:
        pass
    for t in list(texts):  # bat 이 띄우는 app.py 같은 파일도 한 단계 들여다본다
        for m in re.findall(r"[\w\-.가-힣]+\.pyw?\b", t):
            f = os.path.join(folder, os.path.basename(m.strip()))
            if os.path.isfile(f) and f != path:
                try:
                    texts.append(open(f, encoding="utf-8", errors="ignore").read()[:200_000])
                except OSError:
                    pass
    for t in texts:
        names |= {os.path.basename(m).lower() for m in re.findall(r"[\w\-.가-힣]+\.(?:ico|exe)\b", t, re.I)}
    return names


def find_folder_icon(path, max_depth=3, max_files=5000):
    """스크립트(bat 등)가 있는 폴더와 하위 폴더에서 쓸 만한 아이콘 파일을 찾는다.
    우선순위: 스크립트(또는 그 스크립트가 실행하는 .py)에 이름이 나오는 .ico → 이름이 같은 .ico →
    app/icon/logo 같은 이름 → 얕은 폴더. 없으면 스크립트가 실행하는 .exe. 아무것도 없으면 ''."""
    root = os.path.dirname(os.path.abspath(path))
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    refs = _script_refs(path)
    icos, exes, seen = [], [], 0
    for cur, dirs, files in os.walk(root):
        depth = os.path.relpath(cur, root).count(os.sep) + (cur != root)
        dirs[:] = [d for d in dirs if d.lower() not in _SKIP_DIRS and not d.startswith(".")] if depth < max_depth else []
        for f in files:
            seen += 1
            low = f.lower()
            if low.endswith(".ico"):
                icos.append((depth, os.path.join(cur, f)))
            elif low.endswith(".exe") and low in refs:
                exes.append((depth, os.path.join(cur, f)))
        if seen > max_files:
            break

    def rank(item):
        depth, f = item
        name = os.path.basename(f).lower()
        base = os.path.splitext(name)[0]
        return (name not in refs, base != stem, base not in ("app", "icon", "logo", "main"), depth, name)

    if icos:
        return min(icos, key=rank)[1]
    return min(exes)[1] if exes else ""


def _save_square(img, p):
    """투명 여백을 자르고 가운데 맞춘 256px 정사각 PNG 로 저장한다."""
    from PIL import Image
    img = img.convert("RGBA")
    box = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if not box:
        return ""
    img = img.crop(box)
    w, h = img.size
    side = max(w, h)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(img, ((side - w) // 2, (side - h) // 2))
    sq.resize((256, 256), Image.LANCZOS).save(os.path.join(ICON_DIR, p["id"] + ".png"))
    return f"icons/{p['id']}.png"


def _ico_file_icon(ico, p):
    """.ico 파일에서 가장 큰 크기를 골라 저장한다."""
    from PIL import Image
    img = Image.open(ico)
    sizes = img.info.get("sizes")
    if sizes:
        img.size = max(sizes)
    img.load()
    return _save_square(img, p)


def fetch_exe_icon(p):
    """PC 프로그램(exe·lnk·bat) 자체 아이콘을 가져와 assets/icons/<id>.png (256px 정사각)로 저장하고
    상대경로를 돌려준다. bat 같은 스크립트는 윈도우 기본 아이콘밖에 없으니, 폴더(하위 포함)에 있는
    .ico 나 스크립트가 실행하는 .exe 의 아이콘을 먼저 쓴다."""
    path = p.get("path", "")
    if not os.path.exists(path):
        return ""
    if path.lower().endswith(SCRIPT_EXTS):
        try:
            found = find_folder_icon(path)
            if found.lower().endswith(".ico"):
                rel = _ico_file_icon(found, p)
                if rel:
                    return rel
            elif found:
                return _shell_icon(found, p)
        except Exception:
            pass
    return _shell_icon(path, p)


def _shell_icon(path, p):
    """윈도우 탐색기와 같은 방식으로 파일 아이콘을 가져온다."""
    import ctypes
    from ctypes import wintypes as wt
    from PIL import Image
    sh, u32, g32 = ctypes.windll.shell32, ctypes.windll.user32, ctypes.windll.gdi32
    ctypes.windll.ole32.CoInitialize(None)

    class SHFILEINFOW(ctypes.Structure):
        _fields_ = [("hIcon", wt.HICON), ("iIcon", ctypes.c_int), ("dwAttributes", wt.DWORD),
                    ("szDisplayName", wt.WCHAR * 260), ("szTypeName", wt.WCHAR * 80)]

    class GUID(ctypes.Structure):
        _fields_ = [("a", wt.DWORD), ("b", wt.WORD), ("c", wt.WORD), ("d", ctypes.c_ubyte * 8)]

    info = SHFILEINFOW()
    sh.SHGetFileInfoW.argtypes = [wt.LPCWSTR, wt.DWORD, ctypes.c_void_p, wt.UINT, wt.UINT]
    if not sh.SHGetFileInfoW(path, 0, ctypes.byref(info), ctypes.sizeof(info), 0x4000):  # SYSICONINDEX
        return ""
    iid = GUID(0x46EB5926, 0x582E, 0x4017, (ctypes.c_ubyte * 8)(0x9F, 0xDF, 0xE8, 0x99, 0x8D, 0xAA, 0x09, 0x50))
    hicon, size = None, 256
    for shil, size in ((4, 256), (2, 48)):  # JUMBO(256) → 안 되면 EXTRALARGE(48)
        il = ctypes.c_void_p()
        if sh.SHGetImageList(shil, ctypes.byref(iid), ctypes.byref(il)) == 0 and il.value:
            vt = ctypes.cast(ctypes.cast(il, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
            get_icon = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int, wt.UINT,
                                          ctypes.POINTER(wt.HICON))(vt[10])  # IImageList::GetIcon
            h = wt.HICON()
            if get_icon(il, info.iIcon, 0x20, ctypes.byref(h)) == 0 and h.value:  # ILD_TRANSPARENT
                hicon = h
                break
    if hicon is None:
        return ""

    def render(bg):
        """bg 색 바탕에 아이콘을 그려 RGB 바이트를 돌려준다."""
        class BMIH(ctypes.Structure):
            _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                        ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                        ("biSizeImage", wt.DWORD), ("a", ctypes.c_long), ("b", ctypes.c_long),
                        ("c", wt.DWORD), ("d", wt.DWORD)]
        bmi = BMIH(ctypes.sizeof(BMIH), size, -size, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        hdc = g32.CreateCompatibleDC(None)
        g32.CreateDIBSection.restype = ctypes.c_void_p
        bmp = g32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        old = g32.SelectObject(hdc, ctypes.c_void_p(bmp))
        ctypes.memset(bits, bg, size * size * 4)
        u32.DrawIconEx(hdc, 0, 0, hicon, size, size, 0, None, 3)  # DI_NORMAL
        data = ctypes.string_at(bits, size * size * 4)
        g32.SelectObject(hdc, old)
        g32.DeleteObject(ctypes.c_void_p(bmp))
        g32.DeleteDC(hdc)
        return Image.frombuffer("RGBA", (size, size), data, "raw", "BGRA", 0, 1).convert("RGB")

    try:
        # 검정·흰 바탕에 각각 그려 차이로 투명도를 계산 → 오래된 아이콘도 투명 배경이 정확하다
        black, white = render(0), render(255)
    finally:
        u32.DestroyIcon(hicon)
    from PIL import ImageChops
    alpha = ImageChops.invert(ImageChops.subtract(white, black).convert("L"))
    img = black.copy()
    img.putalpha(alpha)
    # 투명도로 나눈 원래 색 복원(premultiplied → straight)
    px, a = img.load(), alpha.load()
    for y in range(size):
        for x in range(size):
            al = a[x, y]
            if 0 < al < 255:
                r, g, b, _ = px[x, y]
                px[x, y] = (min(255, r * 255 // al), min(255, g * 255 // al), min(255, b * 255 // al), al)
    return _save_square(img, p)  # 작은 아이콘이 왼쪽 위에 몰린 경우도 여백을 잘라 가운데로
