"""프로그램 목록(programs.json)을 고치는 규칙. 파일·HTTP 를 모르는 순수 함수라 입력 → 결과만 시험하면 된다."""
import copy, os


class StoreError(ValueError):
    """화면에 그대로 보여줄 수 있는 입력 오류 메시지."""


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


def _icon(icons, p):
    """아이콘은 부가 요소라 가져오기에 실패해도 저장을 막지 않는다(빈 문자열 → 카드에 첫 글자가 나온다)."""
    try:
        return icons(p) or ""
    except Exception:
        return ""


def apply(cfg, req, icons):
    """req = {action: add|update|delete|reorder, ...} 를 적용한 새 cfg 를 돌려준다(입력 cfg 는 그대로).
    icons(program) → 'icons/<id>.png' 또는 ''. 잘못된 입력은 StoreError."""
    cfg = copy.deepcopy(cfg)
    progs = cfg["programs"]
    act = req["action"]
    if act == "reorder":  # [{id, group}...] 순서대로 다시 배열하고 그룹도 반영
        byid = {x["id"]: x for x in progs}
        new = []
        for o in req["order"]:
            x = byid.pop(o["id"], None)
            if x:
                x["group"] = o.get("group") or x.get("group", "기타")
                new.append(x)
        cfg["programs"] = new + list(byid.values())
    elif act == "delete":
        cfg["programs"] = [p for p in progs if p["id"] != req["id"]]
    elif act in ("add", "update"):
        p = clean(req["program"])
        if not p["name"] or not (p.get("url") or p.get("path")):
            raise StoreError("이름과 경로(주소)는 필수예요")
        if act == "add":
            ids = {x["id"] for x in progs}
            n = 1
            while f"custom{n}" in ids:
                n += 1
            p["id"] = f"custom{n}"
            p["icon"] = _icon(icons, p)
            progs.append(p)
        else:
            i = next((i for i, x in enumerate(progs) if x["id"] == p["id"]), None)
            if i is None:
                raise StoreError("수정할 프로그램을 찾을 수 없어요")
            old = progs[i]
            p["icon"] = old.get("icon", "")
            key = "url" if p["type"] == "url" else "path"
            if p["id"].startswith("custom") and (not p["icon"] or old.get(key) != p[key]):
                p["icon"] = _icon(icons, p) or p["icon"]
            progs[i] = p
    else:
        raise StoreError(f"알 수 없는 동작: {act}")
    return cfg
