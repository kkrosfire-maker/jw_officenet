"""annotate.py 순수 함수 스모크 테스트. pytest 없이 `python test_annotate.py`로 실행."""
import math

from annotate import (rect_corners, hit_zone, point_in_rect,
                       resize_rect, rotate_angle, move_rect_center)


def approx(a, b, eps=1e-6):
    return abs(a - b) < eps


def test_rect_corners_no_rotation():
    r = {"cx": 10, "cy": 10, "hw": 5, "hh": 2, "angle": 0}
    corners = rect_corners(r)
    assert corners[0] == (5, 8)    # TL
    assert corners[2] == (15, 12)  # BR


def test_rect_corners_90deg():
    r = {"cx": 0, "cy": 0, "hw": 4, "hh": 1, "angle": 90}
    tl = rect_corners(r)[0]
    assert approx(tl[0], 1) and approx(tl[1], -4)


def test_point_in_rect_no_rotation():
    r = {"cx": 0, "cy": 0, "hw": 5, "hh": 5, "angle": 0}
    assert point_in_rect(r, 3, 3)
    assert not point_in_rect(r, 6, 0)


def test_point_in_rect_rotated():
    # 45도 회전한 정사각형(hw=hh=3): (2,2) 방향은 회전각과 일치하므로 로컬 x축상 거리 sqrt(8)=2.83 < 3 → 내부.
    r = {"cx": 0, "cy": 0, "hw": 3, "hh": 3, "angle": 45}
    assert point_in_rect(r, 2, 2)
    assert not point_in_rect(r, 5, 5)


def test_resize_rect_axis_aligned():
    cx, cy, hw, hh = resize_rect(fixed_pt=(0, 0), drag_pt=(10, 4), angle=0, min_half=1)
    assert approx(cx, 5) and approx(cy, 2)
    assert approx(hw, 5) and approx(hh, 2)


def test_resize_rect_min_half_clamped():
    cx, cy, hw, hh = resize_rect(fixed_pt=(0, 0), drag_pt=(1, 1), angle=0, min_half=8)
    assert hw == 8 and hh == 8


def test_rotate_angle_basic():
    a = rotate_angle(start_angle=10, start_mouse_angle=0, cur_mouse_angle=30)
    assert approx(a, 40)


def test_rotate_angle_wraps():
    a = rotate_angle(start_angle=350, start_mouse_angle=0, cur_mouse_angle=20)
    assert approx(a, 10)  # 370 % 360


def test_rotate_angle_snap():
    # delta=22 → 22/15=1.467 → round-half-even 규칙상 1 → 스냅 결과 15도.
    a = rotate_angle(start_angle=0, start_mouse_angle=0, cur_mouse_angle=22, snap_step=15)
    assert a == 15


def test_move_rect_center_clamped():
    cx, cy = move_rect_center(origin_cx=5, origin_cy=5, start_pt=(0, 0),
                               cur_pt=(-100, 3), bounds_wh=(20, 20))
    assert cx == 0.0            # 음수 방향으로 clamp
    assert approx(cy, 8)


def test_hit_zone_resize_then_rotate_ring():
    r = {"cx": 0, "cy": 0, "hw": 10, "hh": 10, "angle": 0}
    # scale=1, ox=oy=0 → 캔버스 좌표 == 이미지 좌표. TL 코너는 (-10,-10).
    assert hit_zone(r, -10, -10, scale=1, ox=0, oy=0, resize_hit=5, rotate_hit=20) == ("resize", 0)
    assert hit_zone(r, -10 - 12, -10, scale=1, ox=0, oy=0, resize_hit=5, rotate_hit=20) == ("rotate", 0)
    assert hit_zone(r, 1000, 1000, scale=1, ox=0, oy=0, resize_hit=5, rotate_hit=20) is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
        except AssertionError:
            failed += 1
            print(f"FAIL {t.__name__}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    if failed:
        raise SystemExit(1)
