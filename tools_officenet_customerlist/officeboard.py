# officeboard(Render) 연동: 로그인 → /data 읽기 → 비상주 고객 1건 추가/수정 → /data 저장 → 다시 읽어 확인
import json, os, re, time, urllib.request, urllib.parse, urllib.error, http.cookiejar

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.environ.get("JW_OB_CONFIG") or os.path.join(HERE, "officeboard_config.json")   # 비밀번호가 들어 있어 git에 올리지 않음(.gitignore)
DEFAULT_URL = "https://jw-officenet.onrender.com"

class NeedPassword(Exception): pass

def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f: c = json.load(f)
    except (OSError, ValueError): c = {}
    c["url"] = os.environ.get("JW_OB_URL") or c.get("url") or DEFAULT_URL; c.setdefault("password", "")
    return c

def save_password(pw):
    c = load_config(); c["password"] = pw
    with open(CONFIG, "w", encoding="utf-8") as f: json.dump(c, f, ensure_ascii=False, indent=2)

class Client:
    def __init__(self):
        c = load_config(); self.base = c["url"].rstrip("/"); self.pw = c["password"]
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _req(self, path, data=None, headers=None, timeout=60):
        rq = urllib.request.Request(self.base + path, data=data, headers=headers or {})
        return self.op.open(rq, timeout=timeout)

    def login(self, wake_secs=150):
        if not self.pw: raise NeedPassword("officeboard 비밀번호가 아직 없어요.")
        end = time.time() + wake_secs; last = ""
        while time.time() < end:
            try:
                body = urllib.parse.urlencode({"password": self.pw}).encode()
                r = self._req("/login", body, {"Content-Type": "application/x-www-form-urlencoded"})
                url = r.geturl(); txt = r.read(300).decode("utf-8", "replace")
                if "/login" in url and "error" in url: raise NeedPassword("officeboard 비밀번호가 맞지 않아요.")
                if "WAKING" in txt.upper() or "APPLICATION LOADING" in txt.upper():   # Render 슬립 해제 대기
                    last = "서버가 깨어나는 중"; time.sleep(5); continue
                return
            except NeedPassword: raise
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = str(e); time.sleep(5)
        raise RuntimeError("officeboard 서버에 연결하지 못했어요 (" + last + ")")

    def get_data(self):
        for _ in range(6):
            r = self._req("/data")
            if "application/json" in (r.headers.get("Content-Type") or ""):
                return json.loads(r.read().decode("utf-8"))
            time.sleep(5)
        raise RuntimeError("officeboard 데이터를 읽지 못했어요 (서버가 깨어나는 중일 수 있어요)")

    def put_data(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        r = self._req("/data", body, {"Content-Type": "application/json"})
        if r.status != 204: raise RuntimeError("officeboard 저장 응답 이상: HTTP %s" % r.status)

def _digits(x): return re.sub(r"\D", "", str(x or ""))

def to_id(room):        # 엑셀 호실 'A18(2)' -> officeboard ID 'A18-2'
    m = re.fullmatch(r"(.+)\((\d+)\)", (room or "").strip())
    return f"{m.group(1)}-{m.group(2)}" if m else (room or "").strip()

def next_suffixed(base, data):          # office-domain.js nextSuffixedVaId 와 같은 규칙
    if base not in data: return base
    n = 2
    while f"{base}-{n}" in data: n += 1
    return f"{base}-{n}"

def build_record(c, prev=None):
    months = int(c.get("months") or 0)
    rec = dict(prev or {})
    rec.update({
        "name": c.get("company") or c.get("rep") or "", "tenantName": c.get("rep") or "",
        "isCorp": bool(c.get("corp")), "phone": c.get("phone") or "",
        "start": c.get("start") or "", "end": c.get("end") or "", "vat": True, "discount": 0,
        "rent": int(c.get("rentTotal") or 0), "contractMonths": months, "contractType": "비상주",
        "prepaid": True, "prepaidAt": (c.get("start") or "")[:7],
    })
    rec.setdefault("contractStatus", "계약중"); rec.setdefault("memo", "")
    return rec

LABELS = {"name": "상호", "tenantName": "입주자(대표자)", "isCorp": "법인", "phone": "연락처", "start": "계약 시작일",
          "end": "계약 종료일", "rent": "선납 총액(VAT포함)", "contractMonths": "개월수"}

def _norm(k, v):
    if k == "phone": return _digits(v)
    if k == "isCorp": return "법인" if v else "개인"
    return "" if v in (None, "") else str(v)

def find_existing(c, data):
    hint = c.get("obId")
    if hint and hint in data:
        d = data[hint]
        if _digits(d.get("phone")) == _digits(c.get("phone")) or (d.get("tenantName") or "") == (c.get("rep") or ""): return hint
    ph = _digits(c.get("phone"))
    if ph:
        for k, d in data.items():
            if d.get("contractType") == "비상주" and _digits(d.get("phone")) == ph and d.get("contractStatus") in ("계약중", "예정", None): return k
    return None

def check(c, cl=None):
    cl = cl or Client(); cl.login(); data = cl.get_data()
    key = find_existing(c, data)
    if not key:
        return {"status": "new", "id": next_suffixed(to_id(c.get("room")) or "V", data) if c.get("room") else None}
    new = build_record(c, data[key]); diffs = []
    for k, label in LABELS.items():
        if k in ("name", "tenantName", "phone", "start", "end") and not new.get(k): continue
        a, b = _norm(k, data[key].get(k)), _norm(k, new.get(k))
        if a != b: diffs.append({"key": k, "label": label, "old": a or "(비어 있음)", "new": b})
    return {"status": "changed" if diffs else "dup", "id": key, "diffs": diffs, "name": data[key].get("name") or data[key].get("tenantName") or ""}

def insert(c):
    cl = Client(); cl.login(); data = cl.get_data()
    rid = c.get("room") and next_suffixed(to_id(c["room"]), data)
    if not rid:                                               # 호실이 없으면 V번호
        mx = max([int(m.group(1)) for k in data for m in [re.fullmatch(r"V(\d+)", k)] if m] or [0]); rid = "V%03d" % (mx + 1)
    data[rid] = build_record(c)
    cl.put_data(data)
    if rid not in cl.get_data(): raise RuntimeError("저장 후 확인에 실패했어요 (다른 화면에서 덮어썼을 수 있어요)")
    return {"id": rid}

def update(c):
    cl = Client(); cl.login(); data = cl.get_data()
    key = find_existing(c, data)
    if not key: raise RuntimeError("수정할 고객을 officeboard에서 찾지 못했어요.")
    data[key] = build_record(c, data[key]); cl.put_data(data)
    if cl.get_data().get(key, {}).get("start") != data[key]["start"]: raise RuntimeError("저장 후 확인에 실패했어요.")
    return {"id": key}

def remove(c):
    cl = Client(); cl.login(); data = cl.get_data()
    key = find_existing(c, data)
    if not key: return {"removed": False}
    del data[key]; cl.put_data(data)
    if key in cl.get_data(): raise RuntimeError("삭제 후 확인에 실패했어요.")
    return {"removed": True, "id": key}
