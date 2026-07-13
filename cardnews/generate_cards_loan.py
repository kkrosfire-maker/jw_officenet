from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import os, io, urllib.request

W, H = 1080, 1350
OUTPUT = r"C:\Users\JW\Desktop\workspace\cardnews\output_loan"
os.makedirs(OUTPUT, exist_ok=True)

FONT_REG  = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"

def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)

# ── 색상 ─────────────────────────────────────────────────
IG_PURPLE = (131,  58, 180)
IG_PINK   = (193,  53, 132)
IG_RED    = (225,  48, 108)
IG_ORANGE = (247, 119,  55)
IG_YELLOW = (252, 175,  69)
WHITE     = (255, 255, 255)
DARK      = ( 18,  18,  20)
MID_GRAY  = (130, 130, 145)
MARGIN    = 64
COLS      = [IG_PURPLE, IG_RED, IG_ORANGE]

# ── 그라디언트 ───────────────────────────────────────────
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

def ig_grad(w, h):
    return make_gradient(w, h, [
        (0.0, IG_PURPLE), (0.3, IG_PINK),
        (0.6, IG_RED), (0.85, IG_ORANGE), (1.0, IG_YELLOW),
    ])

def paste_grad_rounded(img, gw, gh, dx, dy, radius):
    grad = ig_grad(gw, gh)
    mask = Image.new("L", (gw, gh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, gw, gh], radius=radius, fill=255)
    img.paste(grad, (dx, dy), mask=mask)

# ── 사진 다운로드 ─────────────────────────────────────────
PHOTO_SEEDS = {
    "cover":    "banking-money",
    "impact":   "small-business-owner",
    "cause":    "financial-regulation",
    "action":   "bank-planning",
    "alt":      "government-loan",
    "check":    "personal-finance",
    "strategy": "multichannel",
}

def fetch_photo(seed, w, h):
    url = f"https://picsum.photos/seed/{seed}/{w}/{h}"
    print(f"  다운로드: {url}")
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return Image.open(io.BytesIO(r.read())).convert("RGB")
    except Exception as e:
        print(f"  실패({e}) → 단색 대체")
        return Image.new("RGB", (w, h), (80, 80, 100))

print("사진 다운로드 중...")
photos = {k: fetch_photo(v, W, 500) for k, v in PHOTO_SEEDS.items()}
print("완료\n")

# ── 사진 → 흰 배경 페이드 ────────────────────────────────
def make_photo_header(key, photo_h=400):
    raw = photos[key].resize((W, photo_h), Image.LANCZOS)
    raw = raw.filter(ImageFilter.GaussianBlur(0.8))
    raw = ImageEnhance.Color(raw).enhance(0.85)
    result = raw.copy()

    dark_h = photo_h // 2
    dm = Image.new("L", (1, photo_h), 0)
    dp = dm.load()
    for y in range(dark_h):
        dp[0, y] = int((1 - y / dark_h) * 140)
    dm = dm.resize((W, photo_h))
    result.paste(Image.new("RGB", (W, photo_h), (0, 0, 0)), (0, 0), mask=dm)

    fade_start = int(photo_h * 0.55)
    fm = Image.new("L", (1, photo_h), 0)
    fp = fm.load()
    for y in range(photo_h):
        if y >= fade_start:
            t = (y - fade_start) / (photo_h - fade_start)
            fp[0, y] = int(t ** 0.75 * 255)
    fm = fm.resize((W, photo_h))
    result.paste(Image.new("RGB", (W, photo_h), WHITE), (0, 0), mask=fm)
    return result

def make_canvas(key, photo_h=400):
    img = Image.new("RGB", (W, H), WHITE)
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
    words = list(text)
    lines, cur = [], ""
    for ch in text.split():
        test = (cur + " " + ch).strip()
        if draw.textlength(test, font=f) <= max_w:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = ch
    if cur: lines.append(cur)
    return lines

def put_wrap(draw, text, f, x, y, fill, max_w, gap=10):
    for line in wrap(draw, text, f, max_w):
        y = put(draw, line, f, x, y, fill) + gap
    return y

def th(f, text="가"):
    bb = f.getbbox(text)
    return bb[3] - bb[1]

# ── 공통 UI ──────────────────────────────────────────────
def bottom_bar(img):
    img.paste(ig_grad(W, 8), (0, H - 8))

def card_num(img, draw, n, total=7):
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

def source_line(draw):
    draw.text((MARGIN, H - 54),
              "참고  |  nocutnews.co.kr · insight.co.kr · newspim.com",
              font=font(22), fill=MID_GRAY)

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

def section_badge(draw, text, x, y, col):
    f   = font(26, bold=True)
    bb  = f.getbbox(text)
    lh  = bb[3] - bb[1]
    lw  = draw.textlength(text, font=f)
    bw  = int(lw + 32); bh = lh + 18
    draw.rounded_rectangle([x, y, x + bw, y + bh], radius=8, fill=col)
    draw.text((x + 16, y + 9 - bb[1]), text, font=f, fill=WHITE)
    return bh

def divider(draw, y):
    draw.rectangle([MARGIN, y, W - MARGIN, y + 2], fill=(218, 218, 228))
    return y + 2

def num_circle(draw, num_str, x, y, size=76, col=IG_PURPLE):
    draw.ellipse([x, y, x + size, y + size], fill=col)
    f   = font(26, bold=True)
    bb  = f.getbbox(num_str)
    nw  = draw.textlength(num_str, font=f)
    nh  = bb[3] - bb[1]
    draw.text((x + (size - nw) / 2, y + (size - nh) / 2 - bb[1]),
              num_str, font=f, fill=WHITE)
    return x + size, y + size // 2

def bullet_block(draw, num_str, title, descs, x, y, col=IG_PURPLE, size=76):
    rx, cy = num_circle(draw, num_str, x, y, size=size, col=col)
    tx  = rx + 20
    f_t = font(34, bold=True)
    f_d = font(27)
    bb_t = f_t.getbbox(title)
    tth  = bb_t[3] - bb_t[1]
    draw.text((tx, cy - tth // 2 - bb_t[1] // 2), title, font=f_t, fill=DARK)
    dy = y + size + 10
    for desc in descs:
        dy = put_wrap(draw, desc, f_d, tx, dy, MID_GRAY,
                      max_w=W - tx - MARGIN, gap=8) + 2
    draw.rectangle([x, dy + 8, W - MARGIN, dy + 10], fill=(220, 220, 228))
    return dy + 28

def warn_box(draw, text, y, fg=(190, 40, 40), bg=(255, 242, 242), border=(210, 60, 60)):
    f   = font(26)
    bb  = f.getbbox(text)
    bh  = (bb[3] - bb[1]) + 24
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + bh], radius=12,
                            fill=bg, outline=border, width=2)
    draw.text((MARGIN + 18, y + 12 - bb[1]), text, font=f, fill=fg)
    return y + bh

def info_box(draw, text, y, fg=(30, 100, 180), bg=(240, 248, 255), border=(80, 150, 220)):
    f   = font(26)
    bb  = f.getbbox(text)
    bh  = (bb[3] - bb[1]) + 24
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + bh], radius=12,
                            fill=bg, outline=border, width=2)
    draw.text((MARGIN + 18, y + 12 - bb[1]), text, font=f, fill=fg)
    return y + bh

# ═══════════════════════════════════════════════════════════
# 카드 1 — 표지
# ═══════════════════════════════════════════════════════════
def card01():
    PHOTO_H = 560
    img = make_canvas("cover", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 1); draw = ImageDraw.Draw(img)

    y = 160
    y = put(draw, "사장님,", font(86, bold=True), 0, y, WHITE, align="center") + 8
    y = put(draw, "마이너스통장 한도가", font(70, bold=True), 0, y, WHITE, align="center") + 8
    y = put(draw, "반토막 납니다", font(70, bold=True), 0, y, IG_YELLOW, align="center") + 14
    put(draw, "2억 4천만 → 1억원, 지금 바로 확인하세요", font(30), 0, y, WHITE, align="center")

    y = PHOTO_H + 32
    keywords = [("01", "영향 파악", IG_PURPLE),
                ("02", "즉시 대처", IG_RED),
                ("03", "대안 마련", IG_ORANGE)]
    kw_w = (W - MARGIN * 2 - 32) // 3
    for i, (num, kw, col) in enumerate(keywords):
        kx = MARGIN + i * (kw_w + 16)
        draw.rounded_rectangle([kx, y, kx + kw_w, y + 108],
                                radius=16, fill=(248, 248, 252),
                                outline=(225, 225, 235), width=2)
        f_n = font(22, bold=True); nb = f_n.getbbox(num)
        nw  = draw.textlength(num, font=f_n)
        draw.text((kx + (kw_w - nw) / 2, y + 14 - nb[1]), num, font=f_n, fill=col)
        f_k = font(28, bold=True); kb = f_k.getbbox(kw)
        kw2 = draw.textlength(kw, font=f_k)
        draw.text((kx + (kw_w - kw2) / 2, y + 54 - kb[1]), kw, font=f_k, fill=DARK)
    y += 126

    divider(draw, y); y += 28

    desc = "카카오뱅크가 6월 22일부터 마이너스통장 최대 한도를 1억원으로 줄입니다. 운영자금을 마이너스통장으로 쓰는 개인사업자라면 지금 당장 확인이 필요합니다."
    y = put_wrap(draw, desc, font(30), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=12)
    y += 28

    lbl = "아래로 스와이프해서 확인하세요  ↓"
    f_s = font(28); bb = f_s.getbbox(lbl)
    lw  = draw.textlength(lbl, font=f_s)
    lh  = bb[3] - bb[1]
    pw, ph = int(lw + 48), lh + 28
    bx = (W - pw) // 2
    paste_grad_rounded(img, pw, ph, bx, y, radius=ph // 2)
    draw = ImageDraw.Draw(img)
    draw.text((bx + 24, y + 14 - bb[1]), lbl, font=f_s, fill=WHITE)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_01.jpg"), "JPEG", quality=95)
    print("card_01.jpg 저장")

# ═══════════════════════════════════════════════════════════
# 카드 2 — 무슨 일인가
# ═══════════════════════════════════════════════════════════
def card02():
    PHOTO_H = 380
    img = make_canvas("impact", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 2); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "ISSUE  |  무슨 일이 생겼나", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "2억 4천이 1억으로 줄었습니다", font(50, bold=True), MARGIN, y, DARK) + 14

    intro = "카카오뱅크가 6월 22일부터 마이너스통장(한도 대출) 최대 한도를 기존 2억 4천만 원에서 1억 원으로 대폭 낮춥니다. 시중은행에 이어 인터넷은행까지 신용대출 조이기에 나선 겁니다."
    y = put_wrap(draw, intro, font(29), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=11) + 14

    divider(draw, y); y += 22
    section_badge(draw, "변경 내용 한눈에 보기", MARGIN, y, IG_PURPLE)
    y += th(font(26)) + 18 + 18

    items = [
        (IG_PURPLE, "01", "신규 한도 즉시 적용 (6/22~)",
         ["카카오뱅크 마이너스통장 신규 신청 시 최대 1억원.",
          "기존 2억 4천만원 한도는 더 이상 받을 수 없음.",
          "이미 받은 분도 7월 연장 시 한도 감액 심사 대상."]),
        (IG_RED,    "02", "기존 고객 7월부터 연장 심사",
         ["5천만원 이상 마이너스통장 중 사용률 20% 이하면",
          "연장 시 한도 최대 20% 자동 감액 가능.",
          "한도를 평소에 많이 쓰지 않는 계좌가 먼저 대상."]),
        (IG_ORANGE, "03", "은행권 전체 흐름",
         ["금융당국이 신용대출 총량 관리 강화를 주문한 결과.",
          "시중은행(KB·신한·하나)은 이미 수개월 전 한도 축소.",
          "인터넷은행·핀테크 대출 중개 플랫폼까지 연쇄 적용 중."]),
    ]
    for col, num, tit, descs in items:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col, size=68)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_02.jpg"), "JPEG", quality=95)
    print("card_02.jpg 저장")

# ═══════════════════════════════════════════════════════════
# 카드 3 — 개인사업자에게 미치는 영향
# ═══════════════════════════════════════════════════════════
def card03():
    PHOTO_H = 360
    img = make_canvas("cause", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 3); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "IMPACT  |  사장님 입장", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "운영자금 줄면 사업이 흔들립니다", font(48, bold=True), MARGIN, y, DARK) + 14

    intro = "마이너스통장은 많은 개인사업자에게 '비상금 창고'입니다. 세금 납부, 급여 지급, 재고 구매 등 현금이 필요한 순간마다 꺼내 쓰는 자금줄인데 이게 막히면 직격탄입니다."
    y = put_wrap(draw, intro, font(28), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=10) + 18

    impacts = [
        (IG_PURPLE, "01", "부가세·종합소득세 납부 위기",
         ["세금은 예고 없이 수천만 원이 한 번에 나감.",
          "마이너스통장으로 단기 충당 후 갚는 패턴이 많음.",
          "한도가 줄면 납부 시 현금 부족 사태 발생 가능."]),
        (IG_RED,    "02", "재고·원자재 구매 타격",
         ["성수기 전 대량 매입이 필요한 사업자 직격.",
          "공급업체 선결제 요구 시 현금 조달이 안 되면 발주 차질.",
          "매출 기회 자체를 잃는 연쇄 피해로 이어질 수 있음."]),
        (IG_ORANGE, "03", "직원 급여·임대료 지급 압박",
         ["매출 입금 지연과 지출 시점 불일치를 메워주던 완충재가 사라짐.",
          "소액 한도로는 한 달 운영비 커버도 빠듯할 수 있음.",
          "신용점수 높아도 한도 상한선이 묶여 있어 해결이 안 됨."]),
    ]
    for col, num, tit, descs in impacts:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_03.jpg"), "JPEG", quality=95)
    print("card_03.jpg 저장")

# ═══════════════════════════════════════════════════════════
# 카드 4 — 지금 당장 할 것
# ═══════════════════════════════════════════════════════════
def card04():
    PHOTO_H = 360
    img = make_canvas("action", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 4); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "ACTION  |  지금 당장 할 것", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "6월 22일 전에 움직이세요", font(54, bold=True), MARGIN, y, DARK) + 14

    intro = "한도 변경 시행일(6/22)이 얼마 남지 않았습니다. 그 전에 할 수 있는 것과 이미 계좌가 있는 분이 챙겨야 할 것을 정리했습니다."
    y = put_wrap(draw, intro, font(28), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=10) + 14

    y = warn_box(draw, "⚠  기존 연장 계좌도 7월부터 사용률 낮으면 한도 감액 심사", y)
    y += 20

    steps = [
        (IG_PURPLE, "01", "한도 아직 없다면 22일 전 신청",
         ["카카오뱅크 기준 현재 최대 2.4억까지 신청 가능.",
          "22일 이후에는 상한이 1억으로 묶임.",
          "지금 당장 필요하지 않아도 한도는 미리 확보해두는 것이 유리."]),
        (IG_RED,    "02", "기존 계좌 사용률 30% 이상 유지",
         ["7월 연장 시 한도 감액 기준은 '6개월 사용률 20% 이하'.",
          "잔액을 조금이라도 써두면 감액 심사 대상에서 제외 가능.",
          "이번 달 안에 소액이라도 인출 후 상환하는 방법도 유효."]),
        (IG_ORANGE, "03", "다른 은행 마이너스통장 병행 개설 검토",
         ["한 곳에만 의존하지 말고 2~3곳에 소액 한도 분산 확보.",
          "케이뱅크·토스뱅크·시중은행 한도 비교 후 보조 계좌 마련.",
          "이자는 쓴 금액에만 발생하므로 유지 비용은 거의 없음."]),
    ]
    for col, num, tit, descs in steps:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_04.jpg"), "JPEG", quality=95)
    print("card_04.jpg 저장")

# ═══════════════════════════════════════════════════════════
# 카드 5 — 대안 자금 조달
# ═══════════════════════════════════════════════════════════
def card05():
    PHOTO_H = 360
    img = make_canvas("alt", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 5); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "ALTERNATIVE  |  대안 자금 루트", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "마이너스통장 줄었다면 여기 써보세요", font(44, bold=True), MARGIN, y, DARK) + 14

    intro = "마이너스통장 한도가 부족해진다면 개인사업자가 활용할 수 있는 정책자금과 보완 수단이 있습니다. 금리 조건도 시중보다 유리한 경우가 많습니다."
    y = put_wrap(draw, intro, font(28), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=10) + 16

    good = "✅  정책자금은 신용점수와 무관하게 사업 실적으로 심사"
    f_g = font(26, bold=True); bb = f_g.getbbox(good)
    bh_g = (bb[3] - bb[1]) + 24
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + bh_g], radius=12,
                            fill=(240, 255, 245), outline=(60, 180, 100), width=2)
    draw.text((MARGIN + 18, y + 12 - bb[1]), good, font=f_g, fill=(30, 140, 70))
    y += bh_g + 24

    alts = [
        (IG_PURPLE, "01", "소진공 소상공인 정책자금",
         ["소상공인시장진흥공단: 연 2~3%대 저금리 운영자금 대출.",
          "창업 7년 이내 또는 매출 10억 이하 소상공인 신청 가능.",
          "소진공 홈페이지(sbiz.or.kr) → 정책자금 → 직접대출 신청."]),
        (IG_RED,    "02", "IBK·기업은행 개인사업자 대출",
         ["사업자 등록증 기반 운영자금 대출 상품 다수 보유.",
          "마이너스통장보다 한도는 크고 금리는 비슷하거나 낮음.",
          "세금계산서·카드매출 내역만 있으면 심사 가능."]),
        (IG_ORANGE, "03", "카드 매출 연동 대출 (핀다·카카오 등)",
         ["카드 단말기 매출 실적 기반으로 한도 책정하는 상품.",
          "신용점수 낮아도 매출이 있으면 대출 가능.",
          "핀다·토스·카카오페이에서 한 번에 비교 후 신청."]),
    ]
    for col, num, tit, descs in alts:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_05.jpg"), "JPEG", quality=95)
    print("card_05.jpg 저장")

# ═══════════════════════════════════════════════════════════
# 카드 6 — 꼭 확인할 것들
# ═══════════════════════════════════════════════════════════
def card06():
    PHOTO_H = 360
    img = make_canvas("check", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 6); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "CHECK  |  놓치면 손해인 것들", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "지금 바로 체크하세요", font(56, bold=True), MARGIN, y, DARK) + 28

    checks = [
        (IG_PURPLE, "01", "내 마이너스통장 연장일 확인",
         ["카카오뱅크 앱 → 대출 → 한도대출 → 만기일 확인.",
          "7월 이후 연장 예정이라면 지금 사용 이력 만들어두기.",
          "연장일이 9월 이후라면 여유 있음 — 그래도 미리 확인."]),
        (IG_RED,    "02", "다른 은행 한도도 점검",
         ["카카오뱅크뿐 아니라 보유한 모든 마이너스통장 한도 확인.",
          "시중은행도 이미 축소 흐름 — 연장 시 한도 줄어들 수 있음.",
          "총 가용 한도 = 실제 운영자금 여유로 환산해 파악하기."]),
        (IG_ORANGE, "03", "세금 납부 일정 미리 계산",
         ["부가세: 7월 25일 / 종소세: 5월 (이미 지남) / 원천세: 매월 10일.",
          "7월 부가세 시즌까지 마이너스통장 한도 충분한지 지금 계산.",
          "부족할 것 같으면 지금 정책자금 신청이 최선."]),
    ]
    for col, num, tit, descs in checks:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_06.jpg"), "JPEG", quality=95)
    print("card_06.jpg 저장")

# ═══════════════════════════════════════════════════════════
# 카드 7 — 요약 & CTA
# ═══════════════════════════════════════════════════════════
def card07():
    PHOTO_H = 360
    img = make_canvas("strategy", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 7); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "SUMMARY  |  핵심 요약", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "오늘 당장 해야 할 3가지", font(56, bold=True), MARGIN, y, DARK) + 20

    divider(draw, y); y += 28

    summary_items = [
        "6/22 전 카카오뱅크 한도 아직 없으면 지금 신청",
        "기존 마이너스통장 사용률 30% 이상으로 올려두기",
        "7월 부가세 납부용 정책자금 사전 알아보기",
    ]
    f_s = font(30, bold=True)
    for i, s in enumerate(summary_items):
        bb = f_s.getbbox(s); sh = 56
        cx, cy = MARGIN, y
        draw.ellipse([cx, cy, cx + sh, cy + sh], fill=COLS[i])
        f_n = font(22, bold=True)
        nb = f_n.getbbox(str(i + 1))
        nw2 = draw.textlength(str(i + 1), font=f_n)
        draw.text((cx + (sh - nw2) / 2, cy + (sh - (nb[3] - nb[1])) / 2 - nb[1]),
                  str(i + 1), font=f_n, fill=WHITE)
        tx = cx + sh + 18
        y2 = cy + (sh - (bb[3] - bb[1])) // 2
        put_wrap(draw, s, f_s, tx, y2, DARK, max_w=W - tx - MARGIN, gap=6)
        y += sh + 24

    y += 16
    divider(draw, y); y += 28

    intro2 = "마이너스통장 한도는 '있을 때 확보'가 원칙입니다. 사업 운영에 여유가 있을 때 미리 손 써두는 것이 가장 현명한 대비입니다."
    y = put_wrap(draw, intro2, font(28), MARGIN, y, MID_GRAY, max_w=W - MARGIN * 2, gap=10)
    y += 24

    cta = "저장하고 동료 사장님들과 공유하세요"
    f_c = font(30, bold=True); bb = f_c.getbbox(cta)
    cw  = draw.textlength(cta, font=f_c); ch = bb[3] - bb[1]
    bw, bh = int(cw + 56), ch + 30
    bx  = (W - bw) // 2
    paste_grad_rounded(img, bw, bh, bx, y, radius=bh // 2)
    draw = ImageDraw.Draw(img)
    draw.text((bx + 28, y + 15 - bb[1]), cta, font=f_c, fill=WHITE)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_07.jpg"), "JPEG", quality=95)
    print("card_07.jpg 저장")

# ── 실행 ─────────────────────────────────────────────────
card01(); card02(); card03(); card04()
card05(); card06(); card07()
print("\n완료! output_loan 폴더를 확인하세요.")
