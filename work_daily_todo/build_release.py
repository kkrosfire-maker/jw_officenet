"""배포 파일 만들기: python build_release.py
dist/ 에 두 가지를 만든다.
  - 오늘의할일_업데이트_(yymmdd).exe : 이미 쓰는 사람용. 실행하면 프로그램 파일만 바꾸고 data(할 일 기록)는 그대로 둔다.
  - 오늘의할일_(yymmdd).zip          : 처음 설치하는 사람용.
"""
import os
import shutil
import subprocess
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dist")
WORK = os.path.join(os.environ.get("TEMP", HERE), "build_todo_release")
TAG = f"{date.today():%y%m%d}"
README = """오늘의 할 일

1. 이 폴더를 원하는 곳에 풀어 놓고 '오늘의할일.exe' 를 실행하세요.
2. 할 일은 같은 폴더의 data 폴더에 자동 저장됩니다. 폴더를 옮길 때 data 도 함께 옮기세요.
3. 새 버전이 나오면 압축파일 말고 '오늘의할일_업데이트_(날짜).exe' 를 받아 실행하세요.
   프로그램 파일만 바뀌고 data 폴더(할 일 기록)는 그대로 남습니다.
4. 화면이 비어 보이면 'Microsoft Edge WebView2 런타임'이 필요한 PC입니다.
   (윈도우 10/11 대부분 이미 설치되어 있습니다.)
"""


def pyinstaller(*args):
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
                    "--workpath", os.path.join(WORK, "work"), "--specpath", WORK, *args], check=True)


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    app_dist = os.path.join(WORK, "app")

    # 1) 프로그램 본체 (폴더형 exe)
    pyinstaller("--windowed", "--name", "오늘의할일", "--icon", os.path.join(HERE, "app.ico"),
                "--add-data", f"{os.path.join(HERE, 'index.html')};.",
                "--add-data", f"{os.path.join(HERE, 'app.ico')};.",
                "--add-data", f"{os.path.join(HERE, 'assets', 'icon.png')};assets",
                "--distpath", app_dist, os.path.join(HERE, "app.py"))
    payload = os.path.join(app_dist, "오늘의할일")
    with open(os.path.join(payload, "사용법.txt"), "w", encoding="utf-8-sig") as f:
        f.write(README)
    with open(os.path.join(payload, "version.txt"), "w", encoding="utf-8") as f:
        f.write(TAG)
    assert not os.path.exists(os.path.join(payload, "data")), "배포본에 data 가 들어가면 안 된다"

    # 2) 처음 설치용 zip
    zip_base = os.path.join(OUT, f"오늘의할일_({TAG})")
    shutil.make_archive(zip_base, "zip", app_dist, "오늘의할일")

    # 3) 업데이트용 exe (본체를 payload 로 품은 한 개짜리 exe)
    pyinstaller("--onefile", "--windowed", "--name", f"오늘의할일_업데이트_({TAG})", "--icon", os.path.join(HERE, "app.ico"),
                "--add-data", f"{payload};payload", "--distpath", OUT, os.path.join(HERE, "updater.py"))

    print("완료:")
    print(" ", zip_base + ".zip")
    print(" ", os.path.join(OUT, f"오늘의할일_업데이트_({TAG}).exe"))


if __name__ == "__main__":
    main()
