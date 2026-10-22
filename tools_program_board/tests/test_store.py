import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from store import StoreError, apply

NO_ICON = lambda p: ""


def cfg(*progs):
    return {"title": "t", "programs": list(progs)}


def exe(id, path=r"C:\a\x.exe", **kw):
    return {"id": id, "name": id, "desc": "", "group": "업무", "icon": kw.pop("icon", ""), "type": "exe",
            "path": path, "args": "", "cwd": os.path.dirname(path), **kw}


def test_add_assigns_first_free_custom_id_and_defaults():
    out = apply(cfg(exe("custom1"), exe("custom3")),
                {"action": "add", "program": {"name": " 할일 ", "path": r"C:\w\할일_실행.bat"}}, NO_ICON)
    p = out["programs"][-1]
    assert p["id"] == "custom2" and p["name"] == "할일" and p["group"] == "기타"
    assert p["path"] == r"C:\w\할일_실행.bat" and p["cwd"] == r"C:\w"


def test_add_requires_name_and_target():
    with pytest.raises(StoreError):
        apply(cfg(), {"action": "add", "program": {"name": "", "path": "x"}}, NO_ICON)
    with pytest.raises(StoreError):
        apply(cfg(), {"action": "add", "program": {"name": "a"}}, NO_ICON)


def test_icon_failure_does_not_block_add():
    def boom(p):
        raise OSError("network")
    out = apply(cfg(), {"action": "add", "program": {"name": "a", "path": "x"}}, boom)
    assert out["programs"][0]["icon"] == ""


def test_add_uses_icon_adapter():
    out = apply(cfg(), {"action": "add", "program": {"name": "a", "path": "x"}}, lambda p: f"icons/{p['id']}.png")
    assert out["programs"][0]["icon"] == "icons/custom1.png"


def test_update_keeps_icon_unless_target_changed():
    calls = []
    def icons(p):
        calls.append(p["id"]); return "icons/new.png"
    base = cfg(exe("custom1", icon="icons/old.png"))
    same = apply(base, {"action": "update", "program": {**base["programs"][0], "name": "새이름"}}, icons)
    assert same["programs"][0]["icon"] == "icons/old.png" and not calls
    moved = apply(base, {"action": "update", "program": {**base["programs"][0], "path": r"C:\b\y.exe", "cwd": ""}}, icons)
    assert moved["programs"][0]["icon"] == "icons/new.png" and moved["programs"][0]["cwd"] == r"C:\b"


def test_update_icon_failure_keeps_old_icon():
    base = cfg(exe("custom1", icon="icons/old.png"))
    out = apply(base, {"action": "update", "program": {**base["programs"][0], "path": r"C:\b\y.exe"}}, NO_ICON)
    assert out["programs"][0]["icon"] == "icons/old.png"


def test_update_builtin_never_refetches_icon():
    base = cfg(exe("app4", icon=""))
    out = apply(base, {"action": "update", "program": {**base["programs"][0], "path": r"C:\b\y.exe"}},
                lambda p: 1 / 0)
    assert out["programs"][0]["icon"] == ""


def test_update_unknown_id():
    with pytest.raises(StoreError):
        apply(cfg(), {"action": "update", "program": {"id": "nope", "name": "a", "path": "x"}}, NO_ICON)


def test_delete():
    out = apply(cfg(exe("a"), exe("b")), {"action": "delete", "id": "a"}, NO_ICON)
    assert [p["id"] for p in out["programs"]] == ["b"]


def test_reorder_moves_group_and_keeps_unlisted_at_end():
    out = apply(cfg(exe("a"), exe("b"), exe("c")),
                {"action": "reorder", "order": [{"id": "c", "group": "통계"}, {"id": "a", "group": ""}]}, NO_ICON)
    assert [(p["id"], p["group"]) for p in out["programs"]] == [("c", "통계"), ("a", "업무"), ("b", "업무")]


def test_input_cfg_not_mutated():
    base = cfg(exe("a"))
    apply(base, {"action": "delete", "id": "a"}, NO_ICON)
    assert len(base["programs"]) == 1


def test_unknown_action():
    with pytest.raises(StoreError):
        apply(cfg(), {"action": "zap"}, NO_ICON)
