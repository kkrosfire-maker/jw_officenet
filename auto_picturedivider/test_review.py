from pathlib import Path

from PIL import Image

import pharma_zip
import photo_sort
from review import CONVERT_FAILED, FUZZY, PHARMA_UNKNOWN, UNMATCHED, format_review


def _summary(events):
    return next(e for e in events if e.kind == "summary")


def test_sort_review_lists_fuzzy_and_unmatched(tmp_path):
    for n in ["가나다의원 9월 안국약품.png", "가나다의 9월 안국약품.png", "없는곳 9월 안국약품.png"]:
        (tmp_path / n).write_text("x")
    lookup = {"가나다의원": "김"}
    files = [p.name for p in tmp_path.iterdir()]
    events = photo_sort.execute_moves(str(tmp_path), photo_sort.classify(files, lookup))
    kinds = {(i.kind, i.filename) for i in _summary(events).review}
    assert kinds == {(FUZZY, "가나다의 9월 안국약품.png"), (UNMATCHED, "없는곳 9월 안국약품.png")}


def test_sort_review_empty_when_all_exact(tmp_path):
    (tmp_path / "가나다의원 9월 안국약품.png").write_text("x")
    events = photo_sort.execute_moves(
        str(tmp_path), photo_sort.classify(["가나다의원 9월 안국약품.png"], {"가나다의원": "김"}))
    assert _summary(events).review == []
    assert format_review(_summary(events).review) == []


def test_pharma_review_lists_unknown_and_failed(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    Image.new("RGB", (4, 4)).save(src / "가나다의원 9월 안국약품.png")
    Image.new("RGB", (4, 4)).save(src / "미더스 (1).png")           # 제약사 없음 → 기타
    (src / "가나다의원 9월 깨진파일.png").write_text("not an image")  # 변환 실패
    events = pharma_zip.build_pharma_folders(
        str(src), [p.name for p in src.iterdir()], tmp_path / "out")
    got = {(i.kind, i.filename) for i in _summary(events).review}
    assert got == {(CONVERT_FAILED, "가나다의원 9월 깨진파일.png"), (PHARMA_UNKNOWN, "미더스 (1).png")}


def test_format_review_groups_by_kind():
    from review import ReviewItem
    lines = format_review([ReviewItem(UNMATCHED, "a.png", "x"), ReviewItem(UNMATCHED, "b.png"),
                           ReviewItem(FUZZY, "c.png", "y")])
    assert [t for t, _ in lines if t.startswith("\n")] == ["\n[확인 필요] 미매칭 2개", "\n[확인 필요] 유사 매칭 1개"]
    assert dict((t, tag) for t, tag in lines)["  ✗  c.png  (y)"] == "fuzzy"
