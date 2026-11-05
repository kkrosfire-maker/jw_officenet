"""사진별 조정 기억 — 회전 횟수와 사용자가 맞춘 꼭짓점을 한 묶음으로 관리.

핵심 규칙(불변식): 꼭짓점은 "저장 당시의 회전 상태" 좌표계 기준이므로,
회전이 바뀌면 저장된 꼭짓점은 즉시 무효가 된다. 이 규칙을 읽는 쪽이 아니라
이 클래스가 보장한다.
"""


class PhotoEdits:
    def __init__(self):
        self._rot = {}   # 파일경로 -> 시계방향 90도 횟수 (0~3)
        self._pts = {}   # 파일경로 -> 꼭짓점 [[x, y] * 4] (현재 회전 상태 기준)

    def rotation(self, path) -> int:
        return self._rot.get(path, 0)

    def turn(self, path, delta: int):
        """회전을 delta번(시계방향 +) 더하고, 좌표계가 바뀌었으므로 저장된 꼭짓점은 버린다."""
        self._rot[path] = (self.rotation(path) + delta) % 4
        self._pts.pop(path, None)

    def save_pts(self, path, pts):
        """현재 회전 상태 기준의 꼭짓점을 기억한다. 4개가 아니면 무시."""
        if len(pts) == 4:
            self._pts[path] = [list(p) for p in pts]

    def saved_pts(self, path):
        """저장된 꼭짓점(없으면 None). 항상 복사본."""
        pts = self._pts.get(path)
        return [list(p) for p in pts] if pts else None

    def copy(self) -> "PhotoEdits":
        """스레드로 넘길 때 쓰는 독립 복사본."""
        c = PhotoEdits()
        c._rot = dict(self._rot)
        c._pts = {k: [list(p) for p in v] for k, v in self._pts.items()}
        return c
