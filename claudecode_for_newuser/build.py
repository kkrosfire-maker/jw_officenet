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

설정이나 스킬을 바꾼 뒤에는 build.bat 을 다시 실행하면 된다.
"""

import shutil
import subprocess
import sys
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


if __name__ == "__main__":
    collect_payload()
    build_exe()
    make_release()
