"""사각형(테두리) 편집용 이미지 캔버스 — annotate_app.py / ocr_grid_app.py 공용.

몸통 드래그=이동 / 모서리=리사이즈 / 모서리 바깥쪽 링=회전 상호작용과 그 렌더링을
단일 위젯으로 캡슐화한다. 기하 계산 자체는 annotate.py의 순수 함수를 그대로 쓰고,
이 위젯은 그 함수들을 마우스/키보드 이벤트에 연결하는 상태머신 + 렌더링만 담당한다.

콜백 계약:
- on_edit(kind, pre_snapshot, index=None): 실행취소 대상이 되는 편집이 확정된 시점
  (드래그 완료·추가·삭제·전체삭제·회전)에 한 번 호출된다. kind는
  "drag"|"rotate"|"add"|"delete"|"clear". 두께 변경과 restore(undo/redo)는
  대상이 아니므로 호출되지 않는다.
- on_select(idx): 선택된 테두리가 바뀔 때(선택 해제 포함) 호출된다.
- badge_fn(idx) -> (text, color): 주어지면 각 테두리 중심에 뱃지 텍스트를 그린다.
"""
import math
import tkinter as tk

import cv2
from PIL import Image, ImageTk

from annotate import (rect_corners, hit_zone, point_in_rect,
                       resize_rect, rotate_angle, move_rect_center)

HANDLE_R   = 5
RESIZE_HIT = HANDLE_R * 2.5
ROTATE_HIT = RESIZE_HIT + 16
MIN_HALF   = 8


class RectCanvas(tk.Canvas):
    def __init__(self, parent, *, on_edit=None, on_select=None, badge_fn=None, **kw):
        super().__init__(parent, bg="#1a1a1a", highlightthickness=1,
                          highlightbackground="#3a3a3a", **kw)
        self._on_edit   = on_edit
        self._on_select = on_select
        self._badge_fn  = badge_fn

        self._cv_img = None
        self._tk_img = None
        self._scale  = 1.0
        self._ox = self._oy = 0
        self._resize_job = None

        self._rects        = []
        self._selected_idx = None
        self._drag_mode     = None   # ("resize"|"rotate"|"move", idx, ...)
        self._pre_drag_snapshot = None

        self._alt_held  = False
        self._ctrl_held = False

        self.bind("<Configure>",       self._on_configure)
        self.bind("<Button-1>",        self._on_press)
        self.bind("<B1-Motion>",       self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>",          self._on_hover)

    # ── 공개 API: 이미지 / 전체 초기화 ────────────────────────────────────

    def show(self, cv_img):
        self._cv_img = cv_img
        self._render()

    def clear(self):
        """이미지·테두리·선택을 모두 지운다 (콜백 발생 없음 — 파일 전환/빈 상태 전용)."""
        self._cv_img = None
        self._tk_img = None
        self._rects = []
        self._selected_idx = None
        self._drag_mode = None
        self.delete("all")

    # ── 공개 API: 테두리 목록 ────────────────────────────────────────────

    def get_rects(self):
        """항상 깊은 복사본을 반환 — 호출자가 자유롭게 스냅샷으로 써도 안전."""
        return [dict(r) for r in self._rects]

    def set_rects(self, rects):
        """undo/redo 복원 등, 실행취소 대상이 아닌 방식으로 테두리 목록을 통째로 교체.
        콜백을 발생시키지 않는다 — 호출자(주로 restore_fn)가 이미 전체 문맥을 알고
        있으므로 필요한 후처리(텍스트창 초기화 등)를 직접 수행한다."""
        self._rects = [dict(r) for r in rects]
        self._selected_idx = None
        self._render_overlay()

    def selected_index(self):
        return self._selected_idx

    def select(self, idx):
        self._selected_idx = idx
        self._render_overlay()
        if self._on_select:
            self._on_select(idx)

    def add_rect(self, hw_ratio=0.125, hh_ratio=0.125, thickness=4):
        if self._cv_img is None:
            return None
        pre = self.get_rects()
        h, w = self._cv_img.shape[:2]
        self._rects.append({
            "cx": w / 2, "cy": h / 2,
            "hw": w * hw_ratio, "hh": h * hh_ratio,
            "angle": 0.0, "thickness": thickness,
        })
        new_idx = len(self._rects) - 1
        self._selected_idx = new_idx
        # on_edit를 렌더링보다 먼저 호출한다 — badge_fn 등 렌더링 시점 콜백이
        # 호출자 쪽에서 이미 갱신된 상태(예: 텍스트 목록 길이)를 보도록 하기 위함.
        self._emit_edit("add", pre, new_idx)
        self._render_overlay()
        if self._on_select:
            self._on_select(new_idx)
        return new_idx

    def delete_selected(self):
        if self._selected_idx is None:
            return None
        pre = self.get_rects()
        idx = self._selected_idx
        del self._rects[idx]
        self._selected_idx = None
        self._emit_edit("delete", pre, idx)
        self._render_overlay()
        return idx

    def clear_rects(self):
        if not self._rects:
            return False
        pre = self.get_rects()
        self._rects = []
        self._selected_idx = None
        self._emit_edit("clear", pre)
        self._render_overlay()
        return True

    def rotate_selected(self, delta_deg):
        if self._selected_idx is None:
            return
        pre = self.get_rects()
        r = self._rects[self._selected_idx]
        r["angle"] = (r["angle"] + delta_deg) % 360
        self._emit_edit("rotate", pre, self._selected_idx)
        self._render_overlay()

    def selected_thickness(self):
        if self._selected_idx is None:
            return None
        return self._rects[self._selected_idx]["thickness"]

    def set_selected_thickness(self, value):
        """두께는 실행취소 대상이 아님 — on_edit 발생 없이 즉시 반영."""
        if self._selected_idx is None:
            return
        self._rects[self._selected_idx]["thickness"] = value
        self._render_overlay()

    def _emit_edit(self, kind, pre_snapshot, index=None):
        if self._on_edit and pre_snapshot != self._rects:
            self._on_edit(kind, pre_snapshot, index)

    # ── 키보드 회전 (ALT+←→: 15°, CTRL+ALT+←→: 5°) ────────────────────────

    def bind_keyboard_rotate(self, root):
        """root(Tk 최상위 창)에 전역 단축키를 건다. 마우스 드래그 회전 스냅에도
        같은 Alt/Ctrl 상태를 사용하므로, 이 위젯을 쓰는 앱은 반드시 호출해야 한다."""
        def set_alt(v):
            self._alt_held = v
        def set_ctrl(v):
            self._ctrl_held = v

        for key in ("Alt_L", "Alt_R"):
            root.bind_all(f"<KeyPress-{key}>", lambda e: set_alt(True))
            root.bind_all(f"<KeyRelease-{key}>", lambda e: set_alt(False))
        for key in ("Control_L", "Control_R"):
            root.bind_all(f"<KeyPress-{key}>", lambda e: set_ctrl(True))
            root.bind_all(f"<KeyRelease-{key}>", lambda e: set_ctrl(False))

        def on_arrow(event):
            if not self._alt_held or self._selected_idx is None:
                return None
            step = 5 if self._ctrl_held else 15
            if event.keysym == "Left":
                step = -step
            self.rotate_selected(step)
            return "break"

        root.bind_all("<Left>", on_arrow)
        root.bind_all("<Right>", on_arrow)

    # ── 렌더링 ──────────────────────────────────────────────────────────

    def _on_configure(self, event):
        if self._cv_img is None:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(50, self._render)

    def _render(self):
        self.update_idletasks()
        cw = max(self.winfo_width(),  200)
        ch = max(self.winfo_height(), 200)
        self.delete("all")
        if self._cv_img is None:
            return

        h, w = self._cv_img.shape[:2]
        self._scale = min((cw - 4) / w, (ch - 4) / h)
        nw, nh = max(1, int(w * self._scale)), max(1, int(h * self._scale))
        self._ox = max(0, (cw - nw) // 2)
        self._oy = max(0, (ch - nh) // 2)

        resized = cv2.resize(self._cv_img, (nw, nh), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        self._tk_img = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.create_image(self._ox, self._oy, anchor="nw", image=self._tk_img)
        self._render_overlay()

    def _render_overlay(self):
        self.delete("rect_overlay")
        if self._cv_img is None:
            return
        for idx, r in enumerate(self._rects):
            corners = [self._to_canvas(x, y) for x, y in rect_corners(r)]
            selected = (idx == self._selected_idx)
            outline = "#FFDD33" if selected else "#FF4444"
            flat = [v for p in corners for v in p]
            self.create_polygon(*flat, outline=outline, fill="", width=2, tags="rect_overlay")
            if self._badge_fn:
                text, color = self._badge_fn(idx)
                cx, cy = self._to_canvas(r["cx"], r["cy"])
                self.create_text(cx, cy, text=text, fill=color,
                                  font=("Segoe UI", 12, "bold"), tags="rect_overlay")
            for hx, hy in corners:
                fill = "#FFDD33" if selected else "white"
                self.create_rectangle(hx - HANDLE_R, hy - HANDLE_R, hx + HANDLE_R, hy + HANDLE_R,
                                       fill=fill, outline="#333", tags="rect_overlay")

    # ── 좌표 변환 ───────────────────────────────────────────────────────

    def _to_canvas(self, ix, iy):
        return ix * self._scale + self._ox, iy * self._scale + self._oy

    def _to_image(self, cx, cy):
        return (cx - self._ox) / self._scale, (cy - self._oy) / self._scale

    # ── 히트테스트 ──────────────────────────────────────────────────────

    def _hit_zone(self, r, cx, cy):
        return hit_zone(r, cx, cy, self._scale, self._ox, self._oy, RESIZE_HIT, ROTATE_HIT)

    # ── 드래그(이동/리사이즈/회전) ───────────────────────────────────────

    def _on_press(self, event):
        if self._cv_img is None:
            return

        for idx in reversed(range(len(self._rects))):
            zone = self._hit_zone(self._rects[idx], event.x, event.y)
            if zone is None:
                continue
            kind, corner_idx = zone
            r = self._rects[idx]
            self._pre_drag_snapshot = self.get_rects()
            self.select(idx)
            if kind == "resize":
                fixed_pt = rect_corners(r)[(corner_idx + 2) % 4]
                self._drag_mode = ("resize", idx, fixed_pt)
            else:
                ccx, ccy = self._to_canvas(r["cx"], r["cy"])
                start_mouse_angle = math.degrees(math.atan2(event.y - ccy, event.x - ccx))
                self._drag_mode = ("rotate", idx, r["angle"], start_mouse_angle)
            return

        for idx in reversed(range(len(self._rects))):
            if point_in_rect(self._rects[idx], *self._to_image(event.x, event.y)):
                r = self._rects[idx]
                ix, iy = self._to_image(event.x, event.y)
                self._pre_drag_snapshot = self.get_rects()
                self.select(idx)
                self._drag_mode = ("move", idx, ix, iy, r["cx"], r["cy"])
                return

        self._drag_mode = None
        self.select(None)

    def _on_motion(self, event):
        if not self._drag_mode:
            return
        mode, idx = self._drag_mode[0], self._drag_mode[1]
        r = self._rects[idx]
        ix, iy = self._to_image(event.x, event.y)

        if mode == "resize":
            fixed_pt = self._drag_mode[2]
            r["cx"], r["cy"], r["hw"], r["hh"] = resize_rect(
                fixed_pt, (ix, iy), r.get("angle", 0.0), MIN_HALF)
        elif mode == "rotate":
            _, _, start_angle, start_mouse_angle = self._drag_mode
            ccx, ccy = self._to_canvas(r["cx"], r["cy"])
            cur_mouse_angle = math.degrees(math.atan2(event.y - ccy, event.x - ccx))
            snap_step = (5 if self._ctrl_held else 15) if self._alt_held else None
            r["angle"] = rotate_angle(start_angle, start_mouse_angle, cur_mouse_angle, snap_step)
        else:  # move
            _, _, start_ix, start_iy, ocx, ocy = self._drag_mode
            h_img, w_img = self._cv_img.shape[:2]
            r["cx"], r["cy"] = move_rect_center(
                ocx, ocy, (start_ix, start_iy), (ix, iy), (w_img, h_img))

        self._render_overlay()

    def _on_release(self, event):
        had_drag = self._drag_mode is not None
        mode, idx = (self._drag_mode[0], self._drag_mode[1]) if had_drag else (None, None)
        self._drag_mode = None
        if had_drag:
            pre = self._pre_drag_snapshot
            self._pre_drag_snapshot = None
            self._emit_edit("drag", pre, idx)

    def _on_hover(self, event):
        if self._drag_mode or self._cv_img is None:
            return
        for r in reversed(self._rects):
            zone = self._hit_zone(r, event.x, event.y)
            if zone:
                kind, _ = zone
                self.configure(cursor="sizing" if kind == "resize" else "exchange")
                return
            if point_in_rect(r, *self._to_image(event.x, event.y)):
                self.configure(cursor="fleur")
                return
        self.configure(cursor="")
