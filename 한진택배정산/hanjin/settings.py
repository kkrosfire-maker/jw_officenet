"""config.json: 로그인 정보(PW는 Windows DPAPI 암호화)와 마지막 저장 위치."""
from __future__ import annotations

import base64
import json
from pathlib import Path

DEFAULT_ID = "6482169"


def _protect(text: str) -> str:
    import win32crypt
    blob = win32crypt.CryptProtectData(text.encode("utf-8"), "hanjin", None, None, None, 0)
    return base64.b64encode(blob).decode("ascii")


def _unprotect(token: str) -> str:
    import win32crypt
    try:
        return win32crypt.CryptUnprotectData(base64.b64decode(token), None, None, None, 0)[1].decode("utf-8")
    except Exception:  # 다른 PC·계정에서 복사해 온 경우 → PW 다시 입력
        return ""


class Settings:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.remember = True
        self.user_id = DEFAULT_ID
        self.password = ""
        self.last_save_dir = ""
        self.load()

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.remember = data.get("remember", True)
        self.user_id = data.get("user_id") or DEFAULT_ID
        self.password = _unprotect(data["password"]) if data.get("password") else ""
        self.last_save_dir = data.get("last_save_dir", "")

    def save(self):
        data = {"remember": self.remember, "last_save_dir": self.last_save_dir}
        if self.remember:
            data["user_id"] = self.user_id
            data["password"] = _protect(self.password) if self.password else ""
        try:
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
