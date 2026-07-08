"""스냅샷 기반 범용 실행취소/다시실행 스택.

스냅샷의 의미(어떤 상태를 담고 있는지)는 이 클래스가 알 필요가 없다 —
호출자가 만들고(예: 리스트/딕셔너리의 깊은 복사) 복원한다.
"""


class UndoStack:
    def __init__(self, limit=50):
        self._undo = []
        self._redo = []
        self._limit = limit

    def push(self, snapshot):
        """조작 시작 전 스냅샷을 undo 스택에 쌓고 redo 스택을 비운다."""
        self._undo.append(snapshot)
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self, current_snapshot):
        """
        current_snapshot(되돌아올 현재 상태)을 redo에 보관하고 가장 최근
        스냅샷을 꺼내 반환한다. 되돌릴 것이 없으면 None.
        """
        if not self._undo:
            return None
        self._redo.append(current_snapshot)
        return self._undo.pop()

    def redo(self, current_snapshot):
        if not self._redo:
            return None
        self._undo.append(current_snapshot)
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        return self._redo.pop()

    def clear(self):
        self._undo.clear()
        self._redo.clear()

    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)
