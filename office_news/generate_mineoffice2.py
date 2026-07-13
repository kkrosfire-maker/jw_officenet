"""
마인오피스 카드뉴스 v2 — 경고/위험 콘셉트 (5장)
표지 + 1컷~4컷
"""
from PIL import Image, ImageDraw, ImageFont
import os, textwrap
from card_renderer import font, lerp, th

W, H   = 1080, 1080
OUTPUT = r"C:\Users\JW\Desktop\workspace\office_news\output\mineoffice_v2"
os.makedirs(OUTPUT, exist_ok=True)

LOGO_PATH = r"C:\Users\JW\Desktop\정원유니어스\정원로고.png"

# ── 색상 팔레트 ──────────────────────────────────────────────
DARK_BG   = (12, 12, 18)
DARK_MID  = (20, 14, 28)
DARK2     = (18, 20, 36)
RED       = (220, 38, 38)
RED_DARK  = (150, 18, 18)
RED_GLOW  = (255, 60, 60)
YELLOW    = (245, 210, 40)
ORANGE    = (230, 100, 20)
TEAL      = (38, 195, 145)
WHITE     = (255, 255, 255)
GRAY      = (160, 165, 180)
GRAY_DIM  = (90, 95, 110)
CARD_BOX  = (28, 22, 48)
MARGIN    = 72


def put(draw, text, f, x, y, fill, align="left"):
    bb = f.getbbox(text)
    lw = draw.textlength(text, font=f)
    ox = x
    if align == "center":
        ox = (W - lw) / 2
    elif align == "right":
        ox = W - MARGIN - lw
    draw.text((ox, y - bb[1]), text, font=f, fill=fill)
    return y + (bb[3] - bb[1])


def put_wrap(draw, text, f, x, y, fill, max_w, gap=8, align="left"):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=f) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    for line in lines:
        y = put(draw, line, f, x, y, fill, align=align) + gap
    return y


# ── 배경: 위→아래 어두운 그라디언트 ──────────────────────────
def make_bg(top=None, bot=None):
    top = top or DARK_MID
    bot = bot or DARK_BG
    strip = Image.new("RGB", (1, H))
    px = strip.load()
    for y in range(H):
        px[0, y] = lerp(top, bot, y / H)
    return strip.resize((W, H))


# ── 빨간 사선 경고 스트라이프 (배경 위에 반투명 효과) ────────
def draw_warning_stripes(img, alpha=30):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    stripe_w = 60
    gap = 60
    for x in range(-H, W + H, stripe_w + gap):
        d.polygon(
            [(x, 0), (x + stripe_w, 0),
             (x + stripe_w + H, H), (x + H, H)],
            fill=(180, 0, 0, alpha)
        )
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))


# ── 좌측 세로 강조 바 ─────────────────────────────────────────
def left_bar(draw, y_top, height, color=RED):
    draw.rectangle([MARGIN, y_top, MARGIN + 7, y_top + height], fill=color)


# ── 상단 위험 배지 ────────────────────────────────────────────
def danger_badge(draw, text, x, y, fill=RED, text_fill=WHITE):
    f  = font(28, bold=True)
    bb = f.getbbox(text)
    lw = int(draw.textlength(text, font=f))
    lh = bb[3] - bb[1]
    pw, ph = lw + 40, lh + 16
    draw.rounded_rectangle([x, y, x + pw, y + ph], radius=6, fill=fill)
    draw.text((x + 20, y + 8 - bb[1]), text, font=f, fill=text_fill)
    return pw, ph


# ── 이미지 플레이스홀더 ───────────────────────────────────────
def img_ph(draw, x, y, w, h, label, border_color=GRAY_DIM):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=14, fill=(28, 25, 42))
    draw.rounded_rectangle([x + 2, y + 2, x + w - 2, y + h - 2],
                            radius=12, outline=border_color, width=2)
    fi = font(34)
    iw = draw.textlength("📷", font=fi)
    draw.text((x + (w - iw) // 2, y + h // 2 - 54 - fi.getbbox("📷")[1]),
              "📷", font=fi, fill=GRAY_DIM)
    fl = font(25)
    lines = textwrap.wrap(label, width=int(w / 13))
    total_h = len(lines) * (th(fl) + 5)
    ty = y + h // 2 - total_h // 2 + 14
    for line in lines:
        lw2 = draw.textlength(line, font=fl)
        draw.text((x + (w - lw2) // 2, ty - fl.getbbox(line)[1]),
                  line, font=fl, fill=GRAY_DIM)
        ty += th(fl) + 5


# ── 체크 아이템 박스 ─────────────────────────────────────────
def check_item(draw, num_text, title, desc, bx, by, bw, bh,
               num_fill=RED, title_fill=WHITE):
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=18, fill=CARD_BOX)
    # 번호 원
    cx, cy, r = bx + 44, by + bh // 2, 30
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=num_fill)
    fn = font(28, bold=True)
    nw = draw.textlength(num_text, font=fn)
    nb = fn.getbbox(num_text)
    draw.text((cx - nw // 2, cy - (nb[3] - nb[1]) // 2 - nb[1]),
              num_text, font=fn, fill=WHITE)
    # 제목
    ft = font(38, bold=True)
    tx = bx + 92
    bb_t = ft.getbbox(title)
    draw.text((tx, by + 16 - bb_t[1]), title, font=ft, fill=title_fill)
    # 설명
    put_wrap(draw, desc, font(27), tx, by + 64, GRAY, bw - 110, gap=4)


# ── JW 로고 ──────────────────────────────────────────────────
def draw_logo(img, draw):
    ICON = 52
    f_brand = font(28, bold=True)
    brand   = "JUNGWON OFFICE NET"
    bw      = int(draw.textlength(brand, font=f_brand))
    total_w = ICON + 12 + bw
    sx      = (W - total_w) // 2
    iy      = H - MARGIN - ICON + 8
    draw.rounded_rectangle([sx, iy, sx + ICON, iy + ICON], radius=10, fill=(22, 90, 55))
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        ratio  = ICON / max(logo.width, logo.height)
        lw2, lh2 = int(logo.width * ratio), int(logo.height * ratio)
        logo_r = logo.resize((lw2, lh2), Image.LANCZOS)
        img.paste(logo_r, (sx + (ICON - lw2) // 2, iy + (ICON - lh2) // 2),
                  mask=logo_r.split()[3])
    except Exception:
        fj = font(20, bold=True)
        bb = fj.getbbox("JW")
        draw.text((sx + (ICON - int(draw.textlength("JW", font=fj))) // 2,
                   iy + (ICON - (bb[3] - bb[1])) // 2 - bb[1]),
                  "JW", font=fj, fill=WHITE)
    tx = sx + ICON + 12
    bb = f_brand.getbbox(brand)
    ty = iy + (ICON - (bb[3] - bb[1])) // 2
    draw.text((tx, ty - bb[1]), brand, font=f_brand, fill=GRAY)


# ═══════════════════════════════════════════════════════════
# 표지 — "당신의 집 주소는 안전합니까?"
# ═══════════════════════════════════════════════════════════
def card00():
    img  = make_bg(top=(25, 8, 8), bot=DARK_BG)
    draw_warning_stripes(img, alpha=18)
    draw = ImageDraw.Draw(img)

    # 상단 배지
    bw, bh = danger_badge(draw, "⚠️  경고", MARGIN, 72, fill=RED)
    danger_badge(draw, "당신의 사업자등록증", MARGIN + bw + 16, 72,
                 fill=(50, 20, 20), text_fill=GRAY)

    # 이미지 플레이스홀더 (중간 영역)
    ph_y = 72 + bh + 28
    ph_h = 320
    img_ph(draw, MARGIN, ph_y, W - MARGIN * 2, ph_h,
           "아파트/빌라 건물 외관 사진 위에\n붉은 반투명 오버레이 + '공개 중' 레이블 합성",
           border_color=RED_DARK)
    # 플레이스홀더 위에 '공개 중' 레이블 오버레이
    label_f = font(32, bold=True)
    lw = int(draw.textlength("🔴  공개 중", font=label_f))
    draw.rounded_rectangle([W // 2 - lw // 2 - 16, ph_y + ph_h - 58,
                             W // 2 + lw // 2 + 16, ph_y + ph_h - 10],
                            radius=8, fill=RED)
    draw.text((W // 2 - lw // 2, ph_y + ph_h - 52 - label_f.getbbox("공")[1]),
              "🔴  공개 중", font=label_f, fill=WHITE)

    y = ph_y + ph_h + 40

    # 메인 타이틀
    f_big = font(88, bold=True)
    y = put(draw, "당신의 집 주소는", f_big, 0, y, WHITE, align="center") + 10
    y = put(draw, "안전합니까?", f_big, 0, y, RED_GLOW, align="center") + 24

    # 소제목
    f_sub = font(36)
    y = put_wrap(draw, "사업자등록증 속 '집 주소'가 시한폭탄인 이유",
                 f_sub, 0, y, YELLOW, W, gap=0, align="center")

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "00_표지.png"), "PNG")
    print("00_표지.png 저장")


# ═══════════════════════════════════════════════════════════
# 1컷 — "누가 우리 집 초인종을 눌렀다"
# ═══════════════════════════════════════════════════════════
def card01():
    img  = make_bg(top=(18, 8, 8), bot=DARK_BG)
    draw = ImageDraw.Draw(img)

    # 카드 번호
    danger_badge(draw, "1컷", MARGIN, 66, fill=(60, 20, 20), text_fill=RED_GLOW)
    danger_badge(draw, "사생활 증발", MARGIN + 90, 66, fill=RED)

    y = 66 + 44 + 20

    # 핵심 문구
    left_bar(draw, y, 8, color=RED)
    f_main = font(68, bold=True)
    y = put(draw, '"누가 우리 집', f_main, MARGIN + 20, y, WHITE) + 8
    y = put(draw, ' 초인종을 눌렀다”', f_main, MARGIN + 20, y, RED_GLOW) + 28

    # 스마트폰 플레이스홀더
    ph_x = W - MARGIN - 310
    ph_y = y - th(f_main) * 2 - 28 - 20  # 제목 옆
    ph_y = y
    phone_h = 340
    img_ph(draw, ph_x, ph_y, 310, phone_h,
           "스마트폰 화면\n쇼핑몰 하단\n'사업자 정보'\n집 주소 확대\n돋보기 강조",
           border_color=(150, 40, 40))
    # 폰 안 강조 테두리 (빨간 박스 표시)
    draw.rectangle([ph_x + 16, ph_y + phone_h - 90,
                    ph_x + 294, ph_y + phone_h - 16],
                   outline=RED, width=3)
    fph = font(20, bold=True)
    draw.text((ph_x + 22, ph_y + phone_h - 82 - fph.getbbox("집")[1]),
              "사업장 소재지: 서울시 ○○구 ○○아파트 ○동 ○호",
              font=fph, fill=RED_GLOW)

    y_txt = ph_y

    # 내용 블록 1
    draw.rounded_rectangle([MARGIN, y_txt, ph_x - 20, y_txt + 150],
                            radius=14, fill=CARD_BOX)
    draw.rectangle([MARGIN, y_txt, MARGIN + 6, y_txt + 150], fill=RED)
    f_b = font(30)
    put_wrap(draw, "쇼핑몰 하단·홈택스 조회로 내 집 주소가 인터넷에 그대로 노출됩니다.",
             f_b, MARGIN + 22, y_txt + 18, WHITE, ph_x - MARGIN - 42, gap=7)
    y_txt += 166

    # 내용 블록 2
    draw.rounded_rectangle([MARGIN, y_txt, ph_x - 20, y_txt + 150],
                            radius=14, fill=CARD_BOX)
    draw.rectangle([MARGIN, y_txt, MARGIN + 6, y_txt + 150], fill=RED)
    put_wrap(draw, "악성 민원인·스토커가 내 가족이 사는 공간까지 찾아올 수 있습니다.",
             f_b, MARGIN + 22, y_txt + 18, WHITE, ph_x - MARGIN - 42, gap=7)
    y_txt += 166

    y = max(ph_y + phone_h, y_txt) + 28

    # 강조 바
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + 72], radius=12, fill=RED_DARK)
    f_em = font(36, bold=True)
    em = "24시간 전 국민에게 공개 중인 당신의 집 주소"
    ew = draw.textlength(em, font=f_em)
    draw.text(((W - ew) // 2, y + 18 - f_em.getbbox(em)[1]), em, font=f_em, fill=YELLOW)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "01_사생활증발.png"), "PNG")
    print("01_사생활증발.png 저장")


# ═══════════════════════════════════════════════════════════
# 2컷 — "OO아파트 주민이 비즈니스 파트너?"
# ═══════════════════════════════════════════════════════════
def card02():
    img  = make_bg(top=(14, 10, 22), bot=DARK_BG)
    draw = ImageDraw.Draw(img)

    danger_badge(draw, "2컷", MARGIN, 66, fill=(40, 25, 60), text_fill=YELLOW)
    danger_badge(draw, "신뢰도 추락", MARGIN + 90, 66, fill=YELLOW, text_fill=DARK_BG)

    y = 66 + 44 + 20

    left_bar(draw, y, 8, color=YELLOW)
    f_main = font(66, bold=True)
    y = put(draw, '"○○아파트 주민이', f_main, MARGIN + 20, y, WHITE) + 8
    y = put(draw, '비즈니스 파트너?"', f_main, MARGIN + 20, y, YELLOW) + 28

    # 말풍선 + 캐릭터 플레이스홀더
    ph_h = 300
    img_ph(draw, MARGIN, y, W - MARGIN * 2, ph_h,
           "정장 입은 바이어가 지도 앱을 보며 당황하는 모습\n지도에 아파트 단지 표시\n말풍선: \"어… 아파트네?\"",
           border_color=(120, 100, 20))

    # 말풍선 오버레이
    bubble_x = W - MARGIN - 320
    bubble_y = y + 20
    draw.rounded_rectangle([bubble_x, bubble_y, bubble_x + 300, bubble_y + 80],
                            radius=14, fill=(40, 36, 10))
    draw.rounded_rectangle([bubble_x + 1, bubble_y + 1,
                             bubble_x + 299, bubble_y + 79],
                            radius=13, outline=YELLOW, width=2)
    fb = font(28, bold=True)
    draw.text((bubble_x + 18, bubble_y + 18 - fb.getbbox("어")[1]),
              "어… 이거 아파트 주소인데?", font=fb, fill=YELLOW)

    y += ph_h + 28

    # 내용 박스 2개
    bw = (W - MARGIN * 2 - 20) // 2
    bh = 156

    # 박스 ①
    draw.rounded_rectangle([MARGIN, y, MARGIN + bw, y + bh], radius=14, fill=CARD_BOX)
    draw.rounded_rectangle([MARGIN, y, MARGIN + bw, y + bh],
                            outline=YELLOW, width=2, radius=14)
    f_bx = font(30, bold=True)
    f_bx2= font(26)
    draw.text((MARGIN + 16, y + 14 - f_bx.getbbox("계")[1]),
              "계약 직전 거래처가", font=f_bx, fill=YELLOW)
    draw.text((MARGIN + 16, y + 52 - f_bx.getbbox("주")[1]),
              "주소 검색 → 아파트 노출", font=f_bx, fill=WHITE)
    put_wrap(draw, "신뢰도 0 이 됩니다.",
             f_bx2, MARGIN + 16, y + 96, GRAY, bw - 32, gap=5)

    # 박스 ②
    bx2 = MARGIN + bw + 20
    draw.rounded_rectangle([bx2, y, bx2 + bw, y + bh], radius=14, fill=CARD_BOX)
    draw.rounded_rectangle([bx2, y, bx2 + bw, y + bh],
                            outline=(150, 130, 30), width=2, radius=14)
    draw.text((bx2 + 16, y + 14 - f_bx.getbbox("아")[1]),
              "아무리 좋은 아이템도", font=f_bx, fill=YELLOW)
    draw.text((bx2 + 16, y + 52 - f_bx.getbbox("구")[1]),
              "구멍가게처럼 보입니다", font=f_bx, fill=WHITE)
    put_wrap(draw, "첫인상이 계약을 좌우합니다.",
             f_bx2, bx2 + 16, y + 96, GRAY, bw - 32, gap=5)

    y += bh + 24

    # 강조 바
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + 68], radius=12,
                            fill=(50, 42, 8))
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + 68],
                            outline=YELLOW, width=2, radius=12)
    f_em = font(34, bold=True)
    em = "주소 하나가 수백만 원짜리 계약을 날립니다"
    ew = draw.textlength(em, font=f_em)
    draw.text(((W - ew) // 2, y + 16 - f_em.getbbox(em)[1]), em, font=f_em, fill=YELLOW)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "02_신뢰도추락.png"), "PNG")
    print("02_신뢰도추락.png 저장")


# ═══════════════════════════════════════════════════════════
# 3컷 — "싼 게 비지떡? 유령 사무실의 함정"
# ═══════════════════════════════════════════════════════════
def card03():
    img  = make_bg(top=(20, 8, 8), bot=DARK_BG)
    draw = ImageDraw.Draw(img)

    danger_badge(draw, "3컷", MARGIN, 66, fill=(60, 20, 20), text_fill=RED_GLOW)
    danger_badge(draw, "가짜 비상주 주의!", MARGIN + 90, 66, fill=RED)

    y = 66 + 44 + 18

    left_bar(draw, y, 8, color=RED)
    f_main = font(64, bold=True)
    y = put(draw, '"싼 게 비지떡?', f_main, MARGIN + 20, y, WHITE) + 8
    y = put(draw, '유령 사무실의 함정"', f_main, MARGIN + 20, y, RED_GLOW) + 24

    # 도장 이미지 플레이스홀더 (우측)
    stamp_x = W - MARGIN - 260
    stamp_y = y - th(f_main) * 2 - 24 - 18
    stamp_y = y
    draw.rounded_rectangle([stamp_x, stamp_y, stamp_x + 260, stamp_y + 180],
                            radius=16, fill=(40, 10, 10))
    draw.rounded_rectangle([stamp_x + 4, stamp_y + 4,
                             stamp_x + 256, stamp_y + 176],
                            radius=12, outline=RED_DARK, width=3)
    # 도장 텍스트
    f_stamp1 = font(24, bold=True)
    f_stamp2 = font(46, bold=True)
    f_stamp3 = font(20)
    st1 = "사업자 등록"
    st2 = "반려"
    st3 = "주소지 실사 불일치"
    for st, fs, fc, sy in [
        (st1, f_stamp1, GRAY,     stamp_y + 24),
        (st2, f_stamp2, RED_GLOW, stamp_y + 68),
        (st3, f_stamp3, GRAY_DIM, stamp_y + 140),
    ]:
        sw = draw.textlength(st, font=fs)
        draw.text((stamp_x + (260 - sw) // 2, sy - fs.getbbox(st)[1]),
                  st, font=fs, fill=fc)
    # 도장 테두리 (이중 원)
    cx, cy = stamp_x + 130, stamp_y + 90
    draw.ellipse([cx - 110, cy - 70, cx + 110, cy + 70], outline=RED, width=3)
    draw.ellipse([cx - 103, cy - 63, cx + 103, cy + 63], outline=RED_DARK, width=1)

    y_check = stamp_y + 180 + 20

    # 체크리스트 3개
    bw = W - MARGIN * 2
    bh = 142
    gap = 14
    items = [
        ("①", "실제 공간 있는가?",
         "관공서 실사 시 실제 공간 없으면 사업자 취소. 꼭 실물 사무실 확인!"),
        ("②", "본사 직영인가?",
         "중개·대행 업체는 문제 발생 시 책임 회피. 계약서 임대인 = 판매자 일치 확인."),
        ("③", "우편물 관리 철저?",
         "주소지에 오는 세금계산서·공문 관리 미흡하면 중요 서류 분실 위험."),
    ]
    for i, (num, title, desc) in enumerate(items):
        check_item(draw, num, title, desc,
                   MARGIN, y_check + i * (bh + gap), bw, bh,
                   num_fill=RED)

    y_bottom = y_check + len(items) * (bh + gap) + 10
    if y_bottom + 60 < H - MARGIN - 70:
        draw.rounded_rectangle([MARGIN, y_bottom, W - MARGIN, y_bottom + 56],
                                radius=10, fill=RED_DARK)
        f_w = font(30, bold=True)
        wt = "3가지 중 하나라도 빠지면 → 사업자 취소 위험!"
        ww = draw.textlength(wt, font=f_w)
        draw.text(((W - ww) // 2, y_bottom + 14 - f_w.getbbox(wt)[1]),
                  wt, font=f_w, fill=YELLOW)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "03_유령사무실.png"), "PNG")
    print("03_유령사무실.png 저장")


# ═══════════════════════════════════════════════════════════
# 4컷 — "소 잃고 외양간 고치면 늦습니다" (결론·CTA)
# ═══════════════════════════════════════════════════════════
def card04():
    img  = make_bg(top=(8, 20, 16), bot=DARK_BG)  # 초록 톤 → 안전감
    draw = ImageDraw.Draw(img)

    danger_badge(draw, "4컷", MARGIN, 66, fill=(15, 50, 35), text_fill=TEAL)
    danger_badge(draw, "지금 바로 해결하세요", MARGIN + 90, 66,
                 fill=TEAL, text_fill=DARK_BG)

    y = 66 + 44 + 20

    left_bar(draw, y, 8, color=TEAL)
    f_main = font(68, bold=True)
    y = put(draw, '"소 잃고 외양간', f_main, MARGIN + 20, y, WHITE) + 8
    y = put(draw, '고치면 늦습니다"', f_main, MARGIN + 20, y, TEAL) + 24

    # 번듯한 오피스 빌딩 플레이스홀더
    ph_h = 260
    img_ph(draw, MARGIN, y, W - MARGIN * 2, ph_h,
           "현대적인 오피스 빌딩 외관 사진\n(밝고 전문적인 느낌 / 마인오피스 실제 사진 추천)",
           border_color=(30, 140, 100))
    # 플레이스홀더 위 안전 레이블
    lf = font(28, bold=True)
    lt = "✅  안전한 사업자 주소지"
    lw = int(draw.textlength(lt, font=lf))
    draw.rounded_rectangle([W // 2 - lw // 2 - 14, y + ph_h - 52,
                             W // 2 + lw // 2 + 14, y + ph_h - 8],
                            radius=8, fill=(20, 100, 70))
    draw.text((W // 2 - lw // 2, y + ph_h - 46 - lf.getbbox(lt)[1]),
              lt, font=lf, fill=WHITE)

    y += ph_h + 24

    # 포인트 2개 가로 박스
    bw = (W - MARGIN * 2 - 18) // 2
    bh = 130

    # 왼쪽: 문제
    draw.rounded_rectangle([MARGIN, y, MARGIN + bw, y + bh], radius=14, fill=CARD_BOX)
    draw.rectangle([MARGIN, y, MARGIN + 6, y + bh], fill=RED)
    f_pb = font(28, bold=True)
    f_pb2= font(25)
    draw.text((MARGIN + 18, y + 14 - f_pb.getbbox("한")[1]),
              "한 번 노출된 주소는", font=f_pb, fill=RED_GLOW)
    draw.text((MARGIN + 18, y + 50 - f_pb.getbbox("이")[1]),
              "이사 후에도 기록에 남음", font=f_pb, fill=WHITE)
    put_wrap(draw, "인터넷 기록은 영구히 삭제되지 않습니다.",
             f_pb2, MARGIN + 18, y + 88, GRAY, bw - 34, gap=4)

    # 오른쪽: 해결책
    bx2 = MARGIN + bw + 18
    draw.rounded_rectangle([bx2, y, bx2 + bw, y + bh], radius=14, fill=CARD_BOX)
    draw.rectangle([bx2, y, bx2 + 6, y + bh], fill=TEAL)
    draw.text((bx2 + 18, y + 14 - f_pb.getbbox("월")[1]),
              "월 몇만 원의 선택이", font=f_pb, fill=TEAL)
    draw.text((bx2 + 18, y + 50 - f_pb.getbbox("가")[1]),
              "가족·사업 모두를 지킴", font=f_pb, fill=WHITE)
    put_wrap(draw, "비상주 사무실 = 가장 싼 보험",
             f_pb2, bx2 + 18, y + 88, GRAY, bw - 34, gap=4)

    y += bh + 22

    # 최종 CTA 버튼
    cta_h = 140
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + cta_h], radius=20,
                            fill=(18, 110, 75))
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + cta_h],
                            outline=TEAL, width=3, radius=20)
    f_cta  = font(38, bold=True)
    f_cta2 = font(30)
    cta1 = "안전한 비상주 주소지로 지금 변경하세요!"
    cta2 = "마인공유오피스 | 보증금 0원 · 관리비 0원 · 직영 운영"
    cw1 = draw.textlength(cta1, font=f_cta)
    cw2 = draw.textlength(cta2, font=f_cta2)
    draw.text(((W - cw1) // 2, y + 22 - f_cta.getbbox(cta1)[1]),
              cta1, font=f_cta, fill=WHITE)
    draw.text(((W - cw2) // 2, y + 78 - f_cta2.getbbox(cta2)[1]),
              cta2, font=f_cta2, fill=TEAL)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "04_결론CTA.png"), "PNG")
    print("04_결론CTA.png 저장")


# ── 실행 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("마인오피스 카드뉴스 v2 생성 중...")
    card00()
    card01()
    card02()
    card03()
    card04()
    print(f"\n완료! {OUTPUT}")
