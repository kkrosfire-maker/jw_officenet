"""
파이프라인 공통 설정 — 모든 매직 넘버와 경로의 단일 진실 공급원(SSOT)

경로나 좌표를 바꿔야 할 때 이 파일 한 곳만 수정하면 된다.
"""
import os
import re
import datetime

# ── 기본 경로 ──────────────────────────────────────────────────────
OUTPUT_BASE = r"C:\Users\JW\Desktop\workspace\blog\output"
REF_DIR     = r"C:\Users\JW\Downloads\제목을 입력해주세요"
FRAME_PNG   = r"C:\Users\JW\Downloads\클로드코드 교육용.png"

# ── 이미지 캔버스 크기 ─────────────────────────────────────────────
VIEWPORT_W = 1080
VIEWPORT_H = 1080

# ── 프레임 합성 좌표 (클로드코드 교육용.png 흰 영역, 픽셀 스캔 확인값) ──
FRAME_LEFT = 85
FRAME_TOP  = 88
FRAME_W    = 907   # 992 - 85
FRAME_H    = 903   # 991 - 88

# ── 썸네일 제목 영역 ──────────────────────────────────────────────
# 배경: 1_clean.png (제목 텍스트 없는 클린 클립보드) 위에 텍스트만 그린다.
THUMB_REF_IMAGE      = os.path.join(REF_DIR, "1_clean.png")
TEXT_COLOR           = (95, 107, 141, 255)   # 제목 텍스트 색상 (RGBA)
RIGHT_EDGE           = 955                   # 우측 정렬 기준 x
THUMB_MAX_TEXT_WIDTH = 710                   # 최대 텍스트 너비 (px)
LINE_Y_START         = 390                   # 첫 줄 시작 y
LINE_SPACING         = 105                   # 줄 간격 (px)

# ── 폰트 우선순위 (앞에서부터 존재 여부 확인) ──────────────────────
FONT_PATHS = [
    r"C:\Windows\Fonts\Hancom Gothic Bold.ttf",
    r"C:\Windows\Fonts\HanSantteutDotum-Bold.ttf",
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\gulim.ttc",
]


def topic_dir(topic: str) -> str:
    """주제 폴더 절대 경로를 반환한다.

    1. 이미 yymmdd_ 접두어가 있으면 그대로 사용.
    2. 없으면 OUTPUT_BASE 안에서 *_<topic> 패턴 폴더를 탐색.
       - 1개 존재 → 그 폴더 반환 (날짜 몰라도 기존 작업 이어서 가능)
       - 2개 이상 → 가장 최근(이름 기준 내림차순) 폴더 반환
       - 없으면 → 오늘 날짜로 새 경로 반환
    """
    if re.match(r"^\d{6}_", topic):
        return os.path.join(OUTPUT_BASE, topic)

    suffix = f"_{topic}"
    try:
        candidates = [
            d for d in os.listdir(OUTPUT_BASE)
            if d.endswith(suffix) and re.match(r"^\d{6}_", d)
            and os.path.isdir(os.path.join(OUTPUT_BASE, d))
        ]
    except FileNotFoundError:
        candidates = []

    if candidates:
        return os.path.join(OUTPUT_BASE, sorted(candidates)[-1])

    date = datetime.date.today().strftime("%y%m%d")
    return os.path.join(OUTPUT_BASE, f"{date}_{topic}")
