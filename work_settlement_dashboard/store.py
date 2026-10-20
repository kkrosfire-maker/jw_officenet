"""정원유니어스(주) 정산 대시보드 — 데이터 저장·카톡 파싱·발췌.

app.py(화면)와 chat_tool.py(Claude Code 업데이트용)가 같이 쓴다.
데이터 위치: %APPDATA%\\정원유니어스정산대시보드\\
  dashboard.json  이벤트·기준표·상태 (rev 번호로 충돌 방지)
  chat.json       카톡 원문 메시지 (뒤에만 추가, 번호 고정)
  backups\\        저장할 때마다 이전 dashboard.json 보관(최근 30개)
"""
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta

APP_NAME = "정원유니어스정산대시보드"
DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
DASH = os.path.join(DATA_DIR, "dashboard.json")
CHAT = os.path.join(DATA_DIR, "chat.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def _read(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


# ---------------- 대시보드 데이터 ----------------

def load_dash():
    """dashboard.json을 읽는다. 없으면 seed.json으로 새로 만들고 fresh=True."""
    d = _read(DASH)
    if d is not None:
        if _ensure_ids(d):
            _write(DASH, d)
        return d, False
    d = _read(resource("seed.json"))
    d.setdefault("rev", 0)
    d.setdefault("chat_done", 0)
    d["migrated"] = False  # 예전 exe가 브라우저 저장소에 남긴 상태·메모를 첫 실행 때 옮김
    for c in d.get("criteria", []):
        c.setdefault("upd", "")
    _ensure_ids(d)
    _write(DASH, d)
    return d, True


def _ensure_ids(d):
    """기준표에 같은 제약사가 두 줄 있는 경우가 있어, 행마다 고유 id를 붙인다."""
    crs = d.get("criteria", [])
    used = {c["id"] for c in crs if c.get("id")}
    n, changed = 0, False
    for c in crs:
        if not c.get("id"):
            while f"c{n}" in used:
                n += 1
            c["id"] = f"c{n}"
            used.add(c["id"])
            changed = True
    return changed


def current_rev():
    d = _read(DASH)
    return d.get("rev", 0) if d else -1


def save_dash(d, base_rev):
    """base_rev가 파일의 rev와 같을 때만 저장. 성공하면 새 rev 반환, 충돌이면 None."""
    cur = _read(DASH)
    if cur is not None and cur.get("rev", 0) != base_rev:
        return None
    if cur is not None:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(DASH, os.path.join(BACKUP_DIR, f"dashboard_{stamp}.json"))
        olds = sorted(os.listdir(BACKUP_DIR))
        for f in olds[:-30]:
            try:
                os.remove(os.path.join(BACKUP_DIR, f))
            except OSError:
                pass
    d["rev"] = base_rev + 1
    d["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _write(DASH, d)
    return d["rev"]


# ---------------- 카톡 파싱 ----------------

DAY_RE = re.compile(r"^-{5,} (\d{4})년 (\d{1,2})월 (\d{1,2})일 .*-{5,}$")
MSG_RE = re.compile(r"^\[(.+?)\] \[(오전|오후) (\d{1,2}):(\d{2})\] ?(.*)$")
SYS_RE = re.compile(r"님이 .*(초대했습니다|나갔습니다|내보냈습니다)|님이 들어왔습니다|채팅방 관리자")


def parse_kakao(path):
    """카톡 PC '대화 내보내기' txt → [[ 'YYYY-MM-DD HH:MM', 보낸사람, 내용 ], ...]"""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        lines = f.read().replace("\r\n", "\n").split("\n")
    out, day = [], None
    for ln in lines:
        m = DAY_RE.match(ln)
        if m:
            day = f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
            continue
        if day is None:
            continue
        m = MSG_RE.match(ln)
        if m:
            h = int(m[3]) % 12 + (12 if m[2] == "오후" else 0)
            out.append([f"{day} {h:02d}:{m[4]}", m[1], m[5]])
        elif ln.strip() and SYS_RE.search(ln):
            out.append([f"{day} --:--", "", ln.strip()])
        elif out and out[-1][0].startswith(day):
            out[-1][2] += "\n" + ln
    for m in out:
        m[2] = m[2].rstrip("\n")
    return out


def load_chat():
    return _read(CHAT, {"msgs": [], "src": ""})


def import_chat(path):
    """내보내기 파일에서 '마지막으로 읽은 메시지' 다음부터만 chat.json에 붙인다."""
    new = parse_kakao(path)
    if not new:
        return {"ok": False, "msg": "카톡 대화를 찾지 못했습니다. 카톡 PC의 '대화 내보내기' txt 파일인지 확인해 주세요."}
    chat = load_chat()
    old = chat["msgs"]
    start = 0
    if old:
        key = lambda m: (m[0], m[1], m[2])
        tail = [key(m) for m in old[-3:]]
        start = None
        for k in range(len(new), len(tail) - 1, -1):
            if [key(m) for m in new[k - len(tail):k]] == tail:
                start = k
                break
        if start is None:  # 겹치는 부분을 못 찾으면 마지막 시각 이후만
            last = old[-1][0]
            start = next((i for i, m in enumerate(new) if m[0] > last), len(new))
    add = new[start:]
    chat["msgs"] = old + add
    chat["src"] = os.path.basename(path)
    chat["imported_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _write(CHAT, chat)
    return {"ok": True, "added": len(add), "total": len(chat["msgs"]),
            "first": add[0][0] if add else "", "last": chat["msgs"][-1][0] if chat["msgs"] else ""}


def chat_status(d=None):
    chat = load_chat()
    msgs = chat["msgs"]
    if d is None:
        d, _ = load_dash()
    done = min(d.get("chat_done", 0), len(msgs))
    return {"total": len(msgs), "done": done, "pending": len(msgs) - done,
            "last": msgs[-1][0] if msgs else "", "done_until": msgs[done - 1][0] if done else ""}


# ---------------- 발췌 ----------------

def _clinic_keys(name):
    if not name or name == "-":
        return []
    keys = set()
    base = re.sub(r"\(.*?\)", "", name).strip()
    keys.add(base)
    core = re.sub(r"(의원|병원|클리닉)$", "", base).strip()
    if len(core) >= 2:
        keys.add(core)
    # '365제이에스JS연합의원' ↔ '365제이에스연합의원' 같은 표기 차이 대비
    nolatin = re.sub(r"[A-Za-z]+", "", core)
    if len(nolatin) >= 3:
        keys.add(nolatin)
    if len(core) >= 4:
        keys.add(core[:4])
    return sorted(keys, key=len, reverse=True)


def _pharma_keys(name):
    if not name or name == "-":
        return []
    out = []
    for part in re.split(r"[·/,]", name):
        p = re.sub(r"\(주\)|㈜", "", part).strip()
        if len(p) >= 2:
            out.append(p)
            q = re.sub(r"(제약|약품|파마|바이오|팜)$", "", p)
            if len(q) >= 2 and q != p:
                out.append(q)
    return out


def _words(text):
    return [w for w in re.findall(r"[가-힣A-Za-z0-9]{3,}", text or "")
            if w not in ("요청", "확인", "제출", "전달", "필요", "이번달", "다음달")][:12]


def find_anchor(ev, msgs, by_day):
    ref = ev.get("ref")
    if isinstance(ref, int) and 0 <= ref < len(msgs):
        return ref, []
    ck, pk, wk = _clinic_keys(ev.get("c")), _pharma_keys(ev.get("p")), _words(ev.get("x"))
    d0 = datetime.strptime(ev["d"], "%Y-%m-%d")
    for off in (0, -1, 1, -2, 2, -3, 3):
        day = (d0 + timedelta(days=off)).strftime("%Y-%m-%d")
        best, best_s = None, 0
        for i in by_day.get(day, []):
            t = msgs[i][2]
            s = (4 if any(k in t for k in ck) else 0) + (2 if any(k in t for k in pk) else 0) \
                + min(3, sum(1 for w in wk if w in t))
            if s > best_s:
                best, best_s = i, s
        if best is not None and best_s >= (3 if off else 2):
            return best, ck + pk
        if off == 0 and by_day.get(day) and not ck and not pk:
            return by_day[day][0], []
    lst = by_day.get(ev["d"])
    return (lst[0] if lst else None), ck + pk


def excerpt(ev, before=4, after=16):
    msgs = load_chat()["msgs"]
    if not msgs:
        return {"ok": False, "msg": "저장된 카톡 원문이 없습니다. 「카톡 대화 추가」로 내보내기 파일을 넣어주세요."}
    by_day = {}
    for i, m in enumerate(msgs):
        by_day.setdefault(m[0][:10], []).append(i)
    a, keys = find_anchor(ev, msgs, by_day)
    if a is None:
        return {"ok": False, "msg": f"{ev['d']} 대화를 원문에서 찾지 못했습니다."}
    s, e = max(0, a - before), min(len(msgs), a + after + 1)
    return {"ok": True, "anchor": a, "keys": keys, "start": s, "end": e, "total": len(msgs),
            "msgs": [[i] + msgs[i] for i in range(s, e)]}


def chat_range(start, end):
    msgs = load_chat()["msgs"]
    start, end = max(0, start), min(len(msgs), end)
    return {"ok": True, "start": start, "end": end, "total": len(msgs),
            "msgs": [[i] + msgs[i] for i in range(start, end)]}
