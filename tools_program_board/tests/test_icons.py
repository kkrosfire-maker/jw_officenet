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


def _make_ico(path, color):
    from PIL import Image
    Image.new("RGBA", (64, 64), color).save(path, sizes=[(64, 64), (32, 32)])


def test_bat_uses_ico_from_folder(tmp_path, monkeypatch):
    from PIL import Image
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(icons, "ICON_DIR", str(out))
    proj = tmp_path / "proj"
    (proj / "assets").mkdir(parents=True)
    _make_ico(proj / "assets" / "app.ico", (255, 0, 0, 255))
    bat = proj / "실행.bat"
    bat.write_text('@echo off\nstart "" pythonw "%~dp0main.py"')
    assert icons.icon_for({"id": "t3", "type": "exe", "path": str(bat)}) == "icons/t3.png"
    img = Image.open(out / "t3.png")
    assert img.size == (256, 256) and img.getpixel((128, 128))[:3] == (255, 0, 0)


def test_ico_named_in_launched_script_wins(tmp_path):
    proj = tmp_path / "proj"
    (proj / "sub").mkdir(parents=True)
    _make_ico(proj / "app.ico", (0, 0, 255, 255))
    _make_ico(proj / "sub" / "board.ico", (0, 255, 0, 255))
    (proj / "main.py").write_text('root.iconbitmap("board.ico")', encoding="utf-8")
    bat = proj / "go.bat"
    bat.write_text('pythonw "%~dp0main.py"')
    assert icons.find_folder_icon(str(bat)).endswith("board.ico")


def test_bat_without_ico_falls_back_to_shell_icon(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(icons, "ICON_DIR", str(out))
    bat = tmp_path / "proj" / "x.bat"
    bat.parent.mkdir()
    bat.write_text("@echo off")
    assert icons.find_folder_icon(str(bat)) == ""
    assert icons.icon_for({"id": "t4", "type": "exe", "path": str(bat)}) == "icons/t4.png"
