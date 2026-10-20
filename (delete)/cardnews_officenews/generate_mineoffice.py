"""
마인오피스 후기 카드뉴스 (7장)
블로그: https://blog.naver.com/wons0_0/224168110325
"""
from PIL import Image, ImageDraw, ImageFont
import os, textwrap
from card_renderer import font, lerp, th, put, put_wrap
from card_renderer import make_bg as _make_bg

W, H   = 1080, 1080
OUTPUT = r"C:\Users\JW\Desktop\workspace\office_news\output\mineoffice_cards"
os.makedirs(OUTPUT, exist_ok=True)

LOGO_PATH = r"C:\Users\JW\Desktop\정원유니어스\정원로고.png"

# ── 색상 ────────────────────────────────────────────────────
NAVY      = (10, 16, 52)
NAVY_MID  = (16, 30, 82)
CARD_BOX  = (28, 44, 108)
YELLOW    = (245, 228, 50)
TEAL      = (38, 195, 145)
WHITE     = (255, 255, 255)
ORANGE    = (222, 72, 38)
GRAY_TEXT = (185, 200, 225)
IMG_BG    = (45, 55, 90)
IMG_TEXT  = (140, 165, 210)
MARGIN    = 72


def make_bg():
    return _make_bg(W, H, NAVY_MID, NAVY)


def left_bar(draw, y_top, height):
    draw.rectangle([MARGIN, y_top, MARGIN + 6, y_top + height], fill=TEAL)


def pill_badge(img, draw, text, cx, y, fill=YELLOW, text_fill=NAVY):
    f  = font(30, bold=True)
    bb = f.getbbox(text)
    lw = int(draw.textlength(text, font=f))
    lh = bb[3] - bb[1]
    pw, ph = lw + 48, lh + 18
    bx = cx - pw // 2
    draw.rounded_rectangle([bx, y, bx + pw, y + ph], radius=ph // 2, fill=fill)
    draw.text((bx + 24, y + 9 - bb[1]), text, font=f, fill=text_fill)
    return ph


def item_box(draw, icon_char, title, desc, bx, by, bw, bh):
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=20, fill=CARD_BOX)
    fi = font(52, bold=True)
    ix, iy = bx + 24, by + 20
    draw.text((ix, iy - fi.getbbox(icon_char)[1]), icon_char, font=fi, fill=YELLOW)
    ft = font(40, bold=True)
    tx = ix + int(draw.textlength(icon_char, font=fi)) + 14
    bb_t = ft.getbbox(title)
    ty   = iy + (52 - (bb_t[3] - bb_t[1])) // 2
    draw.text((tx, ty - bb_t[1]), title, font=ft, fill=WHITE)
    put_wrap(draw, desc, font(28), bx + 24, by + 94, GRAY_TEXT, bw - 48, gap=5)


def draw_logo(img, draw):
    ICON = 56
    f_brand = font(30, bold=True)
    brand   = "JUNGWON OFFICE NET"
    bw      = int(draw.textlength(brand, font=f_brand))
    total_w = ICON + 14 + bw
    sx      = (W - total_w) // 2
    iy      = H - MARGIN - ICON + 8

    draw.rounded_rectangle([sx, iy, sx + ICON, iy + ICON], radius=10, fill=(22, 90, 55))
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        ratio  = ICON / max(logo.width, logo.height)
        lw2, lh2 = int(logo.width * ratio), int(logo.height * ratio)
        logo_r = logo.resize((lw2, lh2), Image.LANCZOS)
        img.paste(logo_r, (sx + (ICON - lw2) // 2, iy + (ICON - lh2) // 2), mask=logo_r.split()[3])
    except Exception:
        fj = font(22, bold=True)
        bb = fj.getbbox("JW")
        draw.text((sx + (ICON - int(draw.textlength("JW", font=fj))) // 2,
                   iy + (ICON - (bb[3] - bb[1])) // 2 - bb[1]), "JW", font=fj, fill=WHITE)

    tx = sx + ICON + 14
    bb = f_brand.getbbox(brand)
    ty = iy + (ICON - (bb[3] - bb[1])) // 2
    draw.text((tx, ty - bb[1]), brand, font=f_brand, fill=WHITE)


def img_placeholder(draw, x, y, w, h, label):
    """이미지 자리 표시 — 어두운 박스 + 설명 텍스트"""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=IMG_BG)
    # 카메라 아이콘 느낌의 박스
    draw.rounded_rectangle([x + 2, y + 2, x + w - 2, y + h - 2],
                            radius=14, outline=(70, 90, 140), width=2)
    # 📷 텍스트
    fi = font(36)
    icon_text = "📷"
    iw = draw.textlength(icon_text, font=fi)
    draw.text((x + (w - iw) // 2, y + h // 2 - 60 - fi.getbbox(icon_text)[1]),
              icon_text, font=fi, fill=IMG_TEXT)
    # 설명 텍스트 (줄바꿈 포함)
    fl = font(26)
    lines = textwrap.wrap(label, width=int(w / 14))
    total_h = len(lines) * (th(fl) + 6)
    ty = y + h // 2 - total_h // 2 + 10
    for line in lines:
        lw2 = draw.textlength(line, font=fl)
        draw.text((x + (w - lw2) // 2, ty - fl.getbbox(line)[1]),
                  line, font=fl, fill=IMG_TEXT)
        ty += th(fl) + 6


# ═══════════════════════════════════════════════════════════
# 카드 1 — 표지
# ═══════════════════════════════════════════════════════════
def card01():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    ph = pill_badge(img, draw, "김포 비상주사무실 솔직 후기", W // 2, 68)
    y  = 68 + ph + 36

    f_big = font(96, bold=True)
    y = put(draw, "집 주소 노출", f_big, 0, y, WHITE, align="center") + 8
    y = put(draw, "걱정 끝!", f_big, 0, y, YELLOW, align="center") + 12

    f_sub = font(42)
    y = put(draw, "직접 발품 팔아 결정한", f_sub, 0, y, GRAY_TEXT, align="center") + 6
    y = put(draw, "마인공유오피스 방문기", f_sub, 0, y, WHITE, align="center") + 44

    # 이미지 플레이스홀더
    ph_w = W - MARGIN * 2
    ph_h = 320
    img_placeholder(draw, MARGIN, y, ph_w, ph_h,
                    "블로그 이미지 01~02 중 선택\n마인오피스 건물 외관 또는 입구 전경 사진")

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "01_표지.png"), "PNG")
    print("01_표지.png 저장")


# ═══════════════════════════════════════════════════════════
# 카드 2 — 공감 (문제 제기)
# ═══════════════════════════════════════════════════════════
def card02():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    left_bar(draw, 72, 140)
    f_title = font(72, bold=True)
    y = 72
    y = put(draw, "창업할 때 이 고민, 저도", f_title, MARGIN + 22, y, WHITE) + 8
    y = put(draw, "했습니다.", f_title, MARGIN + 22, y, YELLOW) + 44

    bw = W - MARGIN * 2
    bh = 152
    gap = 18
    items = [
        ("🏠", "집 주소 노출 걱정",
         "사업자 등록 시 집 주소를 쓰면 개인정보가 공개됩니다."),
        ("💸", "번듯한 사무실은 부담",
         "월세+보증금+관리비… 창업 초기엔 고정비 부담이 너무 큽니다."),
        ("😰", "어중간한 선택이 무섭다",
         "잘못 고르면 사업자등록 반려·취소까지 될 수 있습니다."),
    ]
    for i, (icon, title, desc) in enumerate(items):
        item_box(draw, icon, title, desc, MARGIN, y + i * (bh + gap), bw, bh)

    y_img = y + len(items) * (bh + gap) + 16
    img_placeholder(draw, MARGIN, y_img, W - MARGIN * 2, H - y_img - MARGIN - 80,
                    "블로그 이미지 01\n고민하는 창업자 / 집·사무실 콘셉트 사진")

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "02_고민공감.png"), "PNG")
    print("02_고민공감.png 저장")


# ═══════════════════════════════════════════════════════════
# 카드 3 — 마인오피스 소개
# ═══════════════════════════════════════════════════════════
def card03():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    left_bar(draw, 72, 130)
    f_title = font(72, bold=True)
    y = 72
    y = put(draw, "첫인상부터 신뢰가 갔습니다",  f_title, MARGIN + 22, y, WHITE) + 8
    y = put(draw, "🏢 하이브리드 오피스", font(48, bold=True), MARGIN + 22, y, YELLOW) + 36

    # 3개 특징 가로 배치
    f_kw = font(34, bold=True)
    f_kw2= font(28)
    col_w = (W - MARGIN * 2 - 32) // 3
    keywords = [
        ("공유오피스",   "개방적 환경"),
        ("소호사무실",   "독립된 공간"),
        ("비상주사무실", "경제적 비용"),
    ]
    for i, (kw, sub) in enumerate(keywords):
        bx = MARGIN + i * (col_w + 16)
        draw.rounded_rectangle([bx, y, bx + col_w, y + 110], radius=16, fill=CARD_BOX)
        draw.text((bx + (col_w - draw.textlength(kw, font=f_kw)) // 2,
                   y + 12 - f_kw.getbbox(kw)[1]), kw, font=f_kw, fill=TEAL)
        draw.text((bx + (col_w - draw.textlength(sub, font=f_kw2)) // 2,
                   y + 60 - f_kw2.getbbox(sub)[1]), sub, font=f_kw2, fill=GRAY_TEXT)
    y += 110 + 30

    # 강조 문구 박스
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + 90], radius=16, fill=CARD_BOX)
    draw.rectangle([MARGIN, y, MARGIN + 6, y + 90], fill=YELLOW)
    f_em = font(38, bold=True)
    txt = "보증금 0원 · 관리비 0원 · 최저가 임대료 지향"
    tw = draw.textlength(txt, font=f_em)
    draw.text(((W - tw) // 2, y + 28 - f_em.getbbox(txt)[1]), txt, font=f_em, fill=YELLOW)
    y += 90 + 24

    # 이미지 플레이스홀더
    img_placeholder(draw, MARGIN, y, W - MARGIN * 2, H - y - MARGIN - 80,
                    "블로그 이미지 03\n건물 입구 파란 배너 / 외부 전경 사진")

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "03_오피스소개.png"), "PNG")
    print("03_오피스소개.png 저장")


# ═══════════════════════════════════════════════════════════
# 카드 4 — 계약 전 체크리스트 3가지
# ═══════════════════════════════════════════════════════════
def card04():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    left_bar(draw, 72, 130)
    f_title = font(68, bold=True)
    y = 72
    y = put(draw, "계약 전, 이것만은 꼭",    f_title, MARGIN + 22, y, WHITE) + 8
    y = put(draw, "확인하세요!", f_title, MARGIN + 22, y, YELLOW) + 36

    bw = W - MARGIN * 2
    bh = 158
    gap = 16
    items = [
        ("①", "실제 사무 공간이 있나?",
         "관공서 실사 대응 가능한 실제 공간 여부 확인. 마인오피스는 전 지점 실사 지원 서비스 제공."),
        ("②", "100% 직영인가?",
         "중개·대행 업체는 책임 소재 불분명. 계약서 임대인 정보 = 판매자 정보인지 꼭 확인."),
        ("③", "우편·택배 관리는?",
         "우편 도착 즉시 스캔 알림 + 필요 시 재발송 서비스 여부 확인 필수."),
    ]
    for i, (icon, title, desc) in enumerate(items):
        item_box(draw, icon, title, desc, MARGIN, y + i * (bh + gap), bw, bh)

    y_img = y + len(items) * (bh + gap) + 16
    if y_img + 80 < H - MARGIN - 80:
        img_placeholder(draw, MARGIN, y_img, W - MARGIN * 2, H - y_img - MARGIN - 80,
                        "블로그 이미지 04~05\n사무실 내부 / 입구 유리문 안내문 사진")

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "04_체크리스트.png"), "PNG")
    print("04_체크리스트.png 저장")


# ═══════════════════════════════════════════════════════════
# 카드 5 — 내부 시설
# ═══════════════════════════════════════════════════════════
def card05():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    left_bar(draw, 72, 130)
    f_title = font(72, bold=True)
    y = 72
    y = put(draw, "디테일이 살아있는",    f_title, MARGIN + 22, y, WHITE) + 8
    y = put(draw, "내부 시설 🏠", f_title, MARGIN + 22, y, YELLOW) + 36

    # 이미지 플레이스홀더 (좌우 2개)
    ph_w = (W - MARGIN * 2 - 20) // 2
    ph_h = 280
    img_placeholder(draw, MARGIN, y, ph_w, ph_h,
                    "블로그 이미지 07\n택배 업무 공간 / 공용 오픈룸 사진")
    img_placeholder(draw, MARGIN + ph_w + 20, y, ph_w, ph_h,
                    "블로그 이미지 08\n개인 칸막이 좌석 / 업무 공간 내부 사진")
    y += ph_h + 30

    # 시설 목록
    bw = W - MARGIN * 2
    bh = 138
    gap = 16
    items = [
        ("📦", "택배 전용 공간",     "온라인 쇼핑몰 운영자를 위한 별도 택배 업무 공간 마련"),
        ("🖨️", "무료 공용 편의시설",  "프린터 · 컴퓨터 · 냉장고 무료 이용 가능"),
        ("🪟", "집중 업무 환경",     "개인 칸막이 좌석으로 실사 대응 시에도 쾌적한 환경 제공"),
    ]
    for i, (icon, title, desc) in enumerate(items):
        item_box(draw, icon, title, desc, MARGIN, y + i * (bh + gap), bw, bh)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "05_내부시설.png"), "PNG")
    print("05_내부시설.png 저장")


# ═══════════════════════════════════════════════════════════
# 카드 6 — 원스탑 서비스
# ═══════════════════════════════════════════════════════════
def card06():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    left_bar(draw, 72, 130)
    f_title = font(72, bold=True)
    y = 72
    y = put(draw, "법무·세무까지?",       f_title, MARGIN + 22, y, WHITE) + 8
    y = put(draw, "원스탑 서비스!", f_title, MARGIN + 22, y, YELLOW) + 32

    # 큰 강조 문구
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + 100], radius=18, fill=CARD_BOX)
    draw.rectangle([MARGIN, y, MARGIN + 6, y + 100], fill=TEAL)
    f_em = font(36, bold=True)
    line1 = "법인 설립 + 사업자 등록 대행 수수료"
    line2 = "원스탑 이용 시 → 무료 🎉"
    lw1 = draw.textlength(line1, font=f_em)
    lw2 = draw.textlength(line2, font=f_em)
    draw.text(((W - lw1) // 2, y + 14 - f_em.getbbox(line1)[1]), line1, font=f_em, fill=WHITE)
    draw.text(((W - lw2) // 2, y + 58 - f_em.getbbox(line2)[1]), line2, font=f_em, fill=TEAL)
    y += 100 + 28

    bw = W - MARGIN * 2
    bh = 148
    gap = 16
    items = [
        ("⚖️", "법무팀 상주",    "법인 설립부터 사업자 등록까지 전문 법무팀이 원내에서 직접 처리"),
        ("📊", "세무팀 상주",    "세무 신고·관리까지 한 번에 해결 — 초기 창업 비용 절감"),
        ("🤝", "1:1 전담 매니저", "상담부터 계약·사후 관리까지 전담 매니저가 끝까지 책임"),
    ]
    for i, (icon, title, desc) in enumerate(items):
        item_box(draw, icon, title, desc, MARGIN, y + i * (bh + gap), bw, bh)

    y_img = y + len(items) * (bh + gap) + 16
    if y_img + 80 < H - MARGIN - 80:
        img_placeholder(draw, MARGIN, y_img, W - MARGIN * 2, H - y_img - MARGIN - 80,
                        "블로그 이미지 09\n상담 장면 / 원스탑 서비스 안내 사진")

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "06_원스탑.png"), "PNG")
    print("06_원스탑.png 저장")


# ═══════════════════════════════════════════════════════════
# 카드 7 — 위치·CTA
# ═══════════════════════════════════════════════════════════
def card07():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    # 이미지 플레이스홀더 (상단)
    ph_h = 260
    img_placeholder(draw, MARGIN, 72, W - MARGIN * 2, ph_h,
                    "블로그 이미지 06\n건물 주변 상권 / 지도·위치 안내 사진")
    y = 72 + ph_h + 32

    left_bar(draw, y, 110)
    f_title = font(68, bold=True)
    y = put(draw, "📍 오시는 길", f_title, MARGIN + 22, y, WHITE) + 36

    # 위치 정보 박스
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + 220], radius=18, fill=CARD_BOX)
    draw.rectangle([MARGIN, y, MARGIN + 6, y + 220], fill=TEAL)
    f_loc = font(34, bold=True)
    f_loc2= font(30)
    info = [
        ("🏢 주소",   "경기도 김포시 유현로 52 프라임빌복합상가 310호"),
        ("🚗 교통",   "풍무역 차량 4분 · 대형 지하주차장 300대+"),
        ("☕ 주변",   "카페 · 식당 · 병원 · 찜질방 · 골프장 모두 인접"),
    ]
    iy = y + 16
    for label, val in info:
        draw.text((MARGIN + 20, iy - f_loc.getbbox(label)[1]),
                  label, font=f_loc, fill=YELLOW)
        lw = draw.textlength(label + "  ", font=f_loc)
        draw.text((MARGIN + 20 + int(lw), iy - f_loc2.getbbox(val)[1]),
                  val, font=f_loc2, fill=WHITE)
        iy += th(f_loc) + 20
    y += 220 + 30

    # CTA 박스
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + 160], radius=18, fill=(20, 130, 90))
    f_cta = font(40, bold=True)
    f_cta2= font(32)
    cta1 = "예비 창업자·프리랜서분들께 강력 추천!"
    cta2 = "지금 마인오피스에 문의해보세요 😊"
    lw1 = draw.textlength(cta1, font=f_cta)
    lw2 = draw.textlength(cta2, font=f_cta2)
    draw.text(((W - lw1) // 2, y + 28 - f_cta.getbbox(cta1)[1]),  cta1, font=f_cta,  fill=WHITE)
    draw.text(((W - lw2) // 2, y + 94 - f_cta2.getbbox(cta2)[1]), cta2, font=f_cta2, fill=YELLOW)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "07_위치CTA.png"), "PNG")
    print("07_위치CTA.png 저장")


# ── 실행 ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("마인오피스 카드뉴스 생성 중...")
    card01(); card02(); card03(); card04()
    card05(); card06(); card07()
    print(f"\n완료! {OUTPUT}")
