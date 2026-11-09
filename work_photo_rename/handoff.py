"""다른 프로그램(사진 원근 보정)에서 보낸 사진을 받는 모듈.

실행 중인 사진문구넣기에 사진 경로를 보내면(127.0.0.1 전용 소켓) 목록에 바로 추가된다.
꺼져 있으면 보내는 쪽이 이 프로그램을 사진 경로를 인자로 주어 실행하고, 시작할 때 인자를 목록에 넣는다.
"""
import json
import queue
import socket
import sys
import threading
from pathlib import Path

PORT = 47653
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


def valid_images(paths):
    """존재하는 이미지 파일만 (순서 유지)."""
    return [str(p) for p in paths if Path(p).suffix.lower() in IMAGE_EXT and Path(p).is_file()]


def startup_files(argv=None):
    """실행할 때 인자로 받은 사진들."""
    return valid_images((argv if argv is not None else sys.argv)[1:])


class Inbox:
    """받은 경로를 쌓아 두는 서버. 화면은 take()로 주기적으로 꺼내 쓴다. 이미 다른 프로그램이 포트를 쓰면 조용히 꺼진 채로 둔다."""

    def __init__(self):
        self._q = queue.Queue()
        self.active = False
        try:
            self._srv = socket.socket()
            self._srv.bind(("127.0.0.1", PORT))
            self._srv.listen(5)
        except OSError:
            return
        self.active = True
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            with conn:
                try:
                    conn.settimeout(3)
                    buf = b""
                    while chunk := conn.recv(65536):
                        buf += chunk
                    paths = valid_images(json.loads(buf.decode("utf-8")).get("paths", []))
                    self._q.put(paths)
                    conn.sendall(b"ok")
                except Exception:
                    pass

    def take(self):
        out = []
        try:
            while True:
                out += self._q.get_nowait()
        except queue.Empty:
            return out
