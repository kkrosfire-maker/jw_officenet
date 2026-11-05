"""단축키 등록 모듈 — "글자 입력칸에 포커스가 있으면 단축키를 무시한다"는 규칙을 한곳에서 지킨다.

앱의 모든 전역 단축키(방향키·Delete·Ctrl+Z/Y·Ctrl+C/V)는 Shortcuts.bind 로 등록한다.
입력칸(skip_types)에서는 평소처럼 글자 편집이 되도록 핸들러를 부르지 않는다.
Alt/Ctrl 눌림 추적처럼 입력칸에서도 필요한 것만 in_inputs=True 로 등록한다.
같은 키에 여러 핸들러를 등록해도 서로 덮어쓰지 않는다 (add="+").
"""


class Shortcuts:
    def __init__(self, root, skip_types=()):
        self.root = root
        self.skip_types = tuple(skip_types)

    def in_input(self) -> bool:
        """지금 글자 입력칸에 포커스가 있나."""
        return bool(self.skip_types) and isinstance(self.root.focus_get(), self.skip_types)

    def bind(self, sequence, handler, in_inputs=False):
        """handler(event): None이면 다른 처리에 넘기고 "break"면 거기서 끝낸다."""
        def guarded(event):
            if not in_inputs and self.in_input():
                return None
            return handler(event)
        self.root.bind_all(sequence, guarded, add="+")
