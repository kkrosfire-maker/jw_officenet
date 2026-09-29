"""전용 앱 창으로 띄우는 실행기.

브라우저 탭이 아니라 윈도우 창 하나로 뜬다. 창을 닫으면 서버도 같이 꺼진다.

구조: 같은 실행 파일을 `--nv-server <port>` 로 한 번 더 띄워서 그쪽에서 Streamlit
서버를 돌리고, 원래 프로세스는 창(pywebview)만 맡는다. Streamlit 의 bootstrap 은
시그널 핸들러를 걸기 때문에 반드시 그 프로세스의 **메인 스레드**에서 돌아야 하고,
pywebview 창도 메인 스레드를 쓴다. 그래서 둘을 프로세스로 나눈다.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SERVER_FLAG = "--nv-server"
WINDOW_TITLE = "네오벤타 정산문서"
STARTUP_TIMEOUT = 90  # 초

CREATE_NO_WINDOW = 0x08000000  # 자식 프로세스의 콘솔창을 띄우지 않는다


def _frozen() -> bool:
    return getattr(sys, "frozen", False)


def _bundle_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else Path(__file__).resolve().parent


def _app_dir() -> Path:
    """data/ 와 로그를 둘 폴더 (exe 옆, 개발 중에는 프로젝트 폴더)."""
    if _frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# ---------------------------------------------------------------- 서버 쪽

def run_server(port: int) -> None:
    """이 프로세스에서 Streamlit 서버를 돌린다 (메인 스레드)."""
    # 콘솔 없는 exe 에서는 stdout/stderr 가 None 일 수 있다. Streamlit 이 여기에 쓴다.
    log_path = _app_dir() / "app.log"
    try:
        stream = open(log_path, "a", encoding="utf-8", buffering=1)
    except OSError:
        stream = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream

    # data/ 를 exe 옆에 만들기 위해 작업 폴더를 맞춘다.
    os.chdir(str(_app_dir()))

    from streamlit.web import bootstrap

    flag_options = {
        "server.port": port,
        "server.address": "127.0.0.1",
        "server.headless": True,          # 브라우저를 따로 열지 않는다 (창은 우리가 띄운다)
        "server.showEmailPrompt": False,
        "server.fileWatcherType": "none",
        "browser.gatherUsageStats": False,
        "global.developmentMode": False,
        "theme.base": "light",
    }
    bootstrap.load_config_options(flag_options=flag_options)
    bootstrap.run(str(_bundle_dir() / "app.py"), False, [], flag_options)


# ---------------------------------------------------------------- 창 쪽

def _server_command(port: int) -> list[str]:
    if _frozen():
        return [sys.executable, SERVER_FLAG, str(port)]
    return [sys.executable, str(Path(__file__).resolve()), SERVER_FLAG, str(port)]


def _wait_for_server(url: str, process: subprocess.Popen, timeout: int) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.4)
    return False


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        # 자식 프로세스까지 정리한다.
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            creationflags=CREATE_NO_WINDOW,
            capture_output=True,
            check=False,
        )
    except OSError:
        process.terminate()


def _show_error(message: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, WINDOW_TITLE, 0x10)
    except Exception:  # noqa: BLE001
        print(message, file=sys.stderr)


def main() -> int:
    port = _free_port()
    url = f"http://127.0.0.1:{port}"

    creationflags = CREATE_NO_WINDOW if _frozen() else 0
    process = subprocess.Popen(
        _server_command(port),
        cwd=str(_app_dir()),
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )

    if not _wait_for_server(f"{url}/_stcore/health", process, STARTUP_TIMEOUT):
        _stop(process)
        _show_error(
            "정산 앱을 시작하지 못했습니다.\n\n"
            f"자세한 내용은 아래 파일을 확인하세요:\n{_app_dir() / 'app.log'}"
        )
        return 1

    try:
        import webview

        webview.create_window(WINDOW_TITLE, url, width=1500, height=950, min_size=(1100, 700))
        webview.start()
    except Exception as exc:  # noqa: BLE001
        _stop(process)
        _show_error(f"앱 창을 열지 못했습니다.\n\n{exc}")
        return 1
    finally:
        _stop(process)
    return 0


if __name__ == "__main__":
    if SERVER_FLAG in sys.argv:
        run_server(int(sys.argv[sys.argv.index(SERVER_FLAG) + 1]))
    else:
        sys.exit(main())
