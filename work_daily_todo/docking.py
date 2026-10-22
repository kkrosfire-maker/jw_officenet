"""창 배치 - 프로그램 보드 옆에 붙이기·따라가기·항상 위 고정·시작 위치 기억. 창 제목이 두 창을 찾는 열쇠다."""
import ctypes
import json
import time
from ctypes import wintypes as wt

TITLE = "오늘의 할 일"
BOARD_TITLE = "정원유니어스 프로그램 보드"
DEFAULT_SIZE = (360, 800)


def dock_x(board_left, board_right, width, screen_w):
    """보드 오른쪽에 자리가 있으면 거기, 없으면 왼쪽."""
    return board_right if board_right + width <= screen_w else max(board_left - width, 0)


def _user32():
    u = ctypes.windll.user32
    u.FindWindowW.restype = ctypes.c_void_p
    u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    u.IsWindowVisible.argtypes = [ctypes.c_void_p]
    u.IsIconic.argtypes = [ctypes.c_void_p]
    u.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    ctypes.windll.dwmapi.DwmGetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
    return u


def _frame(u, hwnd):
    """(실제 창 사각형, 눈에 보이는 창 테두리) - 둘의 차이가 그림자 두께."""
    r, f = wt.RECT(), wt.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(f), ctypes.sizeof(f))
    return r, f


def is_open():
    return bool(_user32().FindWindowW(None, TITLE))


def set_pin(on):
    """항상 위 고정. pywebview 의 on_top 설정은 UI 스레드와 맞물려 멈출 수 있어 윈도우 API 로 직접 바꾼다."""
    u = _user32()
    hwnd = u.FindWindowW(None, TITLE)
    if hwnd:
        u.SetWindowPos(hwnd, -1 if on else -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # NOSIZE|NOMOVE|NOACTIVATE
    return bool(on)


def dock_next_to_board(wait_sec):
    """프로그램 보드 창 옆에 같은 높이로 붙인다. 붙인 때의 보드 위치를 돌려주고, 보드가 안 보이면 None."""
    u = _user32()
    end = time.time() + wait_sec
    while True:
        board, me = u.FindWindowW(None, BOARD_TITLE), u.FindWindowW(None, TITLE)
        if board and me and u.IsWindowVisible(board):
            time.sleep(0.8)  # 보드 창이 자리를 잡을 때까지
            _, bf = _frame(u, board)
            mr, mf = _frame(u, me)
            x = dock_x(bf.left, bf.right, mf.right - mf.left, u.GetSystemMetrics(0))
            h = bf.bottom - bf.top
            # 프레임 기준 목표 → 창 사각형 기준(그림자 두께만큼 바깥)으로 환산
            pinned = bool(u.GetWindowLongW(me, -20) & 0x8)  # 고정 상태는 그대로 유지
            u.SetWindowPos(me, -1 if pinned else -2, x - (mf.left - mr.left), bf.top - (mf.top - mr.top),
                           mr.right - mr.left, h + (mr.bottom - mr.top) - (mf.bottom - mf.top), 0x0010)
            return (bf.left, bf.top, bf.right, bf.bottom)
        if time.time() > end:
            return None
        time.sleep(0.5)


def follow_board(wait_sec):
    """보드 옆에 붙인 뒤, 보드를 옮기거나 크기를 바꾸면 따라간다. 보드가 닫히면 멈춘다."""
    last = dock_next_to_board(wait_sec)
    if not last:
        return
    u = _user32()
    while True:
        time.sleep(0.7)
        board = u.FindWindowW(None, BOARD_TITLE)
        if not board:
            return
        if u.IsIconic(board):
            continue
        _, f = _frame(u, board)
        cur = (f.left, f.top, f.right, f.bottom)
        if cur != last:
            last = dock_next_to_board(0) or last


def start_geometry(saved_path):
    """저장된 창 위치(없으면 화면 오른쪽 끝)를 (x, y, 너비, 높이)로 돌려준다."""
    try:
        with open(saved_path, encoding="utf-8") as f:
            g = json.load(f)
        return int(g["x"]), int(g["y"]), int(g["width"]), int(g["height"])
    except (OSError, ValueError, KeyError):
        pass
    w, h = DEFAULT_SIZE
    try:
        u = ctypes.windll.user32
        u.SetProcessDPIAware()
        sw, sh = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
        return max(sw - w - 20, 0), 20, w, min(h, sh - 80)
    except Exception:
        return 40, 20, w, h
