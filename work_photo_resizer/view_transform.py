"""이미지 ↔ 캔버스 좌표 변환과 배치 계산 (tkinter 없이 테스트 가능).

ImageCanvas(줌·패닝, main.py)와 RectCanvas(rect_canvas.py)가 공유한다.
"""
from collections import namedtuple

Layout = namedtuple("Layout", ["base_scale", "scale", "width", "height", "ox", "oy"])
"""base_scale — 줌 1.0일 때 창에 맞춘 배율 / scale — 줌 적용 배율 / width,height — 그려질 크기 / ox,oy — 캔버스상 좌상단."""

MIN_CANVAS = 200


def layout_zoomable(img_w, img_h, cw, ch, zoom=1.0, pan_x=0.0, pan_y=0.0) -> Layout:
    """ImageCanvas 배치: 위쪽 라벨 영역(26px)을 비우고 가운데 정렬 후 패닝 적용."""
    cw, ch = max(cw, MIN_CANVAS), max(ch, MIN_CANVAS)
    avail_w, avail_h = cw - 4, ch - 28
    base = min(avail_w / img_w, avail_h / img_h)
    eff = base * zoom
    nw, nh = max(1, int(img_w * eff)), max(1, int(img_h * eff))
    cx = max(2, (avail_w - nw) // 2) + 2
    cy = max(0, (avail_h - nh) // 2) + 26
    return Layout(base, eff, nw, nh, cx + int(pan_x), cy + int(pan_y))


def layout_fit(img_w, img_h, cw, ch) -> Layout:
    """RectCanvas 배치: 창에 꼭 맞추고 가운데 정렬 (줌·패닝 없음)."""
    cw, ch = max(cw, MIN_CANVAS), max(ch, MIN_CANVAS)
    scale = min((cw - 4) / img_w, (ch - 4) / img_h)
    nw, nh = max(1, int(img_w * scale)), max(1, int(img_h * scale))
    return Layout(scale, scale, nw, nh, max(0, (cw - nw) // 2), max(0, (ch - nh) // 2))


def pan_for_anchor(layout_no_pan: Layout, cursor_x, cursor_y, img_x, img_y):
    """커서 아래의 이미지 점(img_x, img_y)이 줌 후에도 같은 자리에 머물도록 하는 패닝값.
    layout_no_pan: 패닝 0으로 계산한 새 배치."""
    return (cursor_x - layout_no_pan.ox - img_x * layout_no_pan.scale,
            cursor_y - layout_no_pan.oy - img_y * layout_no_pan.scale)


class ViewTransform:
    def __init__(self):
        self.scale = 1.0
        self.ox = 0
        self.oy = 0

    def apply(self, layout: Layout):
        self.scale, self.ox, self.oy = layout.scale, layout.ox, layout.oy

    def to_canvas(self, ix, iy):
        return ix * self.scale + self.ox, iy * self.scale + self.oy

    def to_image(self, cx, cy):
        return (cx - self.ox) / self.scale, (cy - self.oy) / self.scale

    def to_image_clamped(self, cx, cy, img_w, img_h):
        """이미지 범위 안으로 자른 좌표. 배율이 유효하지 않으면 None."""
        if self.scale <= 0:
            return None
        ix, iy = self.to_image(cx, cy)
        return max(0.0, min(float(img_w), ix)), max(0.0, min(float(img_h), iy))
