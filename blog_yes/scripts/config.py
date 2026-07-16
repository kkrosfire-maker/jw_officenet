"""
파이프라인 공통 설정 — 모든 매직 넘버와 경로의 단일 진실 공급원(SSOT)

경로나 좌표를 바꿔야 할 때 이 파일 한 곳만 수정하면 된다.
"""
import os
import re
import datetime

# ── 기본 경로 ──────────────────────────────────────────────────────
OUTPUT_BASE = r"C:\Users\JW\Desktop\workspace\blog_yes\output"
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

# ══════════════════════════════════════════════════════════════════
# 연세예스내과 신규 프레임 시스템 (Template A/B) — guide/image-guide-yonsei.md 참고
# 2026-07-15 대개편. 위 구간(REF_DIR/FRAME_PNG/THUMB_* 등)은 구 클립보드 시스템 전용이며
# 이 신규 시스템과 무관하다 — 절대 섞어 쓰지 않는다.
# ══════════════════════════════════════════════════════════════════
YONSEI_BASE = r"C:\Users\JW\Desktop\workspace\blog_yes"
YONSEI_FRAMES = ["fraim1.png", "fraim2.png", "fraim3.png"]   # 순환 배정용
YONSEI_TAB_COLOR = {"fraim1.png": "#EF804F", "fraim2.png": "#51A1EF", "fraim3.png": "#FF5FAB"}

# 카드/캔버스 실측 좌표 (픽셀 스캔 결과, fraim1/2/3.png 공통)
YONSEI_CARD_LEFT, YONSEI_CARD_TOP, YONSEI_CARD_RIGHT, YONSEI_CARD_BOTTOM = 140, 335, 2615, 2626
YONSEI_TEXT_LEFT = 321          # 기존 헤더 라벨 x (참고용, 제목은 이제 중앙정렬이라 직접 쓰진 않음)
YONSEI_CONTENT_TOP = 450
YONSEI_CONTENT_BOTTOM = 2370
YONSEI_RIGHT_MARGIN = YONSEI_TEXT_LEFT - YONSEI_CARD_LEFT          # 181
YONSEI_TEXT_RIGHT = YONSEI_CARD_RIGHT - YONSEI_RIGHT_MARGIN         # 2434
YONSEI_FULL_W = YONSEI_TEXT_RIGHT - YONSEI_TEXT_LEFT                # 2113

# 타이포그래피 (2026-07-15 확정값)
YONSEI_TITLE_FONT_STACK = "'Pretendard ExtraBold','Noto Sans KR','Malgun Gothic',sans-serif"
YONSEI_BODY_FONT_STACK = "'Pretendard SemiBold','Noto Sans KR','Malgun Gothic',sans-serif"
YONSEI_TITLE_PX = 190
YONSEI_BODY_PX = 60
YONSEI_TITLE_GAP = 70

# Template A(리스트형) 전용 좌표
YONSEI_LIST_LEFT = 260
YONSEI_ILLUST_W = 1000
YONSEI_GAP_COL = 113
YONSEI_ILLUST_H_MAX = 1480

# 우상단 코너 라벨
YONSEI_LABEL_COLOR = (199, 203, 207, 255)
YONSEI_LABEL_FONT_PX = 44
YONSEI_LABEL_CIRCLE_FONT_PX = 40
YONSEI_LABEL_CIRCLE_D = 66
YONSEI_LABEL_GAP = 22
YONSEI_LABEL_RIGHT_MARGIN = 40
YONSEI_LABEL_CY = 220

YONSEI_FONT_SEMIBOLD = r"C:\Users\JW\AppData\Local\Microsoft\Windows\Fonts\Pretendard-SemiBold.ttf"
YONSEI_FONT_EXTRABOLD = r"C:\Users\JW\AppData\Local\Microsoft\Windows\Fonts\Pretendard-ExtraBold.ttf"

# 썸네일 (thumb nail.png, 1024x1024) — guide/image-guide-yonsei.md §5 참고
YONSEI_THUMB_FILE = "thumb nail.png"
YONSEI_THUMB_CARD_CENTER_X = 525   # 2026-07-16 재재실측: 점선 줄무늬 자체의 좌우 끝(x≈170~879, 9줄 픽셀 스캔) 중앙.
                                    # 카드 흰 배경 전체 폭(44~925) 기준의 485는 점선이 실제 차지하는 폭보다 넓게 잡혀
                                    # 여전히 살짝 치우쳐 보인다는 피드백으로 점선 폭 기준으로 재조정 (과거 545도 폐기)
YONSEI_THUMB_LINE_Y_START = 650
YONSEI_THUMB_LINE_SPACING = 115
YONSEI_THUMB_MAX_WIDTH = 660
YONSEI_THUMB_TEXT_COLOR = (26, 35, 64, 255)   # #1A2340
YONSEI_THUMB_IMAGE_BOX = (116, 110, 886, 600)  # 카드 백지 영역 실측 중심 x≈501 기준 (제목의 545와 다름, 혼동 금지)


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
