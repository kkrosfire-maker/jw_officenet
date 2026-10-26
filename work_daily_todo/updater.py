"""오늘의 할 일 업데이트 프로그램.
새 버전 프로그램 파일(payload)을 품고 있다가, 이미 설치된 '오늘의할일' 폴더의 프로그램 파일만 바꾼다.
data 폴더(할 일 기록·창 위치)는 건드리지 않고, 바꾸기 전에 data_백업_* 으로 한 벌 복사해 둔다.
build_release.py 가 이 파일을 한 개짜리 exe 로 만든다."""
import ctypes
import os
import shutil
import subprocess
import sys
import time
import tkinter as tk
from ctypes import wintypes as wt
from datetime import datetime
from tkinter import filedialog, messagebox

APP_EXE = "오늘의할일.exe"
WINDOW_TITLE = "오늘의 할 일"  # docking.TITLE 과 같아야 한다
KEEP = {"data"}  # 절대 지우거나 덮어쓰지 않는 것
PAYLOAD = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "payload")
VERSION = open(os.path.join(PAYLOAD, "version.txt"), encoding="utf-8").read().strip() if os.path.exists(os.path.join(PAYLOAD, "version.txt")) else ""

k32 = ctypes.windll.kernel32
u32 = ctypes.windll.user32
k32.OpenProcess.restype = wt.HANDLE
u32.FindWindowW.restype = wt.HWND


# ---- 설치 폴더 찾기 ----
def is_install(folder):
    return bool(folder) and os.path.isfile(os.path.join(folder, APP_EXE))


def running_apps():
    """떠 있는 '오늘의 할 일' exe 창들 → [(창 핸들, 프로세스 id, exe 경로)]. 파이썬으로 띄운 개발용 창은 뺀다."""
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def each(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        u32.GetWindowTextW(hwnd, buf, 256)
        if buf.value == WINDOW_TITLE:
            pid = wt.DWORD()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            h = k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
            if h:
                path, size = ctypes.create_unicode_buffer(1024), wt.DWORD(1024)
                if k32.QueryFullProcessImageNameW(h, 0, path, ctypes.byref(size)) and os.path.basename(path.value).lower() == APP_EXE.lower():
                    found.append((hwnd, pid.value, path.value))
                k32.CloseHandle(h)
        return True

    u32.EnumWindows(each, 0)
    return found


def search_installs():
    """바탕화면·다운로드·문서·C:\\ 얕은 곳에서 오늘의할일.exe 가 있는 폴더를 찾는다."""
    home = os.path.expanduser("~")
    roots = [os.path.join(home, d) for d in ("Desktop", "바탕 화면", "OneDrive\\Desktop", "OneDrive\\바탕 화면", "Downloads", "Documents", "OneDrive\\Documents")]
    roots += ["C:\\", "D:\\"]
    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        depth0 = root.rstrip("\\").count("\\")
        for cur, dirs, files in os.walk(root):
            if APP_EXE in files and os.path.isdir(os.path.join(cur, "_internal")):
                found.append(os.path.normpath(cur))
            if cur.rstrip("\\").count("\\") - depth0 >= (2 if len(root) <= 3 else 4):
                dirs[:] = []
            else:
                dirs[:] = [d for d in dirs if not d.startswith((".", "$", "_internal")) and d not in ("Windows", "Program Files", "Program Files (x86)", "ProgramData", "AppData", "node_modules")]
    return sorted(set(found), key=last_used, reverse=True)


def last_used(folder):
    """data/todos.json 을 마지막으로 고친 시각(없으면 0) - 여러 곳에 있으면 실제로 쓰는 폴더를 고르려고."""
    p = os.path.join(folder, "data", "todos.json")
    return os.path.getmtime(p) if os.path.exists(p) else 0


def find_target():
    here = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    if is_install(here):
        return here  # 설치 폴더 안에 넣고 실행한 경우
    run = running_apps()
    if run:
        return os.path.dirname(run[0][2])
    found = search_installs()
    return found[0] if found else None


# ---- 실행 중인 앱 닫기 ----
def close_app(folder):
    """설치 폴더의 앱이 떠 있으면 정상 종료(창 위치 저장) 시키고, 안 닫히면 강제로 끈다."""
    for hwnd, pid, path in running_apps():
        if os.path.normcase(os.path.dirname(path)) != os.path.normcase(folder):
            continue
        u32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        h = k32.OpenProcess(0x00100000 | 0x0001, False, pid)  # SYNCHRONIZE | PROCESS_TERMINATE
        if h:
            if k32.WaitForSingleObject(h, 8000) != 0:
                k32.TerminateProcess(h, 0)
                k32.WaitForSingleObject(h, 3000)
            k32.CloseHandle(h)
    # 창 없이 남은 프로세스(같은 exe 이름)도 정리
    subprocess.run(["taskkill", "/F", "/IM", APP_EXE], capture_output=True, creationflags=0x08000000)
    time.sleep(0.5)


# ---- 파일 바꾸기 ----
def backup_data(folder):
    src = os.path.join(folder, "data")
    if not os.path.isdir(src):
        return None
    dest = os.path.join(folder, f"data_백업_{datetime.now():%y%m%d_%H%M%S}")
    shutil.copytree(src, dest)
    return dest


def remove(path):
    for _ in range(10):  # 방금 끈 프로세스가 파일을 잠깐 쥐고 있을 수 있다
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
            return
        except PermissionError:
            time.sleep(0.5)
    raise PermissionError(f"파일을 지울 수 없어요(사용 중): {path}")


def install(folder):
    for name in os.listdir(PAYLOAD):
        if name in KEEP:
            continue
        src, dst = os.path.join(PAYLOAD, name), os.path.join(folder, name)
        remove(dst)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


# ---- 화면 ----
def main():
    root = tk.Tk()
    root.withdraw()
    title = f"오늘의 할 일 업데이트 {VERSION}".strip()

    folder = find_target()
    if folder:
        ans = messagebox.askyesnocancel(title, f"아래 폴더의 '오늘의 할 일'을 새 버전으로 바꿉니다.\n\n{folder}\n\n"
                                                "할 일 기록(data 폴더)은 그대로 남습니다.\n\n"
                                                "[예] 이 폴더로 진행   [아니요] 다른 폴더 고르기", parent=root)
        if ans is None:
            return
        if not ans:
            folder = None
    if not folder:
        while True:
            folder = filedialog.askdirectory(title="'오늘의할일.exe' 가 들어 있는 폴더를 고르세요", parent=root)
            if not folder:
                return
            folder = os.path.normpath(folder)
            if is_install(folder):
                break
            messagebox.showwarning(title, f"이 폴더에는 {APP_EXE} 가 없어요. 다시 골라 주세요.\n\n{folder}", parent=root)

    try:
        close_app(folder)
        bak = backup_data(folder)
        install(folder)
    except Exception as e:  # noqa: BLE001 - 사용자에게 그대로 보여준다
        messagebox.showerror(title, f"업데이트하지 못했어요.\n\n{e}\n\n할 일 기록(data 폴더)은 그대로 있습니다.", parent=root)
        return

    msg = "업데이트를 마쳤어요. 프로그램을 다시 켭니다."
    if bak:
        msg += f"\n\n혹시 몰라 기존 기록을 한 벌 더 복사해 두었어요:\n{bak}"
    messagebox.showinfo(title, msg, parent=root)
    subprocess.Popen([os.path.join(folder, APP_EXE)], cwd=folder)


if __name__ == "__main__":
    main()
