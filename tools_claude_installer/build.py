"""
build.py — 이 PC의 현재 Claude Code 설정으로 설치 exe 를 만든다.

  1. payload/ 에 넣을 것 모으기
       ~/.claude/settings.json            → payload/settings.json
       workspace/CLAUDE.md                → payload/CLAUDE.md
       workspace/.claude/settings.local.json → payload/settings.local.json
       workspace/.claude/skills/*         → payload/skills/ (링크는 실제 내용으로 풀어서)
       profile_template.ps1               → payload/profile_template.ps1
  2. PyInstaller 로 installer.py + payload → 단일 exe
  3. 배포/ 폴더에 ClaudeCode_설치.exe + 설치방법.txt 정리
  4. 맥용: mac/install.command + payload(스킬·설정·zsh 프로필) → 배포/ClaudeCode_설치_Mac.zip
     (맥 CLAUDE.md 는 Windows/PowerShell 환경 섹션을 맥/zsh 로 바꿔서 만든다)

설정이나 스킬을 바꾼 뒤에는 build.bat 을 다시 실행하면 된다.
"""

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
HOME = Path.home()
PAYLOAD = HERE / "payload"
BUILD = HERE / "build"
DIST = HERE / "dist"
RELEASE = HERE / "배포"
EXE_NAME = "ClaudeCode_설치.exe"


def collect_payload():
    if PAYLOAD.exists():
        shutil.rmtree(PAYLOAD)
    PAYLOAD.mkdir()

    for src, name in [
        (HOME / ".claude" / "settings.json", "settings.json"),
        (WORKSPACE / "CLAUDE.md", "CLAUDE.md"),
        (WORKSPACE / ".claude" / "settings.local.json", "settings.local.json"),
        (HERE / "profile_template.ps1", "profile_template.ps1"),
    ]:
        if src.exists():
            shutil.copy2(src, PAYLOAD / name)
            print(f"[OK] {name}")
        else:
            print(f"[SKIP] 없음: {src}")

    skills_src = WORKSPACE / ".claude" / "skills"
    skills_dest = PAYLOAD / "skills"
    skills_dest.mkdir()
    for entry in sorted(skills_src.iterdir()):
        real = entry.resolve()  # 심볼릭 링크/정션이면 .agents/skills 의 실제 폴더
        if not (real / "SKILL.md").exists():
            print(f"[SKIP] 스킬 아님: {entry.name}")
            continue
        shutil.copytree(real, skills_dest / entry.name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"[OK] 스킬 {len(list(skills_dest.iterdir()))}개")


def build_exe():
    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--console", "--noconfirm", "--clean",
        "--name", "ClaudeCode_Setup",
        "--add-data", f"{PAYLOAD};payload",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
        str(HERE / "installer.py"),
    ], check=True)


def make_release():
    RELEASE.mkdir(exist_ok=True)
    shutil.copy2(DIST / "ClaudeCode_Setup.exe", RELEASE / EXE_NAME)
    shutil.copy2(HERE / "설치방법.txt", RELEASE / "설치방법.txt")
    print(f"\n완료: {RELEASE}")
    for f in sorted(RELEASE.iterdir()):
        print(f"  {f.name}  ({f.stat().st_size / 1024 / 1024:.1f} MB)")


MAC_ZIP_NAME = "ClaudeCode_설치_Mac.zip"
MAC_ENV_SECTION = """## Environment

- Platform: macOS, zsh
- Shell: Use zsh/bash syntax (`export VAR=...`, `&&` for chaining)

## Claude Code Settings

Permissions can be allowed in `.claude/settings.local.json` (created per project).
"""


def mac_claude_md(text: str) -> str:
    # Windows/PowerShell 전용 '## Environment' ~ '## Running things locally' 사이를 맥용으로 교체
    return re.sub(r"## Environment.*?(?=## Running things locally)", MAC_ENV_SECTION + "\n",
                  text, count=1, flags=re.S)


def make_mac_zip():
    RELEASE.mkdir(exist_ok=True)
    zpath = RELEASE / MAC_ZIP_NAME
    mac = HERE / "mac"

    def add_bytes(z, arcname, data: bytes, executable=False):
        info = zipfile.ZipInfo(arcname, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3  # Unix 로 표시해야 맥이 실행 권한(external_attr)을 읽는다
        info.external_attr = (0o755 if executable else 0o644) << 16  # 맥에서 실행 권한 유지
        z.writestr(info, data)

    def lf(path: Path) -> bytes:  # 맥 쉘은 CR 을 못 먹으므로 줄바꿈을 LF 로 통일, BOM 제거
        return ("\n".join(path.read_text(encoding="utf-8-sig").splitlines()) + "\n").encode("utf-8")

    with zipfile.ZipFile(zpath, "w") as z:
        add_bytes(z, "install.command", lf(mac / "install.command"), executable=True)
        add_bytes(z, "payload/profile_template.zsh", lf(mac / "profile_template.zsh"))
        add_bytes(z, "설치방법_Mac.txt", lf(HERE / "설치방법_Mac.txt"))
        if (PAYLOAD / "settings.json").exists():
            add_bytes(z, "payload/settings.json", lf(PAYLOAD / "settings.json"))
        if (PAYLOAD / "CLAUDE.md").exists():
            add_bytes(z, "payload/CLAUDE.md",
                      mac_claude_md(lf(PAYLOAD / "CLAUDE.md").decode("utf-8")).encode("utf-8"))
        for file in sorted((PAYLOAD / "skills").rglob("*")):
            if file.is_file():
                arc = "payload/skills/" + file.relative_to(PAYLOAD / "skills").as_posix()
                data = file.read_bytes()
                if file.suffix in (".md", ".sh", ".json", ".txt", ".ts", ".tsx", ".js", ".mjs", ".py"):
                    data = data.replace(b"\r\n", b"\n")
                add_bytes(z, arc, data, executable=file.suffix == ".sh")
    shutil.copy2(HERE / "설치방법_Mac.txt", RELEASE / "설치방법_Mac.txt")
    print(f"[OK] 맥용: {zpath.name}  ({zpath.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    collect_payload()
    build_exe()
    make_release()
    make_mac_zip()
