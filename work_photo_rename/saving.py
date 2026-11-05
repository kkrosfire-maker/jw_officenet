"""저장 모듈 — 사진 한 장을 저장하는 순서를 한곳에 둔다 (한 장 저장·전체 저장이 같은 길을 쓴다).

  문구 만들기 → 최근 제약사 표기 기억 → 문구·박스(·정산불가 도장) 그리기 → 겹치지 않는 이름으로 JPG 저장
  → 지웠던 제약사 복귀 → 장부(엑셀)에 입력완료/정산불가 반영 맡기기
물어보기(통계기간 경고·저장 폴더 지정)와 메시지창은 화면(main)의 몫이다.
"""
import datetime
from collections import namedtuple

import labeling
import ledger as ledger_mod
import rxmonth

SaveResult = namedtuple("SaveResult", "path excel")     # path: 저장한 JPG 경로, excel: 장부 반영 상태 문구


def save_photo(img, source_path, hospital, pharma, rects, month, *, out_dir, ledger, settings,
               status=ledger_mod.DONE, today=None):
    """사진 한 장을 JPG로 저장하고 장부에 반영하도록 맡긴다. month 는 '10월' 같은 처방월.
    JPG 저장에 실패하면 OSError. 엑셀 반영은 백그라운드라 결과 문구만 돌려준다."""
    today = today or datetime.date.today()
    label = labeling.build_label(hospital, month, pharma)
    settings.remember_pharma(pharma)
    stamp = ledger_mod.NOSETTLE if status == ledger_mod.NOSETTLE else None     # 정산불가는 사진 가운데 빨간 글씨
    result = labeling.render(img, label, rects, stamp)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = labeling.safe_filename(label)
    if status == ledger_mod.NOSETTLE:      # 정산불가는 번호 대신 이름 뒤에 _정산불가 (겹치면 _정산불가2, 3 ...) — 일반 번호 세기에서 빠진다
        stem += "_" + ledger_mod.NOSETTLE
    out = labeling.numbered_path(out_dir, stem, ".jpg")
    if not labeling.save_jpg(result, out):
        raise OSError("JPG 인코딩 실패")
    return SaveResult(out, _record(source_path, hospital, pharma, month, status, out_dir, ledger, settings, today))


def _record(source_path, hospital, pharma, month, status, out_dir, ledger, settings, today):
    if not ledger.master:
        return "엑셀 미연결"
    ledger.set_work_path(ledger_mod.work_excel_path(out_dir, today))
    settings.unhide_pharma(hospital, pharma)                 # 지웠던 제약사를 다시 저장하면 목록에 복귀
    m = rxmonth.parse(month)
    if not ledger.record_done(source_path, hospital, month, rxmonth.year_for(m, today), pharma,
                              rxmonth.label(today.month), status):
        return "엑셀: 이미 반영됨"
    return "엑셀 반영 중…"
