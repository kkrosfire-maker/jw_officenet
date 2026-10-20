"""데이터 폴더 경로 (로그인 프로필, 다운로드, 학습 규칙).

소스로 실행하면 이 파일이 있는 폴더, exe로 실행하면 exe에서 위로 올라가며 찾은
프로젝트 폴더(kakao_biz.py가 있는 곳)를 쓴다. 못 찾으면 exe 옆 폴더.
"""
import os
import sys


def _data_dir() -> str:
    if not getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(__file__))
    d = os.path.dirname(sys.executable)
    cur = d
    for _ in range(4):
        if os.path.exists(os.path.join(cur, "kakao_biz.py")):
            return cur
        cur = os.path.dirname(cur)
    return d


DATA_DIR = _data_dir()
