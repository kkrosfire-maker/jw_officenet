"""사용자가 발췌문을 고친 내용을 줄 단위 규칙으로 학습한다.

- replace: 자동 추출된 줄(원문) -> 사용자가 고친 줄
- drop   : 사용자가 지운 줄
줄을 새로 추가한 것은 일반화할 수 없어 규칙으로 만들지 않고 로그만 남긴다.
"""
import difflib
import json
import os
import time

from paths import DATA_DIR as HERE

RULES_PATH = os.path.join(HERE, "learned_rules.json")
LOG_PATH = os.path.join(HERE, "corrections.jsonl")


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def load() -> dict:
    try:
        with open(RULES_PATH, encoding="utf-8") as f:
            r = json.load(f)
    except (OSError, ValueError):
        r = {}
    return {"replace": dict(r.get("replace", {})), "drop": list(r.get("drop", []))}


def save(rules: dict) -> None:
    with open(RULES_PATH, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def apply(body: str) -> tuple[str, list[str]]:
    """학습된 규칙을 적용한 본문과, 적용 내역(로그용)을 반환."""
    rules = load()
    out, applied = [], []
    for ln in _lines(body):
        if ln in rules["drop"]:
            applied.append(f"삭제: {ln}")
            continue
        if ln in rules["replace"]:
            new = rules["replace"][ln]
            applied.append(f"수정: {ln} → {new}")
            ln = new
        out.append(ln)
    return "\n".join(out), applied


def learn(shown: str, final: str) -> list[str]:
    """화면에 보여준 발췌문(shown)과 최종본(final)을 비교해 규칙을 갱신. 새로 배운 내역을 반환."""
    a, b = _lines(shown), _lines(final)
    if a == b:
        return []
    rules = load()
    learned: list[str] = []

    def add_replace(old: str, new: str):
        # old 가 기존 규칙의 결과였다면, 그 규칙의 원문 -> new 로 갱신(규칙이 체인으로 꼬이지 않게)
        src = next((s for s, d in rules["replace"].items() if d == old), old)
        for s in [s for s, d in rules["replace"].items() if d == old]:
            del rules["replace"][s]
        if src != new:
            rules["replace"][src] = new
        learned.append(f"수정 학습: {src} → {new}")

    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "delete":
            for ln in a[i1:i2]:
                if ln not in rules["drop"]:
                    rules["drop"].append(ln)
                learned.append(f"삭제 학습: {ln}")
        elif tag == "replace":
            # 줄 수가 다른 덩어리: 비슷한 줄끼리 '수정'으로 짝짓고, 짝 없는 원본 줄은 '삭제'로 본다.
            news = list(b[j1:j2])
            for old in a[i1:i2]:
                best, score = None, 0.6
                for cand in news:
                    r = difflib.SequenceMatcher(None, old, cand).ratio()
                    if r >= score:
                        best, score = cand, r
                if best is not None:
                    news.remove(best)
                    add_replace(old, best)
                else:
                    if old not in rules["drop"]:
                        rules["drop"].append(old)
                    learned.append(f"삭제 학습: {old}")
    save(rules)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "shown": a, "final": b}, ensure_ascii=False) + "\n")
    return learned


def delete_rule(kind: str, key: str) -> None:
    rules = load()
    if kind == "drop" and key in rules["drop"]:
        rules["drop"].remove(key)
    elif kind == "replace":
        rules["replace"].pop(key, None)
    save(rules)
