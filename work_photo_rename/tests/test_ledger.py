import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ledger
from ledger import Ledger, MasterExcel, Schema

HEADER = ["연도", "담당자명", None, "거래처명", "처방월", "입력월", "제약사명", "통합", None, "특이사항"]
ROWS = [  # 연도, 담당자, 상태, 병원, 처방월, 입력월, 제약사, 특이사항
    (2026, "담당A", "입력완료", "다솜의원", "10월", "11월", "명문제약", None),         # 2
    (2026, "담당A", None, "다솜의원", "10월", "11월", "명문제약", None),               # 3
    (2026, "담당A", None, "다솜의원", "10월", "11월", "안국뉴팜(주)", "정산불가 품목"),   # 4
    (2026, "담당B", None, "가온의원", "10월", "11월", "코오롱제약", None),              # 5
    (2026, "담당B", "입력완료", "가온의원", "9월", "10월", "코오롱제약", "이월 메모"),    # 6 (지난 정산월)
    (2025, "담당B", "입력완료", "가온의원", "12월", "11월", "옛제약", None),            # 7 (옛 연도)
]


def formula(r):
    return f'=CONCATENATE(D{r}," ",E{r}," ",G{r})'


def make_book(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = ledger.SHEET
    ws.append(HEADER)
    for i, (y, mgr, st, h, rx, im, ph, note) in enumerate(ROWS, start=2):
        ws.append([y, mgr, st, h, rx, im, ph, formula(i), None, note])
    dv = DataValidation(type="list", formula1='"입력완료, 통계없음, 정산불가"', allow_blank=True)
    dv.add("C2:C100")
    ws.add_data_validation(dv)
    ws.auto_filter.ref = f"A1:J{len(ROWS) + 1}"
    wb.save(path)


def sheet(path):
    return openpyxl.load_workbook(path)[ledger.SHEET]


def col(ws, c):
    return [ws.cell(r, c).value for r in range(2, ws.max_row + 1)]


class LedgerTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.base = self.dir / "기본파일.xlsx"
        make_book(self.base)
        self.ledgers = []

    def tearDown(self):
        for lg in self.ledgers:
            lg.wait()                    # 뒤에서 도는 쓰기가 끝난 뒤에 임시 폴더를 지운다 (Windows 파일 잠금)
        self._tmp.cleanup()


class MarkDoneTest(LedgerTestCase):
    def test_fills_first_unfinished_row(self):
        self.assertEqual(ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "명문제약", "11월"), ("updated", 3))
        self.assertEqual(sheet(self.base).cell(3, 3).value, "입력완료")

    def test_extra_photos_are_inserted_right_below_same_case(self):
        results = [ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "명문제약", "11월") for _ in range(3)]
        self.assertEqual([r[0] for r in results], ["updated", "added", "added"])
        self.assertEqual([r[1] for r in results], [3, 4, 5])
        ws = sheet(self.base)
        self.assertEqual(col(ws, 7)[:5], ["명문제약"] * 4 + ["안국뉴팜(주)"])      # 같은 건이 붙어 있다
        self.assertEqual(ws.cell(6, 7).value, "안국뉴팜(주)")

    def test_month_spelling_08_and_8_is_the_same_month(self):
        """엑셀엔 '10월' 인데 '010월' 같은 표기가 아니라, 앞 0 유무만 다른 같은 달은 같은 건으로 본다."""
        ws = sheet(self.base)
        ws.cell(3, 5).value = "010월"                    # 다솜의원 명문제약 두 번째 줄을 앞 0 표기로
        ws.parent.save(self.base)
        self.assertEqual(ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "명문제약", "11월"), ("updated", 3))
        self.assertEqual(ledger.row_key(sheet(self.base), Schema.of(sheet(self.base)), 3)[2], 10)

    def test_numbers_are_not_appended_to_names(self):
        for _ in range(3):
            ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "명문제약", "11월")
        self.assertTrue(all(v == "명문제약" for v in col(sheet(self.base), 7)[:4]))

    def test_formulas_follow_their_rows_after_insert(self):
        for _ in range(3):
            ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "명문제약", "11월")
        ws = sheet(self.base)
        for r in range(2, ws.max_row + 1):
            self.assertEqual(ws.cell(r, 8).value, formula(r), f"{r}행 통합 수식")

    def test_autofilter_grows_with_rows(self):
        ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "명문제약", "11월")
        ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "명문제약", "11월")
        ws = sheet(self.base)
        self.assertEqual(ws.auto_filter.ref, f"A1:J{ws.max_row}")

    def test_new_pharma_goes_to_bottom_with_manager_of_hospital(self):
        kind, row = ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "신규제약", "11월")
        ws = sheet(self.base)
        self.assertEqual((kind, row), ("added", ws.max_row))
        self.assertEqual([ws.cell(row, c).value for c in (2, 3, 4, 5, 6, 7)],
                         ["담당A", "입력완료", "다솜의원", "10월", "11월", "신규제약"])

    def test_spelling_variant_fills_existing_row(self):
        self.assertEqual(ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "(주)안국뉴팜", "11월"), ("updated", 4))

    def test_manager_hint_used_for_unknown_hospital(self):
        _, row = ledger.mark_done(str(self.base), "새병원", "10월", 2026, "X제약", "11월", manager_hint="담당Z")
        self.assertEqual(sheet(self.base).cell(row, 2).value, "담당Z")

    def test_columns_found_by_header_not_position(self):
        wb = openpyxl.load_workbook(self.base)
        ws = wb[ledger.SHEET]
        ws.insert_cols(1)                       # 모든 열이 한 칸씩 밀림
        wb.save(self.base)
        sc = Schema.of(sheet(self.base))
        self.assertEqual((sc.year, sc.hospital, sc.pharma, sc.note), (2, 5, 8, 11))


class SafeSaveTest(LedgerTestCase):
    def test_failed_save_keeps_original_file(self):
        before = self.base.read_bytes()
        wb = openpyxl.load_workbook(self.base)
        def broken_save(path):                               # 저장 도중 실패: 파일만 비워 놓고 오류
            Path(path).write_bytes(b"PK" + b"" * 18)
            raise RuntimeError("저장 실패")
        wb.save = broken_save
        with self.assertRaises(RuntimeError):
            ledger._save_safely(wb, self.base)
        self.assertEqual(self.base.read_bytes(), before)
        self.assertEqual([p.name for p in self.dir.iterdir() if ".tmp." in p.name], [])


class WorkFileTest(LedgerTestCase):
    def test_contains_only_this_settlement_month_latest_year(self):
        work = self.dir / "work.xlsx"
        n = ledger.create_work_file(str(self.base), str(work), "11월")
        ws = sheet(work)
        self.assertEqual(n, 4)
        self.assertEqual(ws.max_row, 5)
        self.assertEqual({ws.cell(r, 6).value for r in range(2, 6)}, {"11월"})
        self.assertNotIn("옛제약", col(ws, 7))                 # 2025년 입력월 11월은 제외
        self.assertNotIn("이월 메모", col(ws, 10))             # 지난 정산월(10월) 줄은 제외

    def test_new_month_copies_previous_month_with_months_advanced(self):
        work = self.dir / "work.xlsx"
        n = ledger.create_work_file(str(self.base), str(work), "12월")     # 12월 입력분은 기본파일에 없음 → 11월 입력분 복사
        ws = sheet(work)
        self.assertEqual(n, 4)
        self.assertEqual(col(ws, 4), ["다솜의원", "다솜의원", "다솜의원", "가온의원"])
        self.assertEqual(set(col(ws, 5)), {"11월"})                          # 처방월 10→11
        self.assertEqual(set(col(ws, 6)), {"12월"})                          # 입력월 11→12
        self.assertEqual(col(ws, 3), [None] * 4)                             # 입력완료 표시는 비움
        self.assertIn("정산불가 품목", col(ws, 10))                            # 특이사항 유지
        self.assertEqual(ws.cell(3, 8).value, formula(3))

    def test_year_rolls_when_copying_december_to_january(self):
        wb = openpyxl.load_workbook(self.base)
        wb[ledger.SHEET].append([2026, "담당A", "입력완료", "새의원", "11월", "12월", "A제약", None, None, None])
        wb.save(self.base)
        work = self.dir / "work.xlsx"
        ledger.create_work_file(str(self.base), str(work), "1월")
        ws = sheet(work)
        self.assertEqual([ws.cell(2, c).value for c in (1, 4, 5, 6, 7)], [2027, "새의원", "12월", "1월", "A제약"])

    def test_formulas_and_validation_and_filter(self):
        work = self.dir / "work.xlsx"
        ledger.create_work_file(str(self.base), str(work), "11월")
        ws = sheet(work)
        for r in range(2, ws.max_row + 1):
            self.assertEqual(ws.cell(r, 8).value, formula(r))
        dvs = ws.data_validations.dataValidation
        self.assertEqual(len(dvs), 1)
        self.assertIn("입력완료", dvs[0].formula1)
        self.assertEqual(ws.auto_filter.ref, "A1:J5")

    def test_base_file_untouched(self):
        before = col(sheet(self.base), 7)
        ledger.create_work_file(str(self.base), str(self.dir / "work.xlsx"), "11월")
        self.assertEqual(col(sheet(self.base), 7), before)

    def test_mark_done_works_on_work_file(self):
        work = self.dir / "work.xlsx"
        ledger.create_work_file(str(self.base), str(work), "11월")
        self.assertEqual(ledger.mark_done(str(work), "다솜의원", "10월", 2026, "명문제약", "11월")[0], "updated")


class NotesTest(LedgerTestCase):
    def test_set_notes_by_spelling_variant_and_clear(self):
        self.assertEqual(ledger.set_notes(str(self.base), "다솜의원", "명문제약(주)", "메모"), 2)
        self.assertEqual(col(sheet(self.base), 10)[:2], ["메모", "메모"])
        ledger.set_notes(str(self.base), "다솜의원", "명문제약", "")
        self.assertEqual(col(sheet(self.base), 10)[:2], [None, None])

    def test_notes_for_carries_previous_month_with_tag(self):
        m = MasterExcel(str(self.base))
        notes = {g["pharma"]: g for g in m.notes_for("가온의원", month="10월")}
        self.assertEqual(notes["코오롱제약"]["note"], "이월 메모")
        self.assertEqual(notes["코오롱제약"]["tag"], "9월 기록")          # 9월 줄의 메모 -> 10월 화면에서는 이월 표시
        notes = {g["pharma"]: g for g in m.notes_for("가온의원", month="9월")}
        self.assertEqual(notes["코오롱제약"]["tag"], "")                 # 같은 처방월이면 태그 없음

    def test_user_memo_overrides_excel_note(self):
        from names import memo_key
        m = MasterExcel(str(self.base))
        memos = {memo_key("다솜의원", "안국뉴팜"): "내가 고친 메모"}
        g = {g["pharma"]: g for g in m.notes_for("다솜의원", memos)}["안국뉴팜(주)"]
        self.assertEqual((g["note"], g["tag"]), ("내가 고친 메모", ""))

    def test_notes_sorted_by_name_ignoring_marks(self):
        m = MasterExcel(str(self.base))
        self.assertEqual([g["pharma"] for g in m.notes_for("다솜의원")], ["명문제약", "안국뉴팜(주)"])


class MergeTest(LedgerTestCase):
    def _work_with_saves(self, n=3):
        work = self.dir / "work.xlsx"
        ledger.create_work_file(str(self.base), str(work), "11월")
        for _ in range(n):
            ledger.mark_done(str(work), "다솜의원", "10월", 2026, "명문제약", "11월")
        return work

    def test_merge_updates_and_adds_then_is_idempotent(self):
        work = self._work_with_saves(3)
        self.assertEqual(ledger.merge_into_base(str(work), str(self.base)), (1, 2))
        self.assertEqual(ledger.merge_into_base(str(work), str(self.base)), (0, 0))
        ws = sheet(self.base)
        self.assertEqual(col(ws, 7)[:5], ["명문제약"] * 4 + ["안국뉴팜(주)"])      # 새 줄도 같은 건 바로 아래
        for r in range(2, ws.max_row + 1):
            self.assertEqual(ws.cell(r, 8).value, formula(r))

    def test_merge_copies_notes_to_last_row_of_case(self):
        work = self._work_with_saves(1)
        ledger.set_notes(str(work), "다솜의원", "안국뉴팜", "11월 메모")
        ledger.merge_into_base(str(work), str(self.base))
        self.assertEqual(sheet(self.base).cell(4, 10).value, "11월 메모")

    def test_nosettle_is_marked_and_merged(self):
        work = self.dir / "work.xlsx"
        ledger.create_work_file(str(self.base), str(work), "11월")
        self.assertEqual(ledger.mark_done(str(work), "다솜의원", "10월", 2026, "명문제약", "11월",
                                          status=ledger.NOSETTLE), ("updated", 3))
        self.assertEqual(sheet(work).cell(3, 3).value, "정산불가")
        # 정산불가 줄은 끝난 줄이라 다음 사진이 덮어쓰지 않는다
        self.assertEqual(ledger.mark_done(str(work), "다솜의원", "10월", 2026, "명문제약", "11월")[0], "added")
        self.assertEqual(ledger.merge_into_base(str(work), str(self.base)), (1, 1))
        self.assertEqual(sheet(self.base).cell(3, 3).value, "정산불가")
        self.assertEqual(sheet(self.base).cell(4, 3).value, "입력완료")
        self.assertEqual(ledger.merge_into_base(str(work), str(self.base)), (0, 0))

    def test_merge_makes_daily_backup(self):
        work = self._work_with_saves(1)
        ledger.merge_into_base(str(work), str(self.base))
        self.assertEqual(len(list((self.dir / "백업").glob("기본파일_(*).xlsx"))), 1)


class CleanNamesTest(LedgerTestCase):
    def test_strips_trailing_numbers_with_backup(self):
        wb = openpyxl.load_workbook(self.base)
        wb[ledger.SHEET].cell(2, 7).value = "명문제약 (2)"
        wb[ledger.SHEET].cell(3, 7).value = "명문제약3"
        wb.save(self.base)
        self.assertEqual(ledger.clean_names(str(self.base)), 2)
        self.assertEqual(col(sheet(self.base), 7)[:2], ["명문제약", "명문제약"])
        self.assertEqual(len(list((self.dir / "백업").glob("*번호제거전*"))), 1)
        self.assertEqual(ledger.clean_names(str(self.base)), 0)


class MasterReadTest(LedgerTestCase):
    def test_hospital_with_and_without_uiwon_are_one(self):
        wb = openpyxl.load_workbook(self.base)
        ws = wb[ledger.SHEET]
        ws.append([2026, "담당B", "입력완료", "라임비뇨기과의원", "9월", "10월", "가제약", None, None, None])
        ws.append([2026, "담당B", None, "라임비뇨기과", "10월", "11월", "나제약", None, None, None])
        wb.save(self.base)
        m = MasterExcel(str(self.base))
        self.assertEqual([h for h in m.hospitals() if h.startswith("라임")], ["라임비뇨기과"])   # 가장 최근 줄의 표기
        self.assertEqual(sorted(m.hospital_pharmas("라임비뇨기과", "10월")), ["가제약", "나제약"])

    def test_same_month_alias_tie_prefers_uiwon_and_mark_done_matches_either(self):
        wb = openpyxl.load_workbook(self.base)
        ws = wb[ledger.SHEET]
        ws.append([2026, "담당B", None, "라임비뇨기과의원", "10월", "11월", "가제약", None, None, None])
        ws.append([2026, "담당B", None, "라임비뇨기과", "10월", "11월", "가제약", None, None, None])
        wb.save(self.base)
        m = MasterExcel(str(self.base))
        self.assertEqual([h for h in m.hospitals() if h.startswith("라임")], ["라임비뇨기과의원"])   # 같은 달이면 긴 표기
        kind, row = ledger.mark_done(str(self.base), "라임비뇨기과의원", "10월", 2026, "가제약", "11월")
        self.assertEqual(kind, "updated")          # 엑셀에 '의원' 없는 줄이 있어도 같은 병원으로 찾는다

    def test_mark_done_puts_1_in_column_i(self):
        kind, row = ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "명문제약", "11월")
        ws = openpyxl.load_workbook(self.base)[ledger.SHEET]
        self.assertEqual(ws.cell(row, 9).value, 1)                       # 기존 줄 갱신
        kind, row = ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "신규제약", "11월", status="정산불가")
        ws = openpyxl.load_workbook(self.base)[ledger.SHEET]
        self.assertEqual((kind, ws.cell(row, 9).value), ("added", 1))    # 새 줄 (정산불가도)

    def test_mark_done_writes_note_and_empty_clears(self):
        kind, row = ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "명문제약", "11월", note="이월 메모")
        ws = openpyxl.load_workbook(self.base)[ledger.SHEET]
        self.assertEqual(ws.cell(row, 10).value, "이월 메모")
        kind, row = ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "명문제약", "11월", note="  ")
        ws = openpyxl.load_workbook(self.base)[ledger.SHEET]
        self.assertEqual((kind, ws.cell(row, 10).value), ("added", None))      # 지운 채로 저장
        kind, row = ledger.mark_done(str(self.base), "다솜의원", "10월", 2026, "신규제약", "11월")
        self.assertIsNone(openpyxl.load_workbook(self.base)[ledger.SHEET].cell(row, 10).value)

    def test_recent_months_is_four(self):
        self.assertEqual(MasterExcel.RECENT_MONTHS, 4)

    def test_hospital_pharmas_current_month_first(self):
        m = MasterExcel(str(self.base))
        self.assertEqual(m.hospital_pharmas("가온의원", "10월")[0], "코오롱제약")

    def test_names_prefer_most_recent_year_spelling(self):
        wb = openpyxl.load_workbook(self.base)
        wb[ledger.SHEET].cell(7, 7).value = "코오롱제약(주)"     # 2025년 줄의 표기
        wb.save(self.base)
        self.assertEqual(MasterExcel(str(self.base)).names.display("코오롱제약"), "코오롱제약")  # 2026년 표기가 대표

    def test_guess_from_filename(self):
        m = MasterExcel(str(self.base))
        self.assertEqual(m.guess_from_filename("C:/x/다솜 10월 안국뉴팜.png"), ("다솜의원", "안국뉴팜(주)"))
        self.assertEqual(m.guess_from_filename("C:/x/없는병원.png"), (None, None))

    def test_match_pharma_prefers_hospitals_own(self):
        m = MasterExcel(str(self.base))
        name, _ = m.match_pharma("안국뉴퐘", hospital="다솜의원")
        self.assertEqual(name, "안국뉴팜(주)")


class LedgerFacadeTest(LedgerTestCase):
    def _wait(self, lg):
        events, t = [], time.time()
        while lg.pending and time.time() - t < 30:
            events += lg.poll()
            time.sleep(0.05)
        return events + lg.poll()

    def _ledger(self):
        lg = Ledger(self.base)
        self.ledgers.append(lg)
        lg.load()
        lg.set_work_path(self.dir / "out" / "1.통계입력_2611.xlsx")
        return lg

    def test_record_done_creates_work_file_and_updates_history(self):
        lg = self._ledger()
        self.assertTrue(lg.record_done("a.png", "다솜의원", "10월", 2026, "신규제약", "11월"))
        ev = self._wait(lg)
        self.assertEqual([e.kind for e in ev], ["done"])
        self.assertTrue(lg.work.exists())
        self.assertIn("신규제약", lg.master.all_pharmas())          # 새 제약사가 후보에 들어옴
        self.assertEqual(sheet(self.base).max_row, 7)               # 기본파일은 그대로

    def test_hidden_pharma_leaves_lists_and_returns_when_saved_again(self):
        lg = self._ledger()
        names = lambda: [g["pharma"] for g in lg.master.notes_for("다솜의원")]
        self.assertIn("명문제약", names())
        lg.hidden.add(ledger.memo_key("다솜의원", "명문제약"))
        self.assertNotIn("명문제약", names())                                        # 특이사항에서 빠짐
        self.assertNotIn("명문제약", lg.master.hospital_pharmas("다솜의원"))           # 입력 후보에서도 빠짐
        self.assertIn("명문제약", lg.master.all_pharmas())                           # 엑셀 기록·전체 후보는 그대로
        self.assertIn("명문제약", [g["pharma"] for g in lg.master.notes_for("가온의원")] + ["명문제약"])
        lg.record_done("a.png", "다솜의원", "10월", 2026, "명문제약", "11월")        # 다시 저장하면 복귀
        self._wait(lg)
        self.assertIn("명문제약", names())

    def test_new_pharma_appears_in_notes_after_save(self):
        lg = self._ledger()
        lg.record_done("a.png", "다솜의원", "10월", 2026, "신규제약", "11월")
        self._wait(lg)
        self.assertIn("신규제약", [g["pharma"] for g in lg.master.notes_for("다솜의원")])

    def test_same_photo_same_name_not_recorded_twice(self):
        lg = self._ledger()
        self.assertTrue(lg.record_done("a.png", "다솜의원", "10월", 2026, "명문제약", "11월"))
        self.assertFalse(lg.record_done("a.png", "다솜의원", "10월", 2026, "명문제약", "11월"))
        self._wait(lg)
        self.assertTrue(lg.record_done("a.png", "다솜의원", "10월", 2026, "안국뉴팜", "11월"))   # 이름 바꾸면 다시 반영

    def test_jobs_processed_in_order(self):
        lg = self._ledger()
        for i in range(3):
            lg.record_done(f"{i}.png", "다솜의원", "10월", 2026, "명문제약", "11월")
        self._wait(lg)
        ws = sheet(lg.work)
        self.assertEqual(col(ws, 7)[:3], ["명문제약"] * 3)
        self.assertEqual([ws.cell(r, 3).value for r in range(2, 5)], ["입력완료"] * 3)

    def test_error_event_allows_retry(self):
        lg = self._ledger()
        lg.work.parent.mkdir(parents=True)
        lg.work.write_text("not an excel file")                     # 깨진 작업 파일
        lg.record_done("a.png", "다솜의원", "10월", 2026, "명문제약", "11월")
        ev = self._wait(lg)
        self.assertEqual([e.kind for e in ev], ["error"])
        lg.work.unlink()
        self.assertTrue(lg.record_done("a.png", "다솜의원", "10월", 2026, "명문제약", "11월"))   # 실패한 건 다시 가능
        self.assertEqual([e.kind for e in self._wait(lg)], ["done"])

    def test_set_note_needs_work_file(self):
        lg = self._ledger()
        self.assertFalse(lg.set_note("다솜의원", "안국뉴팜", "x"))
        lg.record_done("a.png", "다솜의원", "10월", 2026, "명문제약", "11월")
        self._wait(lg)
        self.assertTrue(lg.set_note("다솜의원", "안국뉴팜", "새 메모"))
        self._wait(lg)
        self.assertIn("새 메모", col(sheet(lg.work), 10))

    def test_complete_merges_and_refuses_while_pending(self):
        lg = self._ledger()
        lg.record_done("a.png", "다솜의원", "10월", 2026, "명문제약", "11월")
        with self.assertRaises(RuntimeError):
            lg.complete()
        self._wait(lg)
        self.assertEqual(lg.complete(), (1, 0))
        self.assertEqual(sheet(self.base).cell(3, 3).value, "입력완료")

    def test_complete_without_work_file(self):
        with self.assertRaises(FileNotFoundError):
            self._ledger().complete()

    def test_wait_blocks_until_jobs_done(self):
        lg = self._ledger()
        lg.record_done("a.png", "다솜의원", "10월", 2026, "명문제약", "11월")
        lg.wait()
        self.assertTrue(lg.work.exists())


if __name__ == "__main__":
    unittest.main()
