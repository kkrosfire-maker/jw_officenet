from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import os, io, urllib.request

W, H = 1080, 1350
OUTPUT = r"C:\Users\JW\Desktop\workspace\cardnews\output"
os.makedirs(OUTPUT, exist_ok=True)

FONT_REG  = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
LOGO_PATH = r"C:\Users\JW\Desktop\정원유니어스\정원로고.png"

def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)

# ── 녹색 전용 팔레트 ─────────────────────────────────────
GN_FOREST = ( 24,  82,  48)   # 짙은 숲 초록
GN_DEEP   = ( 38, 110,  68)   # 짙은 초록
GN_MID    = ( 60, 138,  86)   # 중간 초록
GN_FERN   = ( 85, 155, 106)   # 고사리 초록
GN_SAGE   = (115, 172, 130)   # 세이지
GN_LIGHT  = (152, 198, 160)   # 연초록
GN_LIME   = (190, 225, 165)   # 밝은 연두 (어두운 배경 강조용)
GN_BG     = (232, 247, 234)   # 초록 배경 (카드 내부)
MINT_BG   = (244, 252, 245)   # 민트 크림 (전체 배경)
DARK      = ( 18,  44,  26)   # 텍스트 (짙은 초록)
SUB_TEXT  = ( 95, 120, 100)   # 보조 텍스트
WHITE     = (255, 255, 255)
MARGIN    = 64
COLS      = [GN_FOREST, GN_MID, GN_FERN]

# ── 그라디언트 (짙은 초록 → 밝은 연두) ──────────────────
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

def garden_grad(w, h):
    return make_gradient(w, h, [
        (0.00, GN_FOREST),
        (0.25, GN_DEEP),
        (0.52, GN_MID),
        (0.76, GN_SAGE),
        (1.00, (168, 212, 155)),
    ])

def paste_grad_rounded(img, gw, gh, dx, dy, radius):
    grad = garden_grad(gw, gh)
    mask = Image.new("L", (gw, gh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, gw, gh], radius=radius, fill=255)
    img.paste(grad, (dx, dy), mask=mask)

# ── 관련 사진 다운로드 (LoremFlickr 키워드 → picsum 폴백) ─
# lock= 값으로 항상 같은 사진 고정
PHOTO_URLS = {
    "cover":     ("https://loremflickr.com/1080/500/tax,finance,document?lock=101",
                  "https://picsum.photos/seed/tax-doc-2026/1080/500"),
    "deduction": ("https://loremflickr.com/1080/500/savings,money,piggybank?lock=202",
                  "https://picsum.photos/seed/savings-ira/1080/500"),
    "expense":   ("https://loremflickr.com/1080/500/receipt,invoice,accounting?lock=303",
                  "https://picsum.photos/seed/receipt-paper/1080/500"),
    "reduction": ("https://loremflickr.com/1080/500/calculator,accounting,office?lock=404",
                  "https://picsum.photos/seed/calc-desk/1080/500"),
    "cta":       ("https://loremflickr.com/1080/600/diary,pen,journal?lock=77",
                  "https://loremflickr.com/1080/600/notebook,pen,planner?lock=88"),
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
    print(f"  -> 그린 그라디언트 대체")
    return make_gradient(w, h, [
        (0.0, (28, 75, 45)), (0.5, (50, 120, 75)), (1.0, (80, 155, 100))
    ]).convert("RGB")

print("사진 다운로드 중...")
photos = {k: fetch_photo(k, W, 500) for k in PHOTO_URLS}
print("완료\n")

# ── 사진 → 민트 배경 페이드 ─────────────────────────────
def make_photo_header(key, photo_h=400, side_w=160, side_alpha=210):
    raw = photos[key].resize((W, photo_h), Image.LANCZOS)
    raw = raw.filter(ImageFilter.GaussianBlur(0.6))
    raw = ImageEnhance.Color(raw).enhance(0.75)
    # 붉은 채널 억제 → 녹색 계열로 보정
    r, g, b = raw.split()
    r = r.point(lambda x: int(x * 0.78))
    b = b.point(lambda x: int(x * 0.90))
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

    # 하단 민트 페이드
    fade_start = int(photo_h * 0.52)
    fm = Image.new("L", (1, photo_h), 0)
    fp = fm.load()
    for y in range(photo_h):
        if y >= fade_start:
            t = (y - fade_start) / (photo_h - fade_start)
            fp[0, y] = int(t ** 0.72 * 255)
    fm = fm.resize((W, photo_h))
    result.paste(Image.new("RGB", (W, photo_h), MINT_BG), (0, 0), mask=fm)

    # 좌우 사이드 녹색 그라디언트 오버레이
    sm = Image.new("L", (side_w, 1), 0)
    sm_px = sm.load()
    for x in range(side_w):
        t = x / max(side_w - 1, 1)
        sm_px[x, 0] = int((1 - t) ** 2.2 * side_alpha)
    sm = sm.resize((side_w, photo_h))
    green_side = garden_grad(side_w, photo_h)          # 짙은 → 밝은 초록 수직 그라디언트
    result.paste(green_side, (0, 0), mask=sm)
    result.paste(green_side, (W - side_w, 0), mask=sm.transpose(Image.FLIP_LEFT_RIGHT))

    return result

def make_canvas(key, photo_h=400):
    img = Image.new("RGB", (W, H), MINT_BG)
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
    draw.rectangle([MARGIN, H - 94, W - MARGIN, H - 92], fill=(170, 210, 175))

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
    draw.text((text_x, ty - bb[1]), "JUNGWON OFFICE NET", font=f_brand, fill=GN_FOREST)

    img.paste(garden_grad(W, 16), (0, H - 16))

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
    draw.rectangle([MARGIN, y, W - MARGIN, y + 2], fill=(185, 218, 190))
    return y + 2

def num_circle(draw, num_str, x, y, size=76, col=GN_FOREST):
    draw.ellipse([x, y, x + size, y + size], fill=col)
    f   = font(26, bold=True)
    bb  = f.getbbox(num_str)
    nw  = draw.textlength(num_str, font=f)
    nh  = bb[3] - bb[1]
    draw.text((x + (size - nw) / 2, y + (size - nh) / 2 - bb[1]),
              num_str, font=f, fill=WHITE)
    return x + size, y + size // 2

def bullet_block(draw, num_str, title, descs, x, y, col=GN_FOREST, size=76):
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
    draw.rectangle([x, dy + 8, W - MARGIN, dy + 10], fill=(185, 218, 190))
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
                            fill=GN_BG, outline=GN_SAGE, width=2)
    draw.text((MARGIN + 18, y + 14 - bb[1]), text, font=f, fill=GN_FOREST)
    return y + bh

# =============================================================
# 카드 1 — 표지
# =============================================================
def card01():
    PHOTO_H = 390
    img = make_canvas("cover", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 1); draw = ImageDraw.Draw(img)

    # 제목 — 사진 아래 크림 영역에 검정 계열로
    y = PHOTO_H + 32
    y = put(draw, "세금 더 내고 있지 않나요?", font(72, bold=True), 0, y, DARK, align="center") + 8
    y = put(draw, "종합소득세 절세 방법 10가지", font(50, bold=True), 0, y, GN_FOREST, align="center") + 12
    f_tag = font(26); bb_tag = f_tag.getbbox("가")
    tag = "2026년 5월 신고 전 필독  |  자영업자 · 프리랜서 · 임대소득자"
    y = put(draw, tag, f_tag, 0, y, GN_DEEP, align="center") + 20

    y = y + 4  # keywords 시작
    keywords = [("01", "공제 활용", GN_FOREST),
                ("02", "경비 처리", GN_MID),
                ("03", "세액 감면", GN_FERN)]
    kw_w = (W - MARGIN * 2 - 32) // 3
    for i, (num, kw, col) in enumerate(keywords):
        kx = MARGIN + i * (kw_w + 16)
        draw.rounded_rectangle([kx, y, kx + kw_w, y + 108],
                                radius=16, fill=GN_BG,
                                outline=(185, 218, 190), width=2)
        f_n = font(22, bold=True); nb = f_n.getbbox(num)
        nw  = draw.textlength(num, font=f_n)
        draw.text((kx + (kw_w - nw) / 2, y + 14 - nb[1]), num, font=f_n, fill=col)
        f_k = font(28, bold=True); kb = f_k.getbbox(kw)
        kw2 = draw.textlength(kw, font=f_k)
        draw.text((kx + (kw_w - kw2) / 2, y + 54 - kb[1]), kw, font=f_k, fill=DARK)
    y += 126

    divider(draw, y); y += 28

    desc = "납부 세액은 공제와 경비를 얼마나 챙기느냐에 따라 수백만 원이 달라집니다. 10가지 방법을 확인하고 절세 준비를 시작하세요."
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
    img.save(os.path.join(OUTPUT, "taxsave_01.jpg"), "JPEG", quality=95)
    print("taxsave_01.jpg 저장")

# =============================================================
# 카드 2 — 공제 최대 활용 (①~③)
# =============================================================
def card02():
    PHOTO_H = 360
    img = make_canvas("deduction", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 2); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "DEDUCTION  |  공제 최대 활용", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "공제부터 챙기세요", font(54, bold=True), MARGIN, y, DARK) + 14

    intro = "공제를 얼마나 챙기느냐에 따라 납부 세액이 수백만 원 차이납니다. 놓치기 쉬운 핵심 공제 세 가지를 확인하세요."
    y = put_wrap(draw, intro, font(29), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=11) + 14

    divider(draw, y); y += 22

    items = [
        (GN_FOREST, "01", "인적공제 최대한 활용",
         ["부양가족 1인당 연 150만 원 소득공제.",
          "경로우대(만 70세 이상) 100만 원, 장애인 200만 원 추가공제.",
          "배우자 · 부모 · 자녀 공제 요건 꼼꼼히 확인 필수."]),
        (GN_DEEP, "02", "노란우산공제 + IRP",
         # 소득별 한도: 4천만↓ 500만, 1억↓ 300만, 1억↑ 200만 (원본 정확 수치)
         ["노란우산공제 소득별 최대 200~500만 원 소득공제.",
          "연금저축 · IRP 합산 900만 원 납입 시 최대 148.5만 원 환급.",
          "세액공제율 16.5%(5,500만 이하) / 13.2%(초과) 적용."]),
        (GN_MID, "03", "기부금 세액공제",
         ["법정 · 지정기부금 15% 공제 (1천만 원 초과분은 30%).",
          "홈택스 자동 조회 안 되는 기부금은 직접 제출."]),
    ]
    for col, num, tit, descs in items:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col, size=68)

    bottom_branding(img, draw)
    img.save(os.path.join(OUTPUT, "taxsave_02.jpg"), "JPEG", quality=95)
    print("taxsave_02.jpg 저장")

# =============================================================
# 카드 3 — 누락 경비 찾기 (④~⑥)
# =============================================================
def card03():
    PHOTO_H = 360
    img = make_canvas("expense", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 3); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "EXPENSE  |  누락 경비 찾기", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "경비를 빠짐없이 잡아야 합니다", font(50, bold=True), MARGIN, y, DARK) + 14

    intro = "경비가 하나라도 빠지면 그만큼 과세 소득이 늘어 세금이 증가합니다. 지금 장부를 다시 펼쳐보세요."
    y = put_wrap(draw, intro, font(28), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=10) + 18

    items = [
        (GN_FOREST, "04", "누락 경비 체크",
         ["임대료 · 카드수수료 · 광고선전비 · 공과금 재확인.",
          "영수증 없어도 계좌이체 내역으로 입증 가능.",
          "사업 관련성이 증명되면 경비 인정."]),
        (GN_DEEP, "05", "업무용 차량 비용 처리",
         ["유류비 · 보험료 · 수리비 · 주차비 경비 인정.",
          "복식부기 대상자는 운행일지 작성 필수.",
          # 원본: "차량 명의가 본인 또는 법인이어야 인정" — hallucination 수정
          "차량 명의가 본인 또는 법인이어야 경비 처리 가능."]),
        (GN_MID, "06", "인건비 소급 신고",
         ["계좌이체로 지급한 인건비는 근로계약서 · 급여대장으로 처리.",
          "미신고 외국인 인건비도 사업용 계좌 지급 시 인정.",
          "늦게라도 신고하면 경비로 인정받을 수 있음."]),
    ]
    for col, num, tit, descs in items:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col, size=68)

    bottom_branding(img, draw)
    img.save(os.path.join(OUTPUT, "taxsave_03.jpg"), "JPEG", quality=95)
    print("taxsave_03.jpg 저장")

# =============================================================
# 카드 4 — 세액 절감 마무리 (⑦~⑩)
# =============================================================
def card04():
    PHOTO_H = 330
    img = make_canvas("reduction", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 4); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "TAX CUT  |  세액 절감 + 주의사항", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "이것도 놓치면 손해", font(54, bold=True), MARGIN, y, DARK) + 18

    items = [
        (GN_FOREST, "07", "경조비 한도 내 공제",
         ["건당 20만 원 이하: 청첩장 · 부고장으로 증빙.",
          "초과 시 카드영수증 필수 (중소기업 업무추진비 연 한도 3,600만 원)."]),
        (GN_DEEP, "08", "업무용 카드 홈택스 등록",
         ["최대 50개 카드 등록, 사용 내역 자동 수집.",
          "부가세 신고 시 10% 추가 공제 가능."]),
        (GN_MID, "09", "현금영수증 챙기기",
         ["불가피한 현금 사용 시 반드시 현금영수증 수취.",
          "카드 · 계좌이체 우선 사용으로 증빙 확보."]),
        (GN_FERN, "10", "중소기업 세액감면",
         ["수도권 소기업 · 중기업 10%, 수도권 외 소기업 최대 30%.",
          "감면 한도 1억 원."]),
    ]
    for col, num, tit, descs in items:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col, size=60)

    y += 4
    warn_box(draw, "주의: 무신고 시 가산세 20% + 납부지연 가산세(일 0.022%) 별도", y)

    bottom_branding(img, draw)
    img.save(os.path.join(OUTPUT, "taxsave_04.jpg"), "JPEG", quality=95)
    print("taxsave_04.jpg 저장")

# =============================================================
# 카드 5 — 필수 서류 체크리스트 + CTA
# =============================================================
def card05():
    PHOTO_H = 480
    # 좌우 확장 + 강한 녹색 그라디언트: side_w=260, side_alpha=240
    img = Image.new("RGB", (W, H), MINT_BG)
    img.paste(make_photo_header("cta", PHOTO_H, side_w=260, side_alpha=240), (0, 0))
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 5); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "CHECK  |  신고 준비 완료", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "5월 신고 전, 이것만 준비하세요", font(50, bold=True), MARGIN, y, DARK) + 24

    groups = [
        (GN_FOREST, "소득 관련",  "원천징수영수증 · 임대소득 내역"),
        (GN_DEEP,   "공제 관련",  "공제 납입확인서"),
        (GN_MID,    "경비 관련",  "세금계산서 · 카드 영수증 · 계약서"),
        (GN_FOREST, "인건비",     "근로계약서 · 급여대장"),
        (GN_DEEP,   "차량",       "운행일지 · 주유 영수증"),
        (GN_MID,    "기부금",     "기부금 영수증"),
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
                                radius=14, fill=GN_BG,
                                outline=(185, 218, 190), width=2)
        draw.rectangle([gx, gy, gx + 6, gy + row_h], fill=col)
        bb_cat = f_cat.getbbox(cat)
        draw.text((gx + 18, gy + 14 - bb_cat[1]), cat, font=f_cat, fill=col)
        ity = gy + 14 + (bb_cat[3] - bb_cat[1]) + 8
        for line in wrap(draw, items_text, f_item, col_w - 24):
            ity = put(draw, line, f_item, gx + 18, ity, SUB_TEXT) + 4

    grid_rows = (len(groups) + 1) // 2
    y = grid_y + grid_rows * (row_h + gap) + 12

    divider(draw, y); y += 20

    y = info_box(draw, "신고 기간: 2026년 5월 1일 ~ 5월 31일", y)
    y += 10
    y = info_box(draw, "환급금: 신고 후 30일 이내 (6월 말 ~ 7월 초 입금)", y)
    y += 28

    cta = "저장하고 주변 사장님과 공유하세요"
    f_c = font(30, bold=True); bb = f_c.getbbox(cta)
    cw  = draw.textlength(cta, font=f_c)
    bw, bh = int(cw + 56), (bb[3] - bb[1]) + 30
    bx  = (W - bw) // 2
    paste_grad_rounded(img, bw, bh, bx, y, radius=bh // 2)
    draw = ImageDraw.Draw(img)
    draw.text((bx + 28, y + 15 - bb[1]), cta, font=f_c, fill=WHITE)

    bottom_branding(img, draw)
    img.save(os.path.join(OUTPUT, "taxsave_05.jpg"), "JPEG", quality=95)
    print("taxsave_05.jpg 저장")

# ── 실행 ─────────────────────────────────────────────────────
card01(); card02(); card03(); card04(); card05()
print("\n완료! output 폴더에서 taxsave_01~05.jpg 를 확인하세요.")
