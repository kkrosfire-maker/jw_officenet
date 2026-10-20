"""Claude Code에서 카톡 새 대화를 대시보드에 반영할 때 쓰는 도구.

  python chat_tool.py status                 # 원문 몇 건, 어디까지 정리됐는지
  python chat_tool.py import <카톡.txt>      # 마지막 읽은 메시지 이후만 원문에 추가
  python chat_tool.py pending [시작번호]     # 아직 이벤트로 정리 안 된 대화 출력
  python chat_tool.py events [YYYY-MM-DD]    # 그 날짜 이후 이벤트 출력(대조용)
  python chat_tool.py apply <updates.json>   # 정리 결과 반영

updates.json 형식:
{
  "add":    [{"d":"2026-10-19","c":"거래처","p":"제약사","v":"담당업체","t":1~6,
              "x":"상황","f":"확인할 것","s":"확인필요|답변대기중|후속기록없음|완료","ref":메시지번호}],
  "update": [{"no":585, "s":"완료", "dd":"2026-10-19", "x":"...", "f":"...", "memo":"..."}],
  "criteria": [{"n":"제약사", "a":"..", "b":"..", "c":"..", "etc":"..", "dt":"..", "src":"..", "flag":"변경"}],
  "history":  [{"n":"제약사","d":"2026-10-19","x":"내용"}],
  "done": 6277          # 여기 전 메시지까지 정리 완료 (생략하면 원문 끝까지)
}
앱이 켜져 있어도 된다. 앱은 창에 다시 들어올 때 바뀐 내용을 다시 읽는다.
"""
import json
import sys

import store

sys.stdout.reconfigure(encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    d, _ = store.load_dash()
    if cmd == "status":
        print(json.dumps(store.chat_status(d), ensure_ascii=False, indent=1))
    elif cmd == "import":
        print(json.dumps(store.import_chat(sys.argv[2]), ensure_ascii=False))
    elif cmd == "pending":
        msgs = store.load_chat()["msgs"]
        start = int(sys.argv[2]) if len(sys.argv) > 2 else d.get("chat_done", 0)
        for i in range(start, len(msgs)):
            m = msgs[i]
            print(i, m[0], m[1], "|", m[2].replace("\n", " / "))
    elif cmd == "events":
        since = sys.argv[2] if len(sys.argv) > 2 else ""
        for e in d["events"]:
            if e["d"] >= since:
                print(e["no"], e["d"], e["c"], e["p"], e["s"], "|", e["x"], "|", e.get("f", ""))
    elif cmd == "apply":
        with open(sys.argv[2], encoding="utf-8") as f:
            u = json.load(f)
        nxt = max((e["no"] for e in d["events"]), default=0) + 1
        added = []
        for e in u.get("add", []):
            e = {"no": nxt, "d": e["d"], "c": e.get("c", "-"), "p": e.get("p", "-"), "v": e.get("v", "-"),
                 "t": int(e.get("t", 6)), "x": e.get("x", ""), "f": e.get("f", ""), "s": e.get("s", "확인필요"),
                 "memo": e.get("memo", ""), "dd": e.get("dd", e["d"] if e.get("s") == "완료" else ""),
                 **({"ref": e["ref"]} if "ref" in e else {}), "new": 1}
            d["events"].append(e)
            added.append(nxt)
            nxt += 1
        byno = {e["no"]: e for e in d["events"]}
        for x in u.get("update", []):
            e = byno[x["no"]]
            for k, v in x.items():
                if k != "no":
                    e[k] = v
        byname = {}
        for c in d["criteria"]:
            byname.setdefault(c["n"], c)  # 같은 이름이 여러 줄이면 첫 줄을 고침 (id를 주면 그 줄)
        byid = {c.get("id"): c for c in d["criteria"]}
        for x in u.get("criteria", []):
            if x.get("id") in byid:
                byid[x["id"]].update(x)
            elif x["n"] in byname:
                byname[x["n"]].update(x)
            else:
                d["criteria"].append({"ua": "", "ub": "", "uc": "", "a": "", "b": "", "c": "", "etc": "",
                                      "dt": "", "src": "", "flag": "신규", "upd": "", **x})
        store._ensure_ids(d)
        d["history"].extend(u.get("history", []))
        msgs = store.load_chat()["msgs"]
        d["chat_done"] = int(u.get("done", len(msgs)))
        if d["events"]:
            d["asof"] = max(d["asof"], msgs[d["chat_done"] - 1][0][:10] if d["chat_done"] else d["asof"])
        rev = store.save_dash(d, d.get("rev", 0))
        print(json.dumps({"added": added, "updated": [x["no"] for x in u.get("update", [])],
                          "rev": rev, "chat_done": d["chat_done"]}, ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
