"""사진별 작업 기록 모듈 — 통계 사진 한 장마다 사용자가 입력한 것과 프로그램이 읽어 낸 것을 한곳에 모은다.

한 장의 기록(Photo): 병원명·제약사명·박스·통계기간(OCR)·사진에서 읽은 제약사 글자.
PhotoBook은 그 기록들을 사진 경로로 찾아 주고, 화면 없이 판단할 수 있는 규칙을 맡는다.
  - '입력이 끝난 사진'(병원명·제약사명이 모두 있음) 판정 → 다른 그림으로 넘어갈 때 자동 체크, 전체 저장 대상 선정
  - 선택한 처방월과 통계기간이 맞지 않는 사진 찾기
  - 같은 병원에서 이미 작업이 끝난(체크된) 제약사 이름 모으기 (드롭다운 ✓ 표시용)
체크 상태 자체(체크박스)는 화면이 가지고 있고, 여기서는 '체크된 경로 집합'을 받아서 쓴다.
"""
from dataclasses import dataclass, field
from pathlib import Path

import period_check
from names import norm


@dataclass
class Photo:
    path: str
    hospital: str = ""
    pharma: str = ""
    rects: list = field(default_factory=list)
    opened: bool = False              # 한 번이라도 열어서 입력 상태를 저장했는가 (처음 여는 사진 판정)
    period: object = None             # OCR로 읽은 ((년,월,일),(년,월,일)); None=못 읽음
    period_read: bool = False         # OCR이 끝났는가 (False면 아직 안 읽음)
    ocr_pharma: object = None         # 사진 상단에서 읽은 제약사 글자 (없으면 None)

    @property
    def ready(self) -> bool:
        """병원명·제약사명이 모두 입력됐나 (저장할 수 있는 상태)."""
        return bool(self.hospital.strip() and self.pharma.strip())


class PhotoBook:
    def __init__(self):
        self._photos = {}

    def get(self, path) -> Photo:
        """경로의 기록 (없으면 빈 기록을 만들어 돌려준다)."""
        ph = self._photos.get(path)
        if ph is None:
            ph = self._photos[path] = Photo(path)
        return ph

    # ── 입력 ────────────────────────────────────────────────────────────

    def record(self, path, hospital, pharma, rects):
        """지금 화면에 입력된 내용을 그 사진의 기록으로 저장한다."""
        ph = self.get(path)
        ph.hospital, ph.pharma, ph.rects, ph.opened = hospital, pharma, list(rects), True

    def copy_of(self, src, dst):
        """src 사진의 복사본(dst) 기록: 병원명·통계기간만 이어받고, 제약사·박스는 비운다 (같은 원본으로 다른 통계를 만들 용도)."""
        s = self.get(src)
        d = self.get(dst)
        d.hospital, d.opened = s.hospital, True
        d.period, d.period_read = s.period, s.period_read
        return d

    def set_period(self, path, period):
        ph = self.get(path)
        ph.period, ph.period_read = period, True

    def set_ocr_pharma(self, path, raw):
        self.get(path).ocr_pharma = raw

    # ── 판단 ────────────────────────────────────────────────────────────

    def is_ready(self, path) -> bool:
        ph = self._photos.get(path)
        return bool(ph and ph.ready)

    def period_status(self, path, year, month):
        """(ok, 사유). 아직 OCR을 안 했으면 None."""
        ph = self._photos.get(path)
        if not ph or not ph.period_read:
            return None
        return period_check.check_period(ph.period, year, month)

    def plan_save(self, paths):
        """전체 저장 대상 선정: ([저장할 Photo...], [건너뛴 파일명...]). 목록 순서를 유지한다."""
        todo, skipped = [], []
        for p in paths:
            ph = self._photos.get(p)
            if ph and ph.ready:
                todo.append(ph)
            else:
                skipped.append(Path(p).name)
        return todo, skipped

    def period_problems(self, photos, year, month):
        """통계기간 확인이 필요한 사진 파일명들 (OCR이 끝났고 선택한 연/월과 맞지 않는 것만)."""
        out = []
        for ph in photos:
            status = self.period_status(ph.path, year, month)
            if status is not None and not status[0]:
                out.append(Path(ph.path).name)
        return out

    def pharma_norms_done(self, hospital, checked_paths):
        """그 병원에서 이미 체크된(작업이 끝난) 사진들의 제약사 이름(정규화) 집합."""
        h = norm(hospital)
        if not h:
            return set()
        out = set()
        for p in checked_paths:
            ph = self._photos.get(p)
            if ph and norm(ph.hospital) == h and ph.pharma.strip():
                out.add(norm(ph.pharma))
        return out
