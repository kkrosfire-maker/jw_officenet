import openpyxl
import pytest

import photos
import roster


def _xlsx(tmp_path, rows):
    p = tmp_path / "r.xlsx"
    wb = openpyxl.Workbook()
    for r in rows:
        wb.active.append(r)
    wb.save(p)
    return str(p)


def test_parse_with_header(tmp_path):
    f = _xlsx(tmp_path, [("거래처명", "담당자"), ("A의원", "김"), ("B의원", None), (None, "이")])
    assert roster.parse_excel(f) == [{"거래처명": "A의원", "담당자": "김"}]


def test_parse_blank_rows_before_header(tmp_path):
    f = _xlsx(tmp_path, [(None, None), (None, None), ("거래처명", "담당자"), ("A의원", "김")])
    assert roster.parse_excel(f) == [{"거래처명": "A의원", "담당자": "김"}]


def test_parse_blank_rows_before_data_without_header(tmp_path):
    f = _xlsx(tmp_path, [(None, None), ("A의원", "김")])
    assert roster.parse_excel(f) == [{"거래처명": "A의원", "담당자": "김"}]


def test_parse_only_blank_rows(tmp_path):
    f = _xlsx(tmp_path, [(None, None), (None, None)])
    with pytest.raises(roster.ExcelParseError):
        roster.parse_excel(f)


def test_parse_without_header(tmp_path):
    f = _xlsx(tmp_path, [("A의원", "김")])
    assert roster.parse_excel(f) == [{"거래처명": "A의원", "담당자": "김"}]


def test_parse_no_valid_rows(tmp_path):
    f = _xlsx(tmp_path, [("거래처명", "담당자"), ("A의원", None)])
    with pytest.raises(roster.ExcelParseError):
        roster.parse_excel(f)


def test_list_images_filters_ext_and_dirs(tmp_path):
    for n in ["a.png", "b.JPG", "c.jfif", "d.txt", ".분류되돌리기.json"]:
        (tmp_path / n).write_text("x")
    (tmp_path / "sub.png").mkdir()
    assert sorted(photos.list_images(str(tmp_path))) == ["a.png", "b.JPG", "c.jfif"]
