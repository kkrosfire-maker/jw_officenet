import os
import sys
import tempfile
import unittest
import zipfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import openpyxl  # noqa: E402
from report import build_excel  # noqa: E402


def task(i, text, day, done=None, due=None, **kw):
    return {"id": i, "text": text, "date": day, "created_at": day + "T08:00:00", "done_at": done, "note": "", "parent": None,
            "due": due or day, **kw}


TASKS = [
    task("a", "빠른 완료", "2026-10-20", "2026-10-20T10:00:00"),
    task("b", "늦은 완료", "2026-10-19", "2026-10-22T10:00:00", due="2026-10-20", note="메모"),
    task("c", "아직", "2026-10-21"),
    task("d", "후속", "2026-10-22", parent="b"),
]


class Excel(unittest.TestCase):
    def build(self, start="", end=""):
        path = os.path.join(tempfile.mkdtemp(), "t.xlsx")
        n, done = build_excel(TASKS, start, end, path, date(2026, 10, 22))
        return path, n, done

    def test_counts_and_done_ids(self):
        _, n, done = self.build()
        self.assertEqual((n, sorted(done)), (4, ["a", "b"]))

    def test_period_filter(self):
        _, n, _ = self.build("2026-10-21", "2026-10-22")
        self.assertEqual(n, 3)  # b 는 10/22 에 완료돼 포함

    def test_sheet_order_and_summary_formats(self):
        path, _, _ = self.build()
        wb = openpyxl.load_workbook(path)
        self.assertEqual(wb.sheetnames, ["요약", "할일기록", "일별요약"])
        ws = wb["요약"]
        rows = {ws.cell(r, 1).value: ws.cell(r, 2) for r in range(2, 13)}
        self.assertEqual(rows["완료"].value, 2)
        for pct in ("완료율", "마감 내 완료율", "당일 처리 비율(완료 중)"):
            self.assertEqual(rows[pct].number_format, "0%", pct)
        self.assertEqual(rows["전체 할 일"].number_format, "General")
        self.assertEqual(ws["A14"].value, "오래 걸린 일 TOP 5")

    def test_records_sheet_dday_and_followup(self):
        path, _, _ = self.build()
        ws = openpyxl.load_workbook(path)["할일기록"]
        by_text = {ws.cell(r, 3).value: [c.value for c in ws[r]] for r in range(2, ws.max_row + 1)}
        self.assertEqual(by_text["늦은 완료"][7], "D+2")
        self.assertEqual(by_text["늦은 완료"][10], "후속")
        self.assertEqual(by_text["후속"][9], "늦은 완료")

    def test_no_orphan_selection_that_makes_excel_ask_to_repair(self):
        path, _, _ = self.build()
        z = zipfile.ZipFile(path)
        for name in z.namelist():
            if name.startswith("xl/worksheets/sheet"):
                xml = z.read(name).decode("utf-8")
                if 'pane="' in xml:
                    self.assertIn("<pane ", xml, name)  # selection 이 pane 을 가리키면 pane 도 있어야 한다


if __name__ == "__main__":
    unittest.main()
