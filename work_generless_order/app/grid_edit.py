"""Treeview 셀을 그 자리에서 고쳐 쓰는 인라인 편집기.

주문 그리드와 품목 마스터 그리드가 같은 조작감을 갖도록 편집기 자체(Entry 배치,
커밋/취소, Enter 이동)만 여기에 두고, "무엇을 고칠 수 있고 고친 값을 어디에
반영하는지"는 각 화면이 콜백으로 넘긴다.
"""
import tkinter as tk

from app import theme


class InlineCellEditor:
    """tree 위에 Entry를 띄워 셀 값을 편집한다.

    on_commit(row_iid, col, value): 편집 결과를 반영한다. 다음으로 이어서 편집할
        (row_iid, col)을 반환하면 Enter로 커밋했을 때 그 셀로 이동한다.
    is_editable(row_iid, col): 해당 셀을 편집할 수 있는지.
    initial_value(row_iid, col): Entry에 채울 초기값(기본값은 화면에 보이는 값).
    """

    def __init__(self, tree, columns, on_commit, is_editable,
                 left_aligned=frozenset(), initial_value=None):
        self.tree = tree
        self.columns = tuple(columns)
        self.on_commit = on_commit
        self.is_editable = is_editable
        self.left_aligned = left_aligned
        self.initial_value = initial_value or (lambda row_iid, col: tree.set(row_iid, col))
        self._active: tuple | None = None

    # ---- 클릭 처리 ----
    def handle_click(self, event) -> str | None:
        """Treeview <Button-1> 핸들러에서 호출. 편집을 시작했으면 'break'를 반환한다."""
        if self.tree.identify("region", event.x, event.y) != "cell":
            return None
        row_iid = self.tree.identify_row(event.y)
        col_name = self.column_at(event.x)
        if not row_iid or col_name is None or not self.is_editable(row_iid, col_name):
            return None

        self.commit_active()
        # 클릭 이벤트가 끝난 뒤에 열어야 Treeview 선택 처리와 겹치지 않는다.
        self.tree.after(1, lambda: self.begin(row_iid, col_name))
        return None

    def column_at(self, x: int) -> str | None:
        col_id = self.tree.identify_column(x)
        if not col_id:
            return None
        idx = int(col_id.replace("#", "")) - 1
        if idx < 0 or idx >= len(self.columns):
            return None
        return self.columns[idx]

    # ---- 편집기 수명주기 ----
    def begin(self, row_iid: str, col_name: str) -> None:
        if not self.tree.exists(row_iid):
            return
        bbox = self.tree.bbox(row_iid, col_name)
        if not bbox:
            return
        x, y, width, height = bbox

        entry = tk.Entry(self.tree, font=theme.FONT_BASE,
                         justify="left" if col_name in self.left_aligned else "center")
        entry.insert(0, self.initial_value(row_iid, col_name))
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()
        entry.select_range(0, "end")

        def commit(event=None):
            if self._active is None or self._active[0] is not entry:
                return
            value = entry.get()
            moving = event is not None and getattr(event, "keysym", None) in ("Return", "KP_Enter")
            self._active = None
            entry.destroy()
            nxt = self.on_commit(row_iid, col_name, value)
            if moving and nxt:
                self.begin(*nxt)

        def cancel(_event=None):
            if self._active is None or self._active[0] is not entry:
                return
            self._active = None
            entry.destroy()

        self._active = (entry, commit)
        entry.bind("<Return>", commit)
        entry.bind("<KP_Enter>", commit)
        entry.bind("<Escape>", cancel)
        entry.bind("<FocusOut>", commit)

    def commit_active(self) -> None:
        """열려 있는 편집기를 즉시 커밋한다."""
        if self._active is not None:
            self._active[1]()

    def cancel_active(self) -> None:
        """열려 있는 편집기를 커밋하지 않고 닫는다."""
        if self._active is None:
            return
        entry = self._active[0]
        self._active = None
        entry.destroy()
