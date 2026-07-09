"""좌측 파일 목록(ThumbPanel)과 짝을 이루는 파일 추가/삭제/선택 오케스트레이션.

ThumbPanel은 "화면에 어떻게 그릴지"만 알고, "삭제 시 어느 인덱스로 이동할지"
같은 목록 관리 판단은 이 컨트롤러가 맡는다. 실제 이미지 로드·빈 상태 초기화는
앱마다 달라서 on_load(path)/on_empty() 콜백으로 위임한다.
"""
from tkinter import messagebox


class FileListController:
    def __init__(self, thumb_panel, *, on_load, on_empty, nav=None, nav_label=None, status=None):
        """
        thumb_panel: ThumbPanel 인스턴스
        on_load(path): 활성 파일이 바뀌어 화면에 로드해야 할 때 호출
        on_empty(): 목록이 완전히 비었을 때 호출 (앱이 자기 상태를 초기화)
        nav: ◀▶ 내비게이션 tk.Frame — 파일이 2개 이상일 때만 보인다. None이면 표시 로직 생략.
        nav_label: "n / m" tk.Label. None이면 갱신 생략.
        status(text): 상태표시줄 갱신 콜백 (선택)
        """
        self._panel    = thumb_panel
        self._on_load  = on_load
        self._on_empty = on_empty
        self._nav       = nav
        self._nav_label = nav_label
        self._status     = status

        self.files = []
        self.index = 0

    def _set_status(self, text):
        if self._status:
            self._status(text)

    def _update_nav(self):
        if self._nav_label:
            self._nav_label.config(text=f"{self.index + 1} / {len(self.files)}")

    def add_files(self, new_paths: list):
        """중복 경로 제외 후 목록에 추가. 첫 번째 새 파일로 이동."""
        existing = set(self.files)
        to_add   = [p for p in new_paths if p not in existing]
        if not to_add:
            self._set_status("추가할 새 파일이 없습니다. (모두 이미 목록에 있음)")
            return
        first_new = len(self.files)
        self.files.extend(to_add)
        self.index = first_new
        if self._nav and len(self.files) > 1:
            self._nav.pack(side="right", padx=8)
        self._on_load(self.files[first_new])
        self._update_nav()
        self._panel.rebuild(self.files, self.index)

    def select(self, idx: int):
        """썸네일 클릭 또는 ◀▶ 로 파일 이동 — 저장 없이 전환."""
        if not self.files or not (0 <= idx < len(self.files)):
            return
        self.index = idx
        self._update_nav()
        self._panel.highlight(idx)
        self._panel.scroll_to(idx)
        self._on_load(self.files[idx])

    def prev(self):
        self.select(self.index - 1)

    def next(self):
        self.select(self.index + 1)

    def remove(self, idx: int):
        if not self.files or not (0 <= idx < len(self.files)):
            return
        active = self.index
        self._panel.forget_cache(self.files[idx])
        self.files.pop(idx)

        if not self.files:
            self.index = 0
            if self._nav:
                self._nav.pack_forget()
            self._panel.rebuild(self.files, self.index)
            self._on_empty()
            return

        # 지금 보고 있던 파일이 아닌 다른 항목을 지운 경우, 미리보기를 바꾸지 않고
        # 인덱스만 목록 축소분만큼 보정한다.
        if idx == active:
            self.index = min(idx, len(self.files) - 1)
            reload_preview = True
        else:
            self.index = active - 1 if idx < active else active
            reload_preview = False

        if self._nav and len(self.files) == 1:
            self._nav.pack_forget()
        if reload_preview:
            self._on_load(self.files[self.index])
        self._update_nav()
        self._panel.remove_item(idx, self.index)   # 전체 재구성 대신 항목 하나만 제거 (버벅임 방지)

    def remove_current(self):
        if self.files and 0 <= self.index < len(self.files):
            self.remove(self.index)

    def remove_selected(self):
        """썸네일 체크박스가 선택된(체크된) 항목들을 확인 후 한번에 삭제."""
        idxs = self._panel.checked_indices()
        if not idxs:
            messagebox.showinfo("알림", "선택된 파일이 없습니다.\n썸네일 체크박스를 확인해 주세요.")
            return
        if not messagebox.askyesno(
                "선택 삭제",
                f"체크된 {len(idxs)}개 파일을 목록에서 삭제할까요?\n"
                f"(실제 파일은 삭제되지 않고, 목록에서만 제외됩니다)"):
            return
        for i in sorted(idxs, reverse=True):
            self.remove(i)
