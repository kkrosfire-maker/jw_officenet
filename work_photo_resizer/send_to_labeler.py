"""변환한 사진을 사진문구넣기(work_photo_rename)로 바로 보낸다.

실행 중이면 로컬 소켓(127.0.0.1:47653)으로 경로를 보내 목록에 추가시키고,
꺼져 있으면 프로그램을 사진 경로를 인자로 주어 실행한다 (시작할 때 목록에 넣는다).
"""
import json
import socket
import subprocess
import sys
from pathlib import Path

PORT = 47653                      # work_photo_rename/handoff.py 와 같은 값
EXE_NAME = "사진문구넣기.exe"
_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def labeler_commands():
    """사진문구넣기를 띄울 수 있는 명령 후보 (앞 순서 우선)."""
    root = _BASE.parent if (_BASE.parent / "work_photo_rename").exists() else _BASE.parent.parent
    app = root / "work_photo_rename"
    cmds = []
    if (app / "dist" / EXE_NAME).exists():
        cmds.append([str(app / "dist" / EXE_NAME)])
    if (app / "run.pyw").exists():
        py = Path(sys.executable).with_name("pythonw.exe")
        cmds.append([str(py if py.exists() else sys.executable), str(app / "run.pyw")])
    return cmds


def _send_running(paths):
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=2) as c:
            c.sendall(json.dumps({"paths": paths}, ensure_ascii=False).encode("utf-8"))
            c.shutdown(socket.SHUT_WR)
            return c.recv(8) == b"ok"
    except OSError:
        return False


def send(paths):
    """paths를 사진문구넣기로 보낸다. 반환: "sent"(실행 중인 창에 추가) | "launched"(새로 실행) | None(실패)."""
    paths = [str(p) for p in paths]
    if not paths:
        return None
    if _send_running(paths):
        return "sent"
    for cmd in labeler_commands():
        try:
            subprocess.Popen(cmd + paths, cwd=str(Path(cmd[-1]).parent))
            return "launched"
        except OSError:
            continue
    return None
