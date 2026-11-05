"""박스 묶음 모듈 — 사진 위 빨간 박스들과 그 선택·복사·이동 규칙. 화면(tk) 없이 쓴다.

박스 하나는 딕셔너리: cx, cy(중심) / hw, hh(가로·세로 반길이) / angle(도) / thickness(두께).
좌표는 원본 사진 기준 픽셀. 마우스 드래그·그리기는 RectCanvas(위젯)가 맡고, 목록·선택·클립보드·
키보드 이동/크기/회전·추가·삭제 같은 규칙은 여기에서만 한다.

  선택: sel(선택된 번호들) + primary(대표 = 마지막으로 고른 박스)
  클립보드: Ctrl+C로 복사한 박스들. 사진을 바꿔도 유지된다 (크기를 맞춘 박스를 다른 사진에 붙이는 용도).
"""
MIN_HALF = 8


class BoxSet:
    def __init__(self):
        self.rects = []
        self.sel = set()
        self.primary = None
        self.clipboard = []

    # ── 목록 ────────────────────────────────────────────────────────────

    def snapshot(self):
        """항상 깊은 복사본 — 실행취소 스냅샷으로 써도 안전."""
        return [dict(r) for r in self.rects]

    def replace(self, rects):
        """목록을 통째로 교체 (실행취소 복원 등). 선택은 풀린다."""
        self.rects = [dict(r) for r in rects]
        self.deselect()

    def reset(self):
        """사진을 비울 때: 박스·선택을 모두 지운다 (클립보드는 남는다)."""
        self.rects = []
        self.deselect()

    def deselect(self):
        self.sel, self.primary = set(), None

    def select(self, idx):
        self.primary = idx
        self.sel = {idx} if idx is not None else set()

    def select_many(self, indices, primary):
        self.sel = set(indices)
        self.primary = primary if self.sel else None

    # ── 편집 (바뀌었으면 True / 값을 돌려준다) ────────────────────────────

    def add(self, img_w, img_h, hw_ratio=0.125, hh_ratio=0.125, thickness=4):
        """사진 한가운데에 새 박스를 만들어 선택한다. 새 번호를 돌려준다."""
        self.rects.append({"cx": img_w / 2, "cy": img_h / 2, "hw": img_w * hw_ratio, "hh": img_h * hh_ratio,
                           "angle": 0.0, "thickness": thickness})
        idx = len(self.rects) - 1
        self.select(idx)
        return idx

    def delete_selected(self):
        """선택된 박스(여러 개면 모두)를 지운다. 지운 대표 번호, 지울 게 없으면 None."""
        if self.primary is None or not self.sel:
            return None
        idx = self.primary
        for i in sorted(self.sel, reverse=True):
            if 0 <= i < len(self.rects):
                del self.rects[i]
        self.deselect()
        return idx

    def clear(self):
        if not self.rects:
            return False
        self.rects = []
        self.deselect()
        return True

    def rotate_selected(self, delta_deg):
        if self.primary is None:
            return False
        for i in self.sel:
            r = self.rects[i]
            r["angle"] = (r["angle"] + delta_deg) % 360
        return True

    def move_selected(self, dx, dy, img_w, img_h):
        """선택한 박스들을 (dx, dy)만큼 옮긴다. 중심이 사진 밖으로 나가지 않게 한다."""
        for i in self.sel:
            r = self.rects[i]
            r["cx"] = max(0.0, min(float(img_w), r["cx"] + dx))
            r["cy"] = max(0.0, min(float(img_h), r["cy"] + dy))

    def resize_selected(self, dw, dh):
        """선택한 박스들의 가로를 dw, 세로를 dh만큼 키운다(음수면 줄임). 박스 자체의 가로·세로 기준이라 회전해도 같다."""
        for i in self.sel:
            r = self.rects[i]
            r["hw"] = max(MIN_HALF, r["hw"] + dw / 2)
            r["hh"] = max(MIN_HALF, r["hh"] + dh / 2)

    def thickness(self):
        return None if self.primary is None else self.rects[self.primary]["thickness"]

    def set_thickness(self, value):
        if self.primary is not None:
            self.rects[self.primary]["thickness"] = value

    # ── 복사·붙여넣기 ────────────────────────────────────────────────────

    def copy_selected(self):
        """선택된 박스들을 클립보드에 담는다. 담은 개수를 돌려준다 (선택이 없으면 클립보드는 그대로, 0)."""
        picked = [dict(self.rects[i]) for i in sorted(self.sel) if 0 <= i < len(self.rects)]
        if picked:
            self.clipboard = picked
        return len(picked)

    def paste(self, img_w, img_h):
        """클립보드의 박스들을 사진 한가운데에 붙이고 선택한다 (너비·높이·회전·두께 그대로,
        여러 개면 서로의 위치 관계 유지). 붙인 개수를 돌려준다."""
        if not self.clipboard:
            return 0
        mx = sum(r["cx"] for r in self.clipboard) / len(self.clipboard)
        my = sum(r["cy"] for r in self.clipboard) / len(self.clipboard)
        start = len(self.rects)
        for r in self.clipboard:
            n = dict(r)
            n["cx"], n["cy"] = img_w / 2 + (r["cx"] - mx), img_h / 2 + (r["cy"] - my)
            self.rects.append(n)
        new = list(range(start, len(self.rects)))
        self.select_many(new, new[-1])
        return len(new)
