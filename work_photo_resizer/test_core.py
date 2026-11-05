"""핵심 로직(꼭짓점 결정·조정 기억·좌표 변환·실행취소·변환·학습·클립보드) 테스트.
GUI 없이 실행: `python -m pytest test_core.py`"""
import numpy as np
import pytest

import corner_resolver as cr
from converter import order_points, four_point_transform
from corner_memory import CornerMemory
from photo_edits import PhotoEdits
from undo_stack import UndoStack, HistoryController
from view_transform import ViewTransform, layout_fit, layout_zoomable, pan_for_anchor
from workbench import read_clipboard, images_in_folder, history_status_text

PTS = [[10, 10], [90, 10], [90, 90], [10, 90]]


def blank(w=200, h=100):
    return np.zeros((h, w, 3), np.uint8)


# ── PhotoEdits ──────────────────────────────────────────────────────────

def test_turn_invalidates_saved_pts():
    e = PhotoEdits()
    e.save_pts("a", PTS)
    assert e.saved_pts("a") == PTS
    e.turn("a", 1)
    assert e.rotation("a") == 1
    assert e.saved_pts("a") is None


def test_rotation_wraps_and_is_per_photo():
    e = PhotoEdits()
    e.turn("a", -1)
    assert e.rotation("a") == 3
    assert e.rotation("b") == 0
    e.turn("a", 1)
    assert e.rotation("a") == 0


def test_save_pts_ignores_non_quad_and_returns_copies():
    e = PhotoEdits()
    e.save_pts("a", PTS[:3])
    assert e.saved_pts("a") is None
    e.save_pts("a", PTS)
    e.saved_pts("a")[0][0] = 999
    assert e.saved_pts("a") == PTS


def test_copy_is_independent():
    e = PhotoEdits()
    e.save_pts("a", PTS)
    c = e.copy()
    e.turn("a", 1)
    assert c.saved_pts("a") == PTS and c.rotation("a") == 0


# ── resolve_corners ─────────────────────────────────────────────────────

class FakeMemory:
    def __init__(self, result=None, boom=False):
        self.result, self.boom = result, boom

    def match(self, image):
        if self.boom:
            raise RuntimeError("x")
        return self.result


class Learned:
    pts = np.array(PTS, dtype="float32")
    source = "ref.jpg"


def never(_):
    raise AssertionError("must not be called")


def test_saved_wins_over_everything():
    r = cr.resolve_corners(blank(), saved_pts=PTS, memory=FakeMemory(Learned()), detect=never)
    assert (r.source, r.pts) == (cr.SAVED, PTS)


def test_learned_before_auto():
    r = cr.resolve_corners(blank(), memory=FakeMemory(Learned()), detect=never)
    assert r.source == cr.LEARNED and r.detail == "ref.jpg"
    assert r.pts == [[10.0, 10.0], [90.0, 10.0], [90.0, 90.0], [10.0, 90.0]]


def test_auto_when_no_memory_hit():
    r = cr.resolve_corners(blank(), memory=FakeMemory(None),
                           detect=lambda img: np.array(PTS, dtype="float32"))
    assert r.source == cr.AUTO


def test_memory_error_is_reported_and_falls_through():
    errors = []
    r = cr.resolve_corners(blank(), memory=FakeMemory(boom=True), detect=lambda i: None,
                           on_error=lambda where, e: errors.append(where))
    assert errors == ["memory.match"] and r.source == cr.FALLBACK


def test_fallback_is_5_percent_margin():
    r = cr.resolve_corners(blank(200, 100), detect=lambda i: None)
    assert r.source == cr.FALLBACK
    assert r.pts[0] == [5.0, 5.0] and r.pts[2] == [195.0, 95.0]


def test_render_resolved_fallback_returns_original():
    img = blank()
    out = cr.render_resolved(img, cr.Resolved(cr.margin_corners(200, 100), cr.FALLBACK, ""))
    assert out is img


def test_render_resolved_warps_to_quad_size():
    img = blank(200, 100)
    out = cr.render_resolved(img, cr.Resolved([[20, 10], [120, 10], [120, 60], [20, 60]], cr.SAVED, ""))
    assert out.shape[:2] == (50, 100)


# ── converter ───────────────────────────────────────────────────────────

def test_order_points_tl_tr_br_bl():
    shuffled = [[90, 90], [10, 10], [10, 90], [90, 10]]
    assert order_points(shuffled).tolist() == [[10, 10], [90, 10], [90, 90], [10, 90]]


def test_four_point_transform_extracts_region():
    img = blank(200, 100)
    img[20:60, 30:130] = 255
    out = four_point_transform(img, [[30, 20], [129, 20], [129, 59], [30, 59]])
    assert out.shape[:2] == (39, 99) and out.mean() > 250


# ── view_transform ──────────────────────────────────────────────────────

def test_roundtrip_and_clamp():
    v = ViewTransform()
    v.apply(layout_fit(400, 200, 800, 600))
    assert v.scale == pytest.approx(796 / 400)
    x, y = v.to_canvas(100, 50)
    assert v.to_image(x, y) == pytest.approx((100, 50))
    assert v.to_image_clamped(-999, 99999, 400, 200) == (0.0, 200.0)


def test_clamped_none_when_scale_invalid():
    v = ViewTransform()
    v.scale = 0
    assert v.to_image_clamped(1, 1, 10, 10) is None


def test_zoom_keeps_point_under_cursor():
    img_w, img_h, cw, ch = 400, 300, 800, 600
    lay0 = layout_zoomable(img_w, img_h, cw, ch, 1.0)
    cursor = (350, 280)
    v = ViewTransform(); v.apply(lay0)
    ix, iy = v.to_image(*cursor)
    lay1 = layout_zoomable(img_w, img_h, cw, ch, 3.0)
    px, py = pan_for_anchor(lay1, *cursor, ix, iy)
    v.apply(layout_zoomable(img_w, img_h, cw, ch, 3.0, px, py))
    cx, cy = v.to_canvas(ix, iy)
    assert (cx, cy) == pytest.approx(cursor, abs=1.0)


# ── undo_stack ──────────────────────────────────────────────────────────

def test_undo_redo_roundtrip():
    s = UndoStack()
    s.push("A")
    assert s.undo("B") == "A"
    assert s.redo("A") == "B"
    assert s.undo("B") == "A" and not s.can_undo


def test_push_clears_redo_and_limit():
    s = UndoStack(limit=2)
    for x in "abc":
        s.push(x)
    assert s.undo("now") == "c" and s.undo("c") == "b" and s.undo("b") is None
    s.push("z")
    assert not s.can_redo


def test_history_controller_restores_state():
    state = {"v": 1}
    h = HistoryController(lambda: state["v"], lambda snap: state.update(v=snap))
    h.push(1); state["v"] = 2
    assert h.undo() and state["v"] == 1
    assert h.redo() and state["v"] == 2
    assert not h.redo()


# ── corner_memory ───────────────────────────────────────────────────────

def textured(seed=1, w=400, h=300):
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 255, (h // 10, w // 10, 3), dtype=np.uint8)
    return np.kron(img, np.ones((10, 10, 1), np.uint8))


def test_memory_matches_same_photo_and_persists(tmp_path):
    img = textured()
    mem = CornerMemory(tmp_path)
    assert mem.match(img) is None
    assert mem.add(img, [[50, 40], [350, 40], [350, 260], [50, 260]], "a.jpg") == 1
    m = mem.match(img)
    assert m is not None and m.source == "a.jpg"
    assert np.allclose(m.pts, [[50, 40], [350, 40], [350, 260], [50, 260]], atol=3)
    assert len(CornerMemory(tmp_path)) == 1          # 디스크에서 다시 읽힘


def test_memory_same_source_replaced_and_clear(tmp_path):
    img = textured()
    mem = CornerMemory(tmp_path)
    mem.add(img, PTS, "a.jpg"); mem.add(img, PTS, "a.jpg")
    assert len(mem) == 1
    mem.clear()
    assert len(mem) == 0 and mem.match(img) is None


def test_memory_rejects_different_aspect(tmp_path):
    mem = CornerMemory(tmp_path)
    mem.add(textured(w=400, h=300), PTS, "a.jpg")
    assert mem.match(textured(w=300, h=400)) is None


# ── workbench 헬퍼 ──────────────────────────────────────────────────────

def test_images_in_folder_filters_and_sorts(tmp_path):
    for n in ["b.JPG", "a.png", "c.txt"]:
        (tmp_path / n).write_bytes(b"")
    assert [p[-5:] for p in images_in_folder(tmp_path)] == ["a.png", "b.JPG"]


def test_read_clipboard_kinds():
    assert read_clipboard(lambda: None).kind == "empty"
    assert read_clipboard(lambda: []).kind == "empty"
    assert read_clipboard(lambda: ["x.txt"]).kind == "no_images"
    c = read_clipboard(lambda: ["x.txt", "y.PNG"])
    assert c.kind == "files" and c.files == ["y.PNG"]

    from PIL import Image
    c = read_clipboard(lambda: Image.new("RGB", (4, 2), (255, 0, 0)))   # RGB 빨강 → BGR로 변환
    assert c.kind == "image" and c.image.shape == (2, 4, 3)
    assert c.image[0, 0].tolist() == [0, 0, 255]


def test_history_status_text():
    assert "3개" in history_status_text("undo", True, 3)
    assert "없습니다" in history_status_text("redo", False, 0)
