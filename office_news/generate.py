from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, io, urllib.request, math
from card_renderer import font, lerp, th, put, put_wrap
from card_renderer import make_bg as _make_bg

W, H = 1080, 1080
OUTPUT = r"C:\Users\JW\Desktop\workspace\office_news\output"
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
MARGIN    = 72

def make_bg():
    return _make_bg(W, H, NAVY_MID, NAVY)

# 특정 키워드만 다른 색으로 그리는 인라인 텍스트
def put_inline(draw, parts_colors, f, x, y):
    for text, fill in parts_colors:
        bb = f.getbbox(text) if text else None
        if text:
            draw.text((x, y - f.getbbox(text)[1]), text, font=f, fill=fill)
            x += int(draw.textlength(text, font=f))
    if parts_colors:
        last_text = parts_colors[-1][0]
        last_bb   = f.getbbox(last_text)
        return y + (last_bb[3] - last_bb[1])
    return y

# ── 공통 UI ─────────────────────────────────────────────────
def draw_logo(img, draw):
    """JW 아이콘 + JUNGWON OFFICE NET — 하단 중앙"""
    ICON = 64
    f_brand = font(34, bold=True)
    brand   = "JUNGWON OFFICE NET"
    bw      = int(draw.textlength(brand, font=f_brand))
    total_w = ICON + 18 + bw
    sx      = (W - total_w) // 2
    iy      = H - MARGIN - ICON + 8

    draw.rounded_rectangle([sx, iy, sx + ICON, iy + ICON],
                            radius=12, fill=(22, 90, 55))
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        ratio  = ICON / max(logo.width, logo.height)
        lw, lh = int(logo.width * ratio), int(logo.height * ratio)
        logo_r = logo.resize((lw, lh), Image.LANCZOS)
        img.paste(logo_r, (sx + (ICON - lw) // 2, iy + (ICON - lh) // 2), mask=logo_r.split()[3])
    except:
        fj = font(26, bold=True)
        bb = fj.getbbox("JW")
        draw.text((sx + (ICON - int(draw.textlength("JW", font=fj))) // 2,
                   iy + (ICON - (bb[3] - bb[1])) // 2 - bb[1]), "JW", font=fj, fill=WHITE)

    tx = sx + ICON + 18
    bb = f_brand.getbbox(brand)
    ty = iy + (ICON - (bb[3] - bb[1])) // 2
    draw.text((tx, ty - bb[1]), brand, font=f_brand, fill=WHITE)

def left_bar(draw, y_top, height):
    draw.rectangle([MARGIN, y_top, MARGIN + 6, y_top + height], fill=TEAL)

def pill_badge(img, draw, text, cx, y, fill=YELLOW, text_fill=NAVY):
    f  = font(32, bold=True)
    bb = f.getbbox(text)
    lw = int(draw.textlength(text, font=f))
    lh = bb[3] - bb[1]
    pw, ph = lw + 56, lh + 22
    bx = cx - pw // 2
    draw.rounded_rectangle([bx, y, bx + pw, y + ph], radius=ph // 2, fill=fill)
    draw.text((bx + 28, y + 11 - bb[1]), text, font=f, fill=text_fill)
    return ph

def item_box(img, draw, icon_char, title, desc, bx, by, bw, bh):
    """아이콘 + 제목 + 설명 — 어두운 둥근 박스"""
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=20, fill=CARD_BOX)
    # 아이콘
    fi = font(58, bold=True)
    ix = bx + 28; iy = by + 24
    draw.text((ix, iy - fi.getbbox(icon_char)[1]), icon_char, font=fi, fill=YELLOW)
    # 제목
    ft = font(46, bold=True)
    tx = ix + int(draw.textlength(icon_char, font=fi)) + 18
    bb_t = ft.getbbox(title)
    ty   = iy + (58 - (bb_t[3] - bb_t[1])) // 2
    draw.text((tx, ty - bb_t[1]), title, font=ft, fill=WHITE)
    # 설명 (wrap)
    put_wrap(draw, desc, font(30), bx + 28, by + 108, GRAY_TEXT, bw - 56, gap=6)

def fetch_photo(url, w, h):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            img = Image.open(io.BytesIO(r.read())).convert("RGB")
            return img.resize((w, h), Image.LANCZOS)
    except:
        return Image.new("RGB", (w, h), CARD_BOX)

# ═══════════════════════════════════════════════════════════
# 카드 1 — 표지
# ═══════════════════════════════════════════════════════════
def card01():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    # 상단 배지
    ph = pill_badge(img, draw, "정원오피스넷과 함께하는", W // 2, 80)

    # 메인 타이틀
    y = 80 + ph + 56
    f_big = font(108, bold=True)
    y = put(draw, "개인사업자 90%가", f_big, 0, y, WHITE, align="center") + 10
    # '이것' 강조
    line2_parts = [("'", WHITE), ("이것", YELLOW), ("' 때문에", WHITE)]
    lw2 = sum(int(draw.textlength(t, font=f_big)) for t, _ in line2_parts)
    x2  = (W - lw2) // 2
    y2_start = y
    for text, fill in line2_parts:
        if text:
            bb = f_big.getbbox(text)
            draw.text((x2, y - bb[1]), text, font=f_big, fill=fill)
            x2 += int(draw.textlength(text, font=f_big))
    y = y2_start + th(f_big) + 10
    y = put(draw, "세금을 수백만원", f_big, 0, y, WHITE, align="center") + 10
    y = put(draw, "더 내고 있습니다.", f_big, 0, y, WHITE, align="center") + 52

    # 서브타이틀
    f_sub = font(44, bold=True)
    y = put(draw, '"난 다 챙겼는데?" 하다가', f_sub, 0, y, YELLOW, align="center") + 8
    put(draw, "당하는 5월 종소세 필승 비법", f_sub, 0, y, YELLOW, align="center")

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "1.png"), "PNG")
    print("1.png 저장")

# ═══════════════════════════════════════════════════════════
# 카드 2 — 경조사비 20만 원
# ═══════════════════════════════════════════════════════════
def card02():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    # 좌측 타이틀 바
    left_bar(draw, 72, 160)
    f_title = font(76, bold=True)
    y = 72
    y = put(draw, "경조사비 20만 원,", f_title, MARGIN + 22, y, WHITE) + 8
    y = put(draw, "청첩장 캡처로 끝!", f_title, MARGIN + 22, y, WHITE) + 48

    # 인셋 사진 (우측)
    photo = fetch_photo("https://picsum.photos/seed/phone-wedding/340/240", 340, 240)
    photo = photo.filter(ImageFilter.GaussianBlur(0.5))
    img.paste(photo, (W - MARGIN - 340, 72))

    # 본문
    f_body = font(38)
    body = ("거래처 사장님 아들 결혼식 가셨죠? 축의금 20만 원 내신 거, "
            "모바일 청첩장 캡처만 있으면 경비 인정됩니다.")
    y = put_wrap(draw, body, f_body, MARGIN, y, WHITE, W - MARGIN * 2, gap=10)
    y += 28

    # 강조 문장
    f_em = font(38, bold=True)
    y = put(draw, "일 년에 딱 10번만 챙겨도 200만원입니다.", f_em, MARGIN, y, WHITE) + 16
    f_tip = font(36)
    put_wrap(draw, "당장 카톡 검색창에 '죽의', '부고' 처서 캡처부터 하세요!", f_tip, MARGIN, y, GRAY_TEXT, W - MARGIN * 2, gap=8)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "2.png"), "PNG")
    print("2.png 저장")

# ═══════════════════════════════════════════════════════════
# 카드 3 — 이체 내역
# ═══════════════════════════════════════════════════════════
def card03():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    left_bar(draw, 72, 160)
    f_title = font(76, bold=True)
    y = 72
    y = put(draw, "영수증 없다고 포기?", f_title, MARGIN + 22, y, WHITE) + 8
    # '이체 내역' 강조
    line_parts = [("'이체 내역'", YELLOW), ("이 무기입니다.", WHITE)]
    x = MARGIN + 22
    for text, fill in line_parts:
        bb = f_title.getbbox(text)
        draw.text((x, y - bb[1]), text, font=f_title, fill=fill)
        x += int(draw.textlength(text, font=f_title))
    y += th(f_title) + 48

    # 인셋 사진 (우측)
    photo = fetch_photo("https://picsum.photos/seed/receipts-desk/320/220", 320, 220)
    img.paste(photo, (W - MARGIN - 320, 72))

    # 본문
    f_body = font(38)
    body = ("골프비, 수리비, 단기 알바비… 상대방이 영수증 안 끊어준다고 억울해 마세요. "
            "사업용으로 썼다는 사실만 입증되면 통장 이체 내역서(보낸 사람, 금액, 날짜)로도 "
            "충분히 비용 인정받을 수 있습니다.")
    y = put_wrap(draw, body, f_body, MARGIN, y, WHITE, W - MARGIN * 2, gap=10)
    y += 20
    f_em = font(38, bold=True)
    put(draw, "일단 돈 보낸 내역은 꼭 다 긁어 모아야 합니다.", f_em, MARGIN, y, WHITE)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "3.png"), "PNG")
    print("3.png 저장")

# ═══════════════════════════════════════════════════════════
# 카드 4 — 홈택스 카드 등록
# ═══════════════════════════════════════════════════════════
def card04():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    left_bar(draw, 72, 150)
    f_title = font(76, bold=True)
    y = 72
    # '카드' 강조
    tx_parts = [("홈택스 ", WHITE), ("카드", YELLOW), (" 등록,", WHITE)]
    x = MARGIN + 22
    for text, fill in tx_parts:
        bb = f_title.getbbox(text)
        draw.text((x, y - bb[1]), text, font=f_title, fill=fill)
        x += int(draw.textlength(text, font=f_title))
    y += th(f_title) + 8
    y = put(draw, "안 하면 생돈 버립니다.", f_title, MARGIN + 22, y, WHITE) + 52

    # 3개 아이템 박스
    bw = W - MARGIN * 2
    bh = 170
    gap = 20
    items = [
        ("💳", "자동 인식의 착각",   "내 명의 카드라고 국세청이 알아서 챙겨주지 않습니다."),
        ("📄", "사적 비용 오해",     "미등록 카드로 쓴 돈은 '개인 여가비'로 간주해버립니다."),
        ("🔍", "지금 즉시 확인",    "홈택스 '사업용 신용카드 등록' 메뉴부터 꼭 체크하세요!"),
    ]
    for i, (icon, title, desc) in enumerate(items):
        item_box(img, draw, icon, title, desc, MARGIN, y + i * (bh + gap), bw, bh)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "4.png"), "PNG")
    print("4.png 저장")

# ═══════════════════════════════════════════════════════════
# 카드 5 — 기부금 영수증
# ═══════════════════════════════════════════════════════════
def card05():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    left_bar(draw, 72, 150)
    f_title = font(76, bold=True)
    y = 72
    y = put(draw, "기부금 영수증,", f_title, MARGIN + 22, y, WHITE) + 8
    y = put(draw, "가만히 있으면 안 줍니다.", f_title, MARGIN + 22, y, WHITE) + 52

    bw = W - MARGIN * 2
    bh = 170
    gap = 20
    items = [
        ("⛪", "자동 조회의 한계",   "종교 단체나 복지재단은 국세청에 자료를 누락하는 경우가 많습니다."),
        ("📞", "직접 전화해서 요청", '"기부금 영수증 하나 보내주세요." 이 한마디면 15~30% 세액 공제가 따라옵니다.'),
        ("💰", "수동 입력 필수",     "연말정산 간소화만 믿지 말고, 수동으로 챙겨야 내 돈을 지킵니다."),
    ]
    for i, (icon, title, desc) in enumerate(items):
        item_box(img, draw, icon, title, desc, MARGIN, y + i * (bh + gap), bw, bh)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "5.png"), "PNG")
    print("5.png 저장")

# ═══════════════════════════════════════════════════════════
# 카드 6 — 무신고 가산세 20%
# ═══════════════════════════════════════════════════════════
def card06():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    left_bar(draw, 72, 100)
    f_title = font(82, bold=True)
    y = 72
    # '신고' 강조
    tx_parts = [("돈 없어도 ", WHITE), ("신고", ORANGE), ("는 필수!", WHITE)]
    x = MARGIN + 22
    for text, fill in tx_parts:
        bb = f_title.getbbox(text)
        draw.text((x, y - bb[1]), text, font=f_title, fill=fill)
        x += int(draw.textlength(text, font=f_title))
    y += th(f_title) + 48

    # 큰 숫자 20%
    f_big = font(240, bold=True)
    y = put(draw, "20%", f_big, 0, y, ORANGE, align="center") + 8
    f_sub = font(44, bold=True)
    y = put(draw, "무신고 가산세 폭탄", f_sub, 0, y, WHITE, align="center") + 44

    # 설명 박스 (왼쪽 빨간 세로 보더)
    box_h = 220
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + box_h], radius=16, fill=CARD_BOX)
    draw.rectangle([MARGIN, y, MARGIN + 6, y + box_h], fill=ORANGE)
    f_body = font(36)
    body1 = "5월 31일 넘기는 순간, 낼 세금의 20%가 벌금으로 강제 추가됩니다."
    body2 = "당장 세금 낼 현금이 부족해도 괜찮습니다. 일단 5월 안에 '신고'만 해두세요. 그래야 가산세 벼락을 피할 수 있습니다."
    y2 = y + 22
    y2 = put_wrap(draw, body1, f_body, MARGIN + 24, y2, WHITE, W - MARGIN * 2 - 24, gap=8)
    y2 += 8
    put_wrap(draw, body2, f_body, MARGIN + 24, y2, GRAY_TEXT, W - MARGIN * 2 - 24, gap=8)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "6.png"), "PNG")
    print("6.png 저장")

# ═══════════════════════════════════════════════════════════
# 카드 7 — 조금만 챙겨도 바뀌는 세금
# ═══════════════════════════════════════════════════════════
def card07():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    left_bar(draw, 72, 90)
    f_title = font(82, bold=True)
    y = 72
    y = put(draw, "조금만 챙겨도 바뀌는 세금", f_title, MARGIN + 22, y, WHITE) + 64

    # 바 차트
    f_label = font(36)
    f_val   = font(38, bold=True)
    bar_h   = 68
    bar_y1  = y

    # 챙기기 전 (회색)
    label1 = "챙기기 전(예상)"
    draw.text((MARGIN, bar_y1 - f_label.getbbox(label1)[1]), label1, font=f_label, fill=GRAY_TEXT)
    bx1 = MARGIN + 260
    draw.rounded_rectangle([bx1, bar_y1, W - MARGIN, bar_y1 + bar_h], radius=bar_h // 2, fill=(90, 100, 130))
    val1 = "850만 원"
    vb1  = f_val.getbbox(val1)
    draw.text((W - MARGIN - int(draw.textlength(val1, font=f_val)) - 20,
               bar_y1 + (bar_h - (vb1[3] - vb1[1])) // 2 - vb1[1]), val1, font=f_val, fill=WHITE)

    bar_y2 = bar_y1 + bar_h + 24
    label2 = "꿀팁 적용 후"
    draw.text((MARGIN, bar_y2 - f_label.getbbox(label2)[1]), label2, font=f_label, fill=GRAY_TEXT)
    bar2_w = int((W - MARGIN - bx1) * 0.62)
    draw.rounded_rectangle([bx1, bar_y2, bx1 + bar2_w, bar_y2 + bar_h], radius=bar_h // 2, fill=TEAL)
    # 오른쪽 잔여 (어두운)
    draw.rounded_rectangle([bx1, bar_y2, W - MARGIN, bar_y2 + bar_h], radius=bar_h // 2, fill=(30, 55, 90))
    draw.rounded_rectangle([bx1, bar_y2, bx1 + bar2_w, bar_y2 + bar_h], radius=bar_h // 2, fill=TEAL)
    val2 = "520만 원"
    vb2  = f_val.getbbox(val2)
    draw.text((bx1 + 20, bar_y2 + (bar_h - (vb2[3] - vb2[1])) // 2 - vb2[1]), val2, font=f_val, fill=NAVY)

    y = bar_y2 + bar_h + 64

    # 타임라인
    dot_x  = MARGIN + 16
    line_x = dot_x
    f_tl   = font(42, bold=True)
    f_tl2  = font(36)
    dot_r  = 16
    tl_items = [
        ("5월 1일 ~ 31일",   "정기 신고 및 납부 기간",    TEAL),
        ("6월 말 ~ 7월 초",  "종합소득세 환급금 지급 시작", TEAL),
    ]
    for date_text, desc_text, col in tl_items:
        draw.ellipse([dot_x - dot_r, y, dot_x + dot_r, y + dot_r * 2], fill=col)
        tx = dot_x + dot_r + 24
        y2 = put(draw, date_text, f_tl, tx, y, YELLOW) + 6
        put(draw, desc_text, f_tl2, tx, y2, WHITE)
        # 세로 연결선
        if date_text != tl_items[-1][0]:
            draw.rectangle([dot_x - 2, y + dot_r * 2, dot_x + 2, y + dot_r * 2 + 60], fill=(60, 80, 120))
        y += dot_r * 2 + 70

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "7.png"), "PNG")
    print("7.png 저장")

# ═══════════════════════════════════════════════════════════
# 카드 8 — 마무리 CTA
# ═══════════════════════════════════════════════════════════
def card08():
    img  = make_bg()
    draw = ImageDraw.Draw(img)

    # 큰 제목 (중앙)
    f_big = font(110, bold=True)
    y = 160
    y = put(draw, "더 궁금한 점이", f_big, 0, y, WHITE, align="center") + 12
    y = put(draw, "있으신가요?", f_big, 0, y, WHITE, align="center") + 44

    f_sub = font(46, bold=True)
    y = put(draw, "댓글로 자유롭게 질문 남겨주세요!", f_sub, 0, y, YELLOW, align="center") + 60

    # 설명 박스
    box_h = 300
    bx = MARGIN
    draw.rounded_rectangle([bx, y, W - bx, y + box_h], radius=20, fill=CARD_BOX)

    # 박스 내 로고
    ICON = 56
    ix = bx + 28; iy = y + 28
    draw.rounded_rectangle([ix, iy, ix + ICON, iy + ICON], radius=10, fill=(22, 90, 55))
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        ratio  = ICON / max(logo.width, logo.height)
        lw2, lh2 = int(logo.width * ratio), int(logo.height * ratio)
        logo_r = logo.resize((lw2, lh2), Image.LANCZOS)
        img.paste(logo_r, (ix + (ICON - lw2) // 2, iy + (ICON - lh2) // 2), mask=logo_r.split()[3])
    except:
        pass
    f_brand2 = font(36, bold=True)
    brand_text = "공유오피스 정원오피스넷"
    bb = f_brand2.getbbox(brand_text)
    draw.text((ix + ICON + 16, iy + (ICON - (bb[3] - bb[1])) // 2 - bb[1]),
              brand_text, font=f_brand2, fill=WHITE)

    f_desc = font(34)
    desc = ("저희는 사장님들의 든든한 비즈니스 파트너입니다. "
            "쾌적한 업무 공간은 물론, 앞으로도 사업에 피가 되고 살이 되는 "
            "실전 꿀팁들을 아낌없이 공유해 드릴게요.")
    dy = y + 28 + ICON + 20
    dy = put_wrap(draw, desc, f_desc, bx + 28, dy, GRAY_TEXT, W - bx * 2 - 56, gap=8)
    dy += 16
    f_cta = font(34, bold=True)
    put(draw, "팔로우하시고 돈 버는 정보 놓치지 마세요!", f_cta, 0, dy, WHITE, align="center")

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "8.png"), "PNG")
    print("8.png 저장")

# ── 실행 ───────────────────────────────────────────────────
print("생성 시작...")
card01(); card02(); card03(); card04()
card05(); card06(); card07(); card08()
print(f"\n완료! {OUTPUT} 에서 확인하세요.")
