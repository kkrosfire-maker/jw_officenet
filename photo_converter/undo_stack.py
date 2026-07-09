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


class HistoryController:
    """UndoStack 위에서 snapshot/restore 오케스트레이션과 Ctrl+Z/Y 키바인딩까지 담당.

    snapshot_fn(): 현재 상태의 스냅샷을 만들어 반환 (undo/redo 시 "돌아올 자리"를 기록하는 데 씀).
    restore_fn(snapshot): 스냅샷을 실제 상태로 되돌리고 필요한 후처리(재렌더링 등)를 수행.
    """

    def __init__(self, snapshot_fn, restore_fn, limit=50):
        self._stack = UndoStack(limit=limit)
        self._snapshot_fn = snapshot_fn
        self._restore_fn = restore_fn

    def push(self, snapshot):
        self._stack.push(snapshot)

    def clear(self):
        self._stack.clear()

    def undo(self):
        prev = self._stack.undo(self._snapshot_fn())
        if prev is None:
            return False
        self._restore_fn(prev)
        return True

    def redo(self):
        nxt = self._stack.redo(self._snapshot_fn())
        if nxt is None:
            return False
        self._restore_fn(nxt)
        return True

    def bind_keys(self, root, ignore_types=(), status_fn=None):
        """root에 Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z를 전역 바인딩한다.
        ignore_types에 해당하는 위젯(Entry 등)에 포커스가 있으면 무시(기본 동작에 위임).
        status_fn(action, ok): action은 "undo"|"redo", ok는 실행 성공 여부."""
        def guarded(action, fn):
            def handler(event=None):
                if ignore_types and isinstance(root.focus_get(), ignore_types):
                    return None
                ok = fn()
                if status_fn:
                    status_fn(action, ok)
                return "break"
            return handler

        root.bind_all("<Control-z>", guarded("undo", self.undo))
        root.bind_all("<Control-y>", guarded("redo", self.redo))
        root.bind_all("<Control-Z>", guarded("redo", self.redo))
