import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import icons

NOTEPAD = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "notepad.exe")


def test_suggest_falls_back_to_file_name(tmp_path):
    bat = tmp_path / "할일_실행.bat"
    bat.write_text("@echo off")
    assert icons.suggest(str(bat)) == ("할일_실행", "")


def test_suggest_reads_exe_version_info():
    name, desc = icons.suggest(NOTEPAD)
    assert name and "operating system" not in desc.lower()


def test_exe_icon_is_square_256_png(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setattr(icons, "ICON_DIR", str(tmp_path))
    rel = icons.icon_for({"id": "t1", "type": "exe", "path": NOTEPAD})
    assert rel == "icons/t1.png"
    assert Image.open(tmp_path / "t1.png").size == (256, 256)


def test_missing_exe_gives_no_icon(tmp_path, monkeypatch):
    monkeypatch.setattr(icons, "ICON_DIR", str(tmp_path))
    assert icons.icon_for({"id": "t2", "type": "exe", "path": r"C:\nope\x.exe"}) == ""
