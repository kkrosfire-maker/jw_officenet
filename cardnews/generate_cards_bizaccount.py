from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import os, io, urllib.request

W, H = 1080, 1350
OUTPUT = r"C:\Users\JW\Desktop\workspace\cardnews\output_bizaccount"
os.makedirs(OUTPUT, exist_ok=True)

FONT_REG  = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
LOGO_PATH = r"C:\Users\JW\Desktop\정원유니어스\정원로고.png"

def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)

# ── 블루(은행/금융) 전용 팔레트 ─────────────────────────────
BL_NAVY  = ( 20,  40,  74)   # 짙은 네이비
BL_DEEP  = ( 27,  61, 110)   # 딥 블루
BL_MID   = ( 41,  91, 156)   # 미드 블루
BL_SKY   = ( 84, 140, 199)   # 스카이 블루
BL_LIGHT = (140, 182, 224)   # 연블루
BL_PALE  = (190, 216, 240)   # 파스텔 블루 (어두운 배경 강조용)
BL_BG    = (231, 241, 251)   # 블루 배경 (카드 내부)
SKY_BG   = (245, 249, 253)   # 스카이 크림 (전체 배경)
DARK     = ( 18,  30,  46)   # 텍스트 (짙은 네이비)
SUB_TEXT = ( 92, 112, 136)   # 보조 텍스트
WHITE    = (255, 255, 255)
MARGIN   = 64
COLS     = [BL_NAVY, BL_MID, BL_SKY]

# ── 그라디언트 (짙은 네이비 → 밝은 스카이블루) ────────────
def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def make_gradient(w, h, stops):
    img = Image.new("RGB", (1, h))
    px  = img.load()
    stops = sorted(stops, key=lambda s: s[0])
    for y in range(h):
        t = y / max(h - 1, 1)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]; t1, c1 = stops[i + 1]
            if t <= t1:
                f = (t - t0) / (t1 - t0) if t1 > t0 else 0
                px[0, y] = lerp(c0, c1, f); break
    return img.resize((w, h))

def bank_grad(w, h):
    return make_gradient(w, h, [
        (0.00, BL_NAVY),
        (0.25, BL_DEEP),
        (0.52, BL_MID),
        (0.76, BL_SKY),
        (1.00, (172, 206, 236)),
    ])

def paste_grad_rounded(img, gw, gh, dx, dy, radius):
    grad = bank_grad(gw, gh)
    mask = Image.new("L", (gw, gh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, gw, gh], radius=radius, fill=255)
    img.paste(grad, (dx, dy), mask=mask)

# ── 관련 사진 다운로드 (LoremFlickr 키워드 → picsum 폴백) ─
PHOTO_URLS = {
    "cover":   ("https://picsum.photos/seed/bizaccount-cover-26/1080/500",
                "https://picsum.photos/seed/bank-card-2026/1080/500"),
    "account": ("https://picsum.photos/seed/bizaccount-passbook-26/1080/500",
                "https://picsum.photos/seed/passbook-open/1080/500"),
    "card":    ("https://picsum.photos/seed/bizaccount-card-26/1080/500",
                "https://picsum.photos/seed/card-wallet/1080/500"),
    "hometax": ("https://picsum.photos/seed/bizaccount-hometax-26/1080/500",
                "https://picsum.photos/seed/laptop-desk-tax/1080/500"),
    "cta":     ("https://picsum.photos/seed/bizaccount-cta-26/1080/600",
                "https://picsum.photos/seed/notebook-planner/1080/600"),
}

def fetch_photo(key, w, h):
    primary, fallback = PHOTO_URLS[key]
    for url in (primary, fallback):
        print(f"  다운로드: {url}")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                return Image.open(io.BytesIO(r.read())).convert("RGB")
        except Exception as e:
            print(f"  실패({e})")
    print(f"  -> 블루 그라디언트 대체")
    return make_gradient(w, h, [
        (0.0, (22, 48, 88)), (0.5, (45, 95, 160)), (1.0, (100, 150, 205))
    ]).convert("RGB")

print("사진 다운로드 중...")
photos = {k: fetch_photo(k, W, 500) for k in PHOTO_URLS}
print("완료\n")

# ── 사진 → 스카이 배경 페이드 ────────────────────────────
def make_photo_header(key, photo_h=400, side_w=160, side_alpha=210):
    raw = photos[key].resize((W, photo_h), Image.LANCZOS)
    raw = raw.filter(ImageFilter.GaussianBlur(0.6))
    raw = ImageEnhance.Color(raw).enhance(0.75)
    # 붉은/녹색 채널 억제 → 블루 계열로 보정
    r, g, b = raw.split()
    r = r.point(lambda x: int(x * 0.72))
    g = g.point(lambda x: int(x * 0.85))
    raw = Image.merge("RGB", (r, g, b))
    result = raw.copy()

    # 상단 어두운 오버레이
    dark_h = photo_h // 2
    dm = Image.new("L", (1, photo_h), 0)
    dp = dm.load()
    for y in range(dark_h):
        dp[0, y] = int((1 - y / dark_h) * 155)
    dm = dm.resize((W, photo_h))
    result.paste(Image.new("RGB", (W, photo_h), (0, 0, 0)), (0, 0), mask=dm)

    # 하단 스카이 페이드
    fade_start = int(photo_h * 0.52)
    fm = Image.new("L", (1, photo_h), 0)
    fp = fm.load()
    for y in range(photo_h):
        if y >= fade_start:
            t = (y - fade_start) / (photo_h - fade_start)
            fp[0, y] = int(t ** 0.72 * 255)
    fm = fm.resize((W, photo_h))
    result.paste(Image.new("RGB", (W, photo_h), SKY_BG), (0, 0), mask=fm)

    # 좌우 사이드 블루 그라디언트 오버레이
    sm = Image.new("L", (side_w, 1), 0)
    sm_px = sm.load()
    for x in range(side_w):
        t = x / max(side_w - 1, 1)
        sm_px[x, 0] = int((1 - t) ** 2.2 * side_alpha)
    sm = sm.resize((side_w, photo_h))
    blue_side = bank_grad(side_w, photo_h)
    result.paste(blue_side, (0, 0), mask=sm)
    result.paste(blue_side, (W - side_w, 0), mask=sm.transpose(Image.FLIP_LEFT_RIGHT))

    return result

def make_canvas(key, photo_h=400):
    img = Image.new("RGB", (W, H), SKY_BG)
    img.paste(make_photo_header(key, photo_h), (0, 0))
    return img

# ── 텍스트 유틸 ──────────────────────────────────────────
def put(draw, text, f, x, y, fill, align="left"):
    bb = f.getbbox(text)
    lw = draw.textlength(text, font=f)
    ox = x
    if align == "center": ox = (W - lw) / 2
    draw.text((ox, y - bb[1]), text, font=f, fill=fill)
    return y + (bb[3] - bb[1])

def wrap(draw, text, f, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=f) <= max_w:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def put_wrap(draw, text, f, x, y, fill, max_w, gap=10):
    for line in wrap(draw, text, f, max_w):
        y = put(draw, line, f, x, y, fill) + gap
    return y

# ── 공통 UI ──────────────────────────────────────────────
def bottom_branding(img, draw):
    draw.rectangle([MARGIN, H - 94, W - MARGIN, H - 92], fill=(175, 205, 232))

    logo_h = 54
    logo_y = H - 86
    text_x = MARGIN
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        ratio = logo_h / logo.height
        logo_w = int(logo.width * ratio)
        logo_r = logo.resize((logo_w, logo_h), Image.LANCZOS)
        img.paste(logo_r, (MARGIN, logo_y), mask=logo_r.split()[3])
        text_x = MARGIN + logo_w + 16
    except Exception as e:
        print(f"  로고 로드 실패: {e}")

    f_brand = font(25, bold=True)
    bb = f_brand.getbbox("JUNGWON OFFICE NET")
    ty = logo_y + (logo_h - (bb[3] - bb[1])) // 2
    draw.text((text_x, ty - bb[1]), "JUNGWON OFFICE NET", font=f_brand, fill=BL_NAVY)

    img.paste(bank_grad(W, 16), (0, H - 16))

def card_num(img, draw, n, total=5):
    f   = font(24, bold=True)
    lbl = f"{n} / {total}"
    bb  = f.getbbox(lbl)
    lh  = bb[3] - bb[1]
    lw  = draw.textlength(lbl, font=f)
    px2, py2 = 22, 11
    bw  = int(lw + px2 * 2)
    bh  = lh + py2 * 2
    bx  = W - MARGIN - bw
    by  = 28
    paste_grad_rounded(img, bw, bh, bx, by, radius=bh // 2)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh // 2,
                            outline=WHITE, width=2)
    draw.text((bx + px2, by + py2 - bb[1]), lbl, font=f, fill=WHITE)

def category_pill(img, draw, text, x, y):
    f   = font(26, bold=True)
    bb  = f.getbbox(text)
    lh  = bb[3] - bb[1]
    lw  = draw.textlength(text, font=f)
    px2, py2 = 24, 12
    pw  = int(lw + px2 * 2)
    ph  = lh + py2 * 2
    paste_grad_rounded(img, pw, ph, x, y, radius=ph // 2)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([x, y, x + pw, y + ph], radius=ph // 2,
                            outline=WHITE, width=2)
    draw.text((x + px2, y + py2 - bb[1]), text, font=f, fill=WHITE)
    return ph

def divider(draw, y):
    draw.rectangle([MARGIN, y, W - MARGIN, y + 2], fill=(195, 220, 240))
    return y + 2

def num_circle(draw, num_str, x, y, size=76, col=BL_NAVY):
    draw.ellipse([x, y, x + size, y + size], fill=col)
    f   = font(26, bold=True)
    bb  = f.getbbox(num_str)
    nw  = draw.textlength(num_str, font=f)
    nh  = bb[3] - bb[1]
    draw.text((x + (size - nw) / 2, y + (size - nh) / 2 - bb[1]),
              num_str, font=f, fill=WHITE)
    return x + size, y + size // 2

def bullet_block(draw, num_str, title, descs, x, y, col=BL_NAVY, size=76):
    rx, cy = num_circle(draw, num_str, x, y, size=size, col=col)
    tx  = rx + 20
    f_t = font(34, bold=True)
    f_d = font(27)
    bb_t = f_t.getbbox(title)
    tth  = bb_t[3] - bb_t[1]
    draw.text((tx, cy - tth // 2 - bb_t[1] // 2), title, font=f_t, fill=DARK)
    dy = y + size + 10
    for desc in descs:
        dy = put_wrap(draw, desc, f_d, tx, dy, SUB_TEXT,
                      max_w=W - tx - MARGIN, gap=8) + 2
    draw.rectangle([x, dy + 8, W - MARGIN, dy + 10], fill=(195, 220, 240))
    return dy + 28

def warn_box(draw, text, y):
    f   = font(26)
    bb  = f.getbbox(text)
    bh  = (bb[3] - bb[1]) + 28
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + bh], radius=12,
                            fill=(255, 243, 240), outline=(200, 80, 80), width=2)
    draw.text((MARGIN + 18, y + 14 - bb[1]), text, font=f, fill=(175, 50, 50))
    return y + bh

def info_box(draw, text, y):
    f   = font(26)
    bb  = f.getbbox(text)
    bh  = (bb[3] - bb[1]) + 28
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + bh], radius=12,
                            fill=BL_BG, outline=BL_SKY, width=2)
    draw.text((MARGIN + 18, y + 14 - bb[1]), text, font=f, fill=BL_NAVY)
    return y + bh

# =============================================================
# 카드 1 — 표지
# =============================================================
def card01():
    PHOTO_H = 390
    img = make_canvas("cover", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 1); draw = ImageDraw.Draw(img)

    y = PHOTO_H + 32
    y = put(draw, "사업자등록만 하고 끝났나요?", font(66, bold=True), 0, y, DARK, align="center") + 8
    y = put(draw, "사업자통장 · 카드 개설 가이드", font(50, bold=True), 0, y, BL_NAVY, align="center") + 12
    tag = "공유오피스 · 가상오피스 입주 사업자 필독  |  개인사업자 · 법인"
    y = put(draw, tag, font(26), 0, y, BL_DEEP, align="center") + 20

    y = y + 4
    keywords = [("01", "통장개설", BL_NAVY),
                ("02", "카드발급", BL_MID),
                ("03", "홈택스 등록", BL_SKY)]
    kw_w = (W - MARGIN * 2 - 32) // 3
    for i, (num, kw, col) in enumerate(keywords):
        kx = MARGIN + i * (kw_w + 16)
        draw.rounded_rectangle([kx, y, kx + kw_w, y + 108],
                                radius=16, fill=BL_BG,
                                outline=(195, 220, 240), width=2)
        f_n = font(22, bold=True); nb = f_n.getbbox(num)
        nw  = draw.textlength(num, font=f_n)
        draw.text((kx + (kw_w - nw) / 2, y + 14 - nb[1]), num, font=f_n, fill=col)
        f_k = font(28, bold=True); kb = f_k.getbbox(kw)
        kw2 = draw.textlength(kw, font=f_k)
        draw.text((kx + (kw_w - kw2) / 2, y + 54 - kb[1]), kw, font=f_k, fill=DARK)
    y += 126

    divider(draw, y); y += 28

    desc = "사업자등록증만으로 끝이 아닙니다. 통장·카드를 어떻게 준비하느냐에 따라 이후 세무 처리가 훨씬 수월해집니다."
    y = put_wrap(draw, desc, font(30), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=12)
    y += 28

    lbl = "아래로 스와이프해서 확인하세요  v"
    f_s = font(28); bb = f_s.getbbox(lbl)
    lw  = draw.textlength(lbl, font=f_s)
    pw, ph = int(lw + 48), (bb[3] - bb[1]) + 28
    bx = (W - pw) // 2
    paste_grad_rounded(img, pw, ph, bx, y, radius=ph // 2)
    draw = ImageDraw.Draw(img)
    draw.text((bx + 24, y + 14 - bb[1]), lbl, font=f_s, fill=WHITE)

    bottom_branding(img, draw)
    img.save(os.path.join(OUTPUT, "bizaccount_01.jpg"), "JPEG", quality=95)
    print("bizaccount_01.jpg 저장")

# =============================================================
# 카드 2 — 사업자통장 개설
# =============================================================
def card02():
    PHOTO_H = 360
    img = make_canvas("account", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 2); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "ACCOUNT  |  사업자통장 개설", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "통장부터 만드세요", font(54, bold=True), MARGIN, y, DARK) + 14

    intro = "사업자등록증이 나온 뒤에 은행을 방문해야 개설이 됩니다. 준비서류를 미리 챙겨야 헛걸음을 막을 수 있습니다."
    y = put_wrap(draw, intro, font(29), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=11) + 14

    divider(draw, y); y += 22

    items = [
        (BL_NAVY, "01", "사업자등록증 발급이 먼저",
         ["사업자등록번호가 나오기 전에는 사업자통장 개설이 불가능합니다.",
          "세무서 방문 또는 홈택스에서 등록증을 먼저 발급받으세요."]),
        (BL_DEEP, "02", "방문 시 준비서류",
         ["사업자등록증, 대표자 신분증, 사업장 임대차계약서(또는 확인서류) 필요.",
          "업종에 따라 인허가증 등 추가서류를 요구하는 경우도 있습니다."]),
        (BL_MID, "03", "대포통장 방지로 심사 강화",
         ["최근 은행들이 개설 심사를 까다롭게 진행하는 추세입니다.",
          "사업 목적과 실체를 증빙할수록 개설이 원활합니다."]),
    ]
    for col, num, tit, descs in items:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col, size=68)

    bottom_branding(img, draw)
    img.save(os.path.join(OUTPUT, "bizaccount_02.jpg"), "JPEG", quality=95)
    print("bizaccount_02.jpg 저장")

# =============================================================
# 카드 3 — 사업자카드 발급
# =============================================================
def card03():
    PHOTO_H = 360
    img = make_canvas("card", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 3); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "CARD  |  사업자카드 발급", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "카드도 사업용으로 분리하세요", font(46, bold=True), MARGIN, y, DARK) + 14

    intro = "매출이 없는 창업 초기라도 발급 자체는 가능한 경우가 많습니다. 사업 목적에 맞게 카드를 선택하세요."
    y = put_wrap(draw, intro, font(28), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=10) + 18

    items = [
        (BL_NAVY, "04", "매출 없어도 발급 가능",
         ["신생 사업자는 사업장 매출 증빙이 어렵지만, 개인 신용도 기준으로 발급되는 경우가 많습니다.",
          "카드사·심사 기준에 따라 결과는 달라질 수 있습니다."]),
        (BL_DEEP, "05", "개인사업자 vs 법인카드",
         ["개인사업자는 개인 명의 카드를 사업용으로 등록해 사용합니다.",
          "법인은 법인 명의로 별도의 법인카드를 발급받아야 합니다."]),
        (BL_MID, "06", "카드사별 한도 · 혜택 비교",
         ["카드사와 상품에 따라 한도, 캐시백·포인트 혜택이 다릅니다.",
          "여러 상품을 비교한 뒤 사업 지출 패턴에 맞는 카드를 선택하세요."]),
    ]
    for col, num, tit, descs in items:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col, size=68)

    bottom_branding(img, draw)
    img.save(os.path.join(OUTPUT, "bizaccount_03.jpg"), "JPEG", quality=95)
    print("bizaccount_03.jpg 저장")

# =============================================================
# 카드 4 — 개설 후 꼭 할 일 (홈택스 등록)
# =============================================================
def card04():
    PHOTO_H = 330
    img = make_canvas("hometax", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 4); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "REGISTER  |  개설 후 꼭 할 일", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "이것도 놓치면 손해", font(54, bold=True), MARGIN, y, DARK) + 18

    items = [
        (BL_NAVY, "07", "홈택스 사업용계좌 등록",
         ["개설한 통장은 홈택스에 사업용 계좌로 등록해야 세금 신고 시 인정됩니다."]),
        (BL_DEEP, "08", "홈택스 사업용카드 등록",
         ["카드도 홈택스에 등록하면 최대 50개까지 등록 가능하며 사용 내역이 자동 수집됩니다.",
          "부가세 신고 시 매입세액 공제에 활용할 수 있습니다."]),
        (BL_MID, "09", "개인용 · 사업용 분리 사용",
         ["통장과 카드를 개인용과 분리해서 사용해야 경비 증빙과 세무 관리가 수월합니다."]),
    ]
    for col, num, tit, descs in items:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col, size=60)

    y += 4
    warn_box(draw, "주의: 사업용 계좌 미등록 시 가산세가 부과될 수 있습니다", y)

    bottom_branding(img, draw)
    img.save(os.path.join(OUTPUT, "bizaccount_04.jpg"), "JPEG", quality=95)
    print("bizaccount_04.jpg 저장")

# =============================================================
# 카드 5 — 준비서류 체크리스트 + CTA
# =============================================================
def card05():
    PHOTO_H = 480
    img = Image.new("RGB", (W, H), SKY_BG)
    img.paste(make_photo_header("cta", PHOTO_H, side_w=260, side_alpha=240), (0, 0))
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 5); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "CHECK  |  방문 전 준비 완료", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "은행 가기 전, 이것만 챙기세요", font(48, bold=True), MARGIN, y, DARK) + 24

    groups = [
        (BL_NAVY, "통장 개설",  "사업자등록증 · 대표자 신분증"),
        (BL_DEEP, "사업장 증빙", "임대차계약서 · 확인서류"),
        (BL_MID,  "카드 신청",  "신분증 · 사업자등록증"),
        (BL_NAVY, "법인 추가",  "법인등기부등본 · 법인인감"),
        (BL_DEEP, "홈택스",     "공동인증서 · 계좌 · 카드 정보"),
        (BL_MID,  "기타",       "도장 · 연락처 · 사업장 주소"),
    ]

    col_w  = (W - MARGIN * 2 - 20) // 2
    row_h  = 92
    gap    = 12
    f_cat  = font(23, bold=True)
    f_item = font(22)
    grid_y = y

    for i, (col, cat, items_text) in enumerate(groups):
        row = i // 2
        cidx = i % 2
        gx = MARGIN + cidx * (col_w + 20)
        gy = grid_y + row * (row_h + gap)
        draw.rounded_rectangle([gx, gy, gx + col_w, gy + row_h],
                                radius=14, fill=BL_BG,
                                outline=(195, 220, 240), width=2)
        draw.rectangle([gx, gy, gx + 6, gy + row_h], fill=col)
        bb_cat = f_cat.getbbox(cat)
        draw.text((gx + 18, gy + 14 - bb_cat[1]), cat, font=f_cat, fill=col)
        ity = gy + 14 + (bb_cat[3] - bb_cat[1]) + 8
        for line in wrap(draw, items_text, f_item, col_w - 24):
            ity = put(draw, line, f_item, gx + 18, ity, SUB_TEXT) + 4

    grid_rows = (len(groups) + 1) // 2
    y = grid_y + grid_rows * (row_h + gap) + 12

    divider(draw, y); y += 20

    y = info_box(draw, "사업자통장 개설: 사업자등록 후 은행 영업점 방문", y)
    y += 10
    y = info_box(draw, "등록 완료 후: 홈택스에서 사업용 계좌 · 카드 등록 필수", y)
    y += 28

    cta = "저장하고 개설 전에 확인하세요"
    f_c = font(30, bold=True); bb = f_c.getbbox(cta)
    cw  = draw.textlength(cta, font=f_c)
    bw, bh = int(cw + 56), (bb[3] - bb[1]) + 30
    bx  = (W - bw) // 2
    paste_grad_rounded(img, bw, bh, bx, y, radius=bh // 2)
    draw = ImageDraw.Draw(img)
    draw.text((bx + 28, y + 15 - bb[1]), cta, font=f_c, fill=WHITE)

    bottom_branding(img, draw)
    img.save(os.path.join(OUTPUT, "bizaccount_05.jpg"), "JPEG", quality=95)
    print("bizaccount_05.jpg 저장")

# ── 실행 ─────────────────────────────────────────────────────
card01(); card02(); card03(); card04(); card05()
print("\n완료! output_bizaccount 폴더에서 bizaccount_01~05.jpg 를 확인하세요.")
