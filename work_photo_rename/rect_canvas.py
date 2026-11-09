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
from boxes import BoxSet, MIN_HALF

HANDLE_R   = 5
RESIZE_HIT = HANDLE_R * 4
ROTATE_HIT = RESIZE_HIT + 20
EDGE_HIT   = 6
ZOOM_MIN, ZOOM_MAX = 0.3, 15.0     # 휠 확대/축소 범위 (창에 맞춘 크기 = 1.0)
ZOOM_STEP  = 1.2


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
        self._base_scale = 1.0       # 창에 맞춘 배율 (확대 1.0일 때의 배율)
        self._zoom       = 1.0
        self._pan_x = self._pan_y = 0.0
        self._pan_anchor = None

        self.boxes         = BoxSet()    # 박스 목록·선택·클립보드 (규칙은 boxes.py)
        self._group_orig   = {}
        self._drag_mode     = None   # ("resize"|"rotate"|"move"|"edge"|"marquee", idx, ...)
        self._pre_drag_snapshot = None

        self._kb_pre = None
        self._kb_job = None
        self._alt_held  = False
        self._ctrl_held = False

        self.bind("<Configure>",       self._on_configure)
        self.bind("<Button-1>",        self._on_press)
        self.bind("<B1-Motion>",       self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>",          self._on_hover)
        self.bind("<MouseWheel>",      self._on_wheel)
        for b in (2, 3):                                   # 가운데/오른쪽 버튼 드래그 = 화면 이동
            self.bind(f"<Button-{b}>",        self._pan_start)
            self.bind(f"<B{b}-Motion>",       self._pan_motion)
            self.bind(f"<ButtonRelease-{b}>", self._pan_end)

    # BoxSet 의 상태를 예전 이름 그대로 읽고 쓴다 (마우스 처리 코드가 이 이름을 많이 쓴다)
    @property
    def _rects(self):
        return self.boxes.rects

    @_rects.setter
    def _rects(self, v):
        self.boxes.rects = v

    @property
    def _sel(self):
        return self.boxes.sel

    @_sel.setter
    def _sel(self, v):
        self.boxes.sel = set(v)

    @property
    def _selected_idx(self):
        return self.boxes.primary

    @_selected_idx.setter
    def _selected_idx(self, v):
        self.boxes.primary = v

    # ── 공개 API: 이미지 / 전체 초기화 ────────────────────────────────────

    def show(self, cv_img):
        self._cv_img = cv_img
        self._zoom, self._pan_x, self._pan_y = 1.0, 0.0, 0.0     # 새 사진은 처음 배율로
        self._render()

    def reset_view(self):
        """확대/축소·이동을 원래(창에 맞춤) 상태로 되돌린다. 박스는 건드리지 않는다."""
        self._zoom, self._pan_x, self._pan_y = 1.0, 0.0, 0.0
        self._render()

    def clear(self):
        """이미지·테두리·선택을 모두 지운다 (콜백 발생 없음 — 파일 전환/빈 상태 전용). 복사해 둔 박스는 남는다."""
        self._cv_img = None
        self._tk_img = None
        self.boxes.reset()
        self._drag_mode = None
        self._zoom, self._pan_x, self._pan_y = 1.0, 0.0, 0.0
        self.delete("all")

    # ── 공개 API: 테두리 목록 ────────────────────────────────────────────

    def get_rects(self):
        """항상 깊은 복사본을 반환 — 호출자가 자유롭게 스냅샷으로 써도 안전."""
        return self.boxes.snapshot()

    def set_rects(self, rects):
        """undo/redo 복원 등, 실행취소 대상이 아닌 방식으로 테두리 목록을 통째로 교체.
        콜백을 발생시키지 않는다 — 호출자(주로 restore_fn)가 이미 전체 문맥을 알고
        있으므로 필요한 후처리(텍스트창 초기화 등)를 직접 수행한다."""
        self.boxes.replace(rects)
        self._render_overlay()

    def selected_index(self):
        return self.boxes.primary

    def selected_indices(self):
        return sorted(self.boxes.sel)

    def _set_multi(self, indices, primary):
        self.boxes.select_many(indices, primary)
        self._render_overlay()
        if self._on_select:
            self._on_select(self.boxes.primary)

    def select(self, idx):
        self.boxes.select(idx)
        self._render_overlay()
        if self._on_select:
            self._on_select(idx)

    def _edit(self, change, kind):
        """박스 규칙(change)을 실행하고 실행취소 스냅샷(on_edit)·그리기까지 처리한다. change 의 결과를 돌려준다."""
        pre = self.get_rects()
        out = change()
        # on_edit를 렌더링보다 먼저 호출한다 — badge_fn 등 렌더링 시점 콜백이
        # 호출자 쪽에서 이미 갱신된 상태(예: 텍스트 목록 길이)를 보도록 하기 위함.
        self._emit_edit(kind, pre, self.boxes.primary)
        self._render_overlay()
        return out

    def _img_size(self):
        h, w = self._cv_img.shape[:2]
        return w, h

    def add_rect(self, hw_ratio=0.125, hh_ratio=0.125, thickness=4):
        if self._cv_img is None:
            return None
        idx = self._edit(lambda: self.boxes.add(*self._img_size(), hw_ratio, hh_ratio, thickness), "add")
        if self._on_select:
            self._on_select(idx)
        return idx

    def copy_selected(self):
        """선택된 박스(여러 개면 모두)를 복사해 둔다. 복사한 개수를 돌려준다."""
        return self.boxes.copy_selected()

    def paste(self):
        """복사해 둔 박스를 사진 한가운데에 붙이고 선택한다. 붙인 개수를 돌려준다."""
        if self._cv_img is None or not self.boxes.clipboard:
            return 0
        n = self._edit(lambda: self.boxes.paste(*self._img_size()), "add")
        if self._on_select:
            self._on_select(self.boxes.primary)
        return n

    def delete_selected(self):
        """선택된 박스(여러 개면 모두)를 지운다."""
        if self.boxes.primary is None or not self.boxes.sel:
            return None
        pre = self.get_rects()
        idx = self.boxes.delete_selected()
        self._emit_edit("delete", pre, idx)
        self._render_overlay()
        return idx

    def clear_rects(self):
        if not self.boxes.rects:
            return False
        return self._edit(self.boxes.clear, "clear")

    def rotate_selected(self, delta_deg):
        if self.boxes.primary is None:
            return
        self._edit(lambda: self.boxes.rotate_selected(delta_deg), "rotate")

    def selected_thickness(self):
        return self.boxes.thickness()

    def set_selected_thickness(self, value):
        """두께는 실행취소 대상이 아님 — on_edit 발생 없이 즉시 반영."""
        self.boxes.set_thickness(value)
        self._render_overlay()

    def _emit_edit(self, kind, pre_snapshot, index=None):
        if self._on_edit and pre_snapshot != self._rects:
            self._on_edit(kind, pre_snapshot, index)

    # ── 키보드 (방향키 이동·크기·회전) ───────────────────────────────────

    def bind_keyboard(self, shortcuts):
        """선택된 박스를 방향키로 조작한다 (입력칸에 포커스가 있으면 shortcuts 가 알아서 무시).
        방향키: 이동 / Shift+방향키: 크기(←→ 가로, ↑↓ 세로) / Alt+←→: 회전 10°(Ctrl+Alt 3°)
        이동량: 기본 5단위, Ctrl을 누르면 1단위(미세 조정). 크기: 기본 3단위, Ctrl을 누르면 1단위.
        마우스 회전 스냅에도 같은 Alt/Ctrl 상태를 쓰므로, 이 위젯을 쓰는 앱은 반드시 호출해야 한다."""
        for key in ("Alt_L", "Alt_R"):
            shortcuts.bind(f"<KeyPress-{key}>", lambda e: setattr(self, "_alt_held", True), in_inputs=True)
            shortcuts.bind(f"<KeyRelease-{key}>", lambda e: setattr(self, "_alt_held", False), in_inputs=True)
        for key in ("Control_L", "Control_R"):
            shortcuts.bind(f"<KeyPress-{key}>", lambda e: setattr(self, "_ctrl_held", True), in_inputs=True)
            shortcuts.bind(f"<KeyRelease-{key}>", lambda e: setattr(self, "_ctrl_held", False), in_inputs=True)

        def on_arrow(event):
            if self._selected_idx is None:
                return None
            key = event.keysym
            if self._alt_held:
                if key in ("Left", "Right"):
                    step = 3 if self._ctrl_held else 10
                    self.rotate_selected(-step if key == "Left" else step)
                return "break"
            shift = bool(event.state & 0x1)
            base = max(1.0, 2.0 / self._scale)
            if shift:                         # 크기: 기본 3배 / Ctrl과 같이 누르면 예전 크기(1배)
                step = base * (1 if self._ctrl_held else 3)
            else:                             # 이동: 기본 5배 / Ctrl과 같이 누르면 예전 이동량(1배)
                step = base * (1 if self._ctrl_held else 5)
            dx = {"Left": -1, "Right": 1}.get(key, 0)
            dy = {"Up": -1, "Down": 1}.get(key, 0)
            if self._kb_pre is None:
                self._kb_pre = self.get_rects()
            if shift:
                # → 가로 넓힘 / ← 좁힘 / ↑ 세로 키움 / ↓ 줄임
                self.boxes.resize_selected(dx * step, -dy * step)
            else:
                self.boxes.move_selected(dx * step, dy * step, *self._img_size())
            self._render_overlay()
            if self._kb_job:
                self.after_cancel(self._kb_job)
            self._kb_job = self.after(400, self._commit_kb)
            return "break"

        for k in ("Left", "Right", "Up", "Down"):
            shortcuts.bind(f"<{k}>", on_arrow)

    def _commit_kb(self):
        """연속 방향키 입력을 실행취소 1단계로 묶어 확정한다."""
        self._kb_job = None
        pre, self._kb_pre = self._kb_pre, None
        if pre is not None:
            self._emit_edit("drag", pre, self._selected_idx)

    # ── 모서리/변 히트테스트 (변 드래그 = 한 방향 크기 조절) ──────────────────

    def _local(self, r, ix, iy):
        a = math.radians(r.get("angle", 0.0))
        dx, dy = ix - r["cx"], iy - r["cy"]
        c, s = math.cos(-a), math.sin(-a)
        return dx * c - dy * s, dx * s + dy * c

    def _classify(self, r, cx, cy):
        """한 박스에 대한 마우스 위치 판정. 우선순위: 모서리(크기) > 변(한 방향 크기) >
        박스 안쪽(이동) > 모서리 바깥 링(회전). 작은 박스에서 회전 링이 변·몸통을 가리지 않게 한다."""
        zone = self._hit_zone(r, cx, cy)
        if zone and zone[0] == "resize":
            return zone
        if self._hit_edge(r, cx, cy):
            return ("edge", 0)
        if point_in_rect(r, *self._to_image(cx, cy)):
            return ("move", 0)
        return zone                      # ("rotate", i) 또는 None

    def _hit_edge(self, r, cx, cy):
        ix, iy = self._to_image(cx, cy)
        lx, ly = self._local(r, ix, iy)
        thr = EDGE_HIT / self._scale
        if abs(ly) <= r["hh"] + thr:
            if abs(lx - r["hw"]) <= thr:
                return 0, 1
            if abs(lx + r["hw"]) <= thr:
                return 0, -1
        if abs(lx) <= r["hw"] + thr:
            if abs(ly - r["hh"]) <= thr:
                return 1, 1
            if abs(ly + r["hh"]) <= thr:
                return 1, -1
        return None

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
        self._base_scale = min((cw - 4) / w, (ch - 4) / h)
        eff = self._base_scale * self._zoom
        self._scale = eff
        nw, nh = w * eff, h * eff
        self._ox = int((cw - nw) // 2 + self._pan_x)
        self._oy = int((ch - nh) // 2 + self._pan_y)

        # 화면에 보이는 부분만 잘라서 그린다 (크게 확대해도 빠르게)
        x0 = max(0, int(math.floor(-self._ox / eff)))
        y0 = max(0, int(math.floor(-self._oy / eff)))
        x1 = min(w, int(math.ceil((cw - self._ox) / eff)))
        y1 = min(h, int(math.ceil((ch - self._oy) / eff)))
        if x1 > x0 and y1 > y0:
            crop = self._cv_img[y0:y1, x0:x1]
            cw2, ch2 = max(1, round((x1 - x0) * eff)), max(1, round((y1 - y0) * eff))
            interp = cv2.INTER_AREA if eff < 1 else cv2.INTER_LINEAR
            rgb = cv2.cvtColor(cv2.resize(crop, (cw2, ch2), interpolation=interp), cv2.COLOR_BGR2RGB)
            self._tk_img = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.create_image(self._ox + round(x0 * eff), self._oy + round(y0 * eff),
                              anchor="nw", image=self._tk_img)
        self._render_overlay()

    # ── 확대/축소 (휠) · 이동 (가운데/오른쪽 버튼 드래그) ──────────────────

    def _on_wheel(self, event):
        if self._cv_img is None or self._drag_mode:
            return
        ix, iy = self._to_image(event.x, event.y)            # 마우스 아래 지점을 고정한 채 확대/축소
        old = self._zoom
        self._zoom = max(ZOOM_MIN, min(ZOOM_MAX, self._zoom * (ZOOM_STEP if event.delta > 0 else 1 / ZOOM_STEP)))
        if self._zoom == old:
            return
        cw, ch = max(self.winfo_width(), 200), max(self.winfo_height(), 200)
        h, w = self._cv_img.shape[:2]
        eff = self._base_scale * self._zoom
        self._pan_x = event.x - ix * eff - (cw - w * eff) // 2
        self._pan_y = event.y - iy * eff - (ch - h * eff) // 2
        self._render()

    def _pan_start(self, event):
        self._pan_anchor = (event.x - self._pan_x, event.y - self._pan_y)

    def _pan_motion(self, event):
        if self._pan_anchor is None or self._cv_img is None:
            return
        self._pan_x = event.x - self._pan_anchor[0]
        self._pan_y = event.y - self._pan_anchor[1]
        self._render()

    def _pan_end(self, event):
        self._pan_anchor = None

    def _render_overlay(self):
        self.delete("rect_overlay")
        if self._cv_img is None:
            return
        for idx, r in enumerate(self._rects):
            corners = [self._to_canvas(x, y) for x, y in rect_corners(r)]
            selected = idx in self._sel
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
        self.focus_set()          # Entry에 있던 포커스를 가져와야 방향키가 박스에 적용된다
        if self._kb_job:
            self.after_cancel(self._kb_job)
            self._commit_kb()

        ctrl = bool(event.state & 0x4)
        if ctrl:                                   # Ctrl+클릭: 선택에 넣거나 뺀다
            self._drag_mode = None
            for idx in reversed(range(len(self._rects))):
                if self._classify(self._rects[idx], event.x, event.y) is not None:
                    new = set(self._sel) ^ {idx}
                    self._set_multi(new, idx if idx in new else (max(new) if new else None))
                    return
            return

        for idx in reversed(range(len(self._rects))):
            zone = self._classify(self._rects[idx], event.x, event.y)
            if zone is None or zone[0] in ("move", "edge"):
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
            edge = self._hit_edge(self._rects[idx], event.x, event.y)
            if edge and self._classify(self._rects[idx], event.x, event.y)[0] == "edge":
                r = self._rects[idx]
                self._pre_drag_snapshot = self.get_rects()
                self.select(idx)
                self._drag_mode = ("edge", idx, edge[0], edge[1], dict(r))
                return

        for idx in reversed(range(len(self._rects))):
            if point_in_rect(self._rects[idx], *self._to_image(event.x, event.y)):
                r = self._rects[idx]
                ix, iy = self._to_image(event.x, event.y)
                self._pre_drag_snapshot = self.get_rects()
                if idx in self._sel and len(self._sel) > 1:      # 여러 개 선택 중이면 같이 이동
                    self._selected_idx = idx
                    self._render_overlay()
                else:
                    self.select(idx)
                self._group_orig = {i: (self._rects[i]["cx"], self._rects[i]["cy"]) for i in self._sel}
                self._drag_mode = ("move", idx, ix, iy, r["cx"], r["cy"])
                return

        self.select(None)                          # 빈 곳: 선택 해제
        zoomed = self._zoom != 1.0 or self._pan_x or self._pan_y
        if zoomed and not (event.state & 0x1):     # 확대/이동한 상태: 끌면 사진 이동 (Shift+끌기 = 영역 선택)
            self._pan_anchor = (event.x - self._pan_x, event.y - self._pan_y)
            self._drag_mode = ("pan", None)
            self.configure(cursor="fleur")
            return
        self._drag_mode = ("marquee", None, event.x, event.y)   # 그대로: 끌면 영역 선택

    def _on_motion(self, event):
        if not self._drag_mode:
            return
        mode, idx = self._drag_mode[0], self._drag_mode[1]
        if mode == "pan":
            self._pan_motion(event)
            return
        if mode == "marquee":
            _, _, x0, y0 = self._drag_mode
            self.delete("marquee")
            self.create_rectangle(x0, y0, event.x, event.y, outline="#FFDD33", dash=(4, 3), tags="marquee")
            lo_x, hi_x = sorted((x0, event.x))
            lo_y, hi_y = sorted((y0, event.y))
            hit = []
            for i, rr in enumerate(self._rects):
                px, py = self._to_canvas(rr["cx"], rr["cy"])
                if lo_x <= px <= hi_x and lo_y <= py <= hi_y:
                    hit.append(i)
            if set(hit) != self._sel:
                self._sel = set(hit)
                self._selected_idx = max(hit) if hit else None
                self._render_overlay()
            return
        r = self._rects[idx]
        ix, iy = self._to_image(event.x, event.y)

        if mode == "edge":
            _, _, axis, sign, o = self._drag_mode
            lx, ly = self._local(o, ix, iy)          # 드래그 시작 시점 박스 기준 좌표
            half = o["hw"] if axis == 0 else o["hh"]
            fixed = -sign * half                       # 반대쪽 변은 고정
            edge = (lx if axis == 0 else ly)
            edge = fixed + sign * max(2 * MIN_HALF, sign * (edge - fixed))
            new_half = abs(edge - fixed) / 2
            shift = (edge + fixed) / 2                 # 중심이 로컬 축 방향으로 이동한 양
            a = math.radians(o.get("angle", 0.0))
            ux, uy = (math.cos(a), math.sin(a)) if axis == 0 else (-math.sin(a), math.cos(a))
            r["cx"], r["cy"] = o["cx"] + ux * shift, o["cy"] + uy * shift
            r["hw" if axis == 0 else "hh"] = new_half
        elif mode == "resize":
            fixed_pt = self._drag_mode[2]
            r["cx"], r["cy"], r["hw"], r["hh"] = resize_rect(
                fixed_pt, (ix, iy), r.get("angle", 0.0), MIN_HALF)
        elif mode == "rotate":
            _, _, start_angle, start_mouse_angle = self._drag_mode
            ccx, ccy = self._to_canvas(r["cx"], r["cy"])
            cur_mouse_angle = math.degrees(math.atan2(event.y - ccy, event.x - ccx))
            snap_step = (3 if self._ctrl_held else 10) if self._alt_held else None
            r["angle"] = rotate_angle(start_angle, start_mouse_angle, cur_mouse_angle, snap_step)
        else:  # move
            _, _, start_ix, start_iy, ocx, ocy = self._drag_mode
            h_img, w_img = self._cv_img.shape[:2]
            for i, (gx, gy) in self._group_orig.items():
                self._rects[i]["cx"], self._rects[i]["cy"] = move_rect_center(
                    gx, gy, (start_ix, start_iy), (ix, iy), (w_img, h_img))

        self._render_overlay()

    def _on_release(self, event):
        if self._drag_mode and self._drag_mode[0] == "pan":
            self._drag_mode = self._pan_anchor = None
            self.configure(cursor="")
            return
        if self._drag_mode and self._drag_mode[0] == "marquee":
            self.delete("marquee")
            self._drag_mode = None
            if self._on_select:
                self._on_select(self._selected_idx)
            return
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
            zone = self._classify(r, event.x, event.y)
            if not zone:
                continue
            kind = zone[0]
            if kind == "edge":
                axis = self._hit_edge(r, event.x, event.y)[0]
                self.configure(cursor="sb_h_double_arrow" if axis == 0 else "sb_v_double_arrow")
            else:
                self.configure(cursor={"resize": "sizing", "rotate": "exchange", "move": "fleur"}[kind])
            return
        self.configure(cursor="")
