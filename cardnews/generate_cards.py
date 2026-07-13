from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import os, io, urllib.request

W, H = 1080, 1350
OUTPUT = r"C:\Users\JW\Desktop\workspace\cardnews\output"
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
    "cover":    "business-phone",
    "impact":   "small-business",
    "cause":    "entrepreneur",
    "recovery": "office-mobile",
    "ban":      "crisis-business",
    "prevent":  "workspace-safe",
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

    # 상단 어두운 오버레이 (텍스트 가독성)
    dark_h = photo_h // 2
    dm = Image.new("L", (1, photo_h), 0)
    dp = dm.load()
    for y in range(dark_h):
        dp[0, y] = int((1 - y / dark_h) * 140)
    dm = dm.resize((W, photo_h))
    result.paste(Image.new("RGB", (W, photo_h), (0, 0, 0)), (0, 0), mask=dm)

    # 하단 흰색 페이드
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
              "참고 ㅣ i-boss.co.kr · polarad.co.kr · nocutnews.co.kr",
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

# ═══════════════════════════════════════════════════════════
# 카드 1 — 표지
# ═══════════════════════════════════════════════════════════
def card01():
    PHOTO_H = 560
    img = make_canvas("cover", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 1); draw = ImageDraw.Draw(img)

    # 로고
    def ig_logo(cx, cy, r):
        b = r * 0.72
        draw.rounded_rectangle([cx-b, cy-b, cx+b, cy+b],
                                radius=r*0.28, outline=WHITE, width=int(r*0.09))
        draw.ellipse([cx-r*0.44, cy-r*0.44, cx+r*0.44, cy+r*0.44],
                     outline=WHITE, width=int(r*0.09))
        dr = r * 0.1
        draw.ellipse([cx+b*0.45-dr, cy-b*0.55-dr,
                      cx+b*0.45+dr, cy-b*0.55+dr], fill=WHITE)
    ig_logo(W // 2, 100, 60)

    # 타이틀 (사진 위)
    y = 210
    y = put(draw, "사장님,", font(86, bold=True), 0, y, WHITE, align="center") + 6
    y = put(draw, "인스타 계정 차단되면", font(72, bold=True), 0, y, WHITE, align="center") + 6
    y = put(draw, "매출이 멈춥니다", font(72, bold=True), 0, y, IG_YELLOW, align="center") + 12
    put(draw, "2026 대숙청, 개인사업자 대처 완벽 가이드", font(30), 0, y, WHITE, align="center")

    # 흰 영역 — 키워드 요약
    y = PHOTO_H + 32
    keywords = [("01", "영향 파악", IG_PURPLE),
                ("02", "빠른 복구", IG_RED),
                ("03", "재발 방지", IG_ORANGE)]
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

    desc = "인스타그램을 주요 마케팅 채널로 쓰는 개인사업자라면 반드시 알아야 할 내용입니다. 갑자기 찾아오는 계정 차단, 미리 준비하면 피해를 최소화할 수 있습니다."
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
# 카드 2 — 개인사업자에게 미치는 영향
# ═══════════════════════════════════════════════════════════
def card02():
    PHOTO_H = 380
    img = make_canvas("impact", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 2); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "IMPACT  |  개인사업자 영향", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "차단 한 번에 매출이 끊깁니다", font(52, bold=True), MARGIN, y, DARK) + 14

    intro = "국내 소상공인·개인사업자의 상당수가 인스타그램을 주요 매출 채널로 활용하고 있습니다. 계정이 차단되는 순간 홍보·문의·예약이 모두 멈춥니다."
    y = put_wrap(draw, intro, font(29), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=11) + 14

    divider(draw, y); y += 22
    section_badge(draw, "구체적으로 어떤 피해가 생기나요?", MARGIN, y, IG_PURPLE)
    y += th(font(26)) + 18 + 18

    impacts = [
        (IG_PURPLE, "01", "신규 고객 유입 완전 차단",
         ["팔로워에게 게시물·스토리가 노출되지 않아 홍보 불가.",
          "인스타 검색·해시태그로 오던 신규 고객 유입이 0으로.",
          "광고를 집행 중이었다면 광고비만 소진되고 효과는 없음."]),
        (IG_RED,    "02", "기존 고객과의 소통 단절",
         ["DM 문의·예약·주문 응대가 모두 불가능해짐.",
          "상품 링크·쇼핑 기능도 함께 중단돼 즉각적인 매출 손실.",
          "재구매 고객이 연락처를 잃어 이탈로 이어질 수 있음."]),
        (IG_ORANGE, "03", "브랜드 신뢰도 하락",
         ["계정이 갑자기 사라지면 고객이 폐업으로 오인할 수 있음.",
          "복구에 수일~수주 소요 → 그 기간 동안 경쟁자에게 고객 이탈.",
          "재개설 시 팔로워·리뷰 등 쌓아온 자산 처음부터 재시작."]),
    ]
    for col, num, tit, descs in impacts:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col, size=68)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_02.jpg"), "JPEG", quality=95)
    print("card_02.jpg 저장")

# ═══════════════════════════════════════════════════════════
# 카드 3 — 개인사업자가 모르고 하는 차단 유발 행동
# ═══════════════════════════════════════════════════════════
def card03():
    PHOTO_H = 360
    img = make_canvas("cause", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 3); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "CAUSE  |  차단 유발 행동", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "나도 모르게 하고 있던 위험 행동", font(50, bold=True), MARGIN, y, DARK) + 14

    intro = "개인사업자들이 홍보 효율을 높이려다 오히려 계정을 잃는 패턴이 반복되고 있습니다. 아래 항목 중 해당 사항이 있는지 지금 바로 점검해 보세요."
    y = put_wrap(draw, intro, font(28), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=10) + 18

    causes = [
        (IG_PURPLE, "01", "비공식 팔로워·좋아요 구매",
         ["팔로워 증대 서비스, 자동 좋아요 앱 사용 시 즉시 차단 대상.",
          "Meta 미등록 제3자 앱에 계정 권한을 준 것만으로도 위험.",
          "팔로워 수보다 계정 안전이 먼저입니다."]),
        (IG_RED,    "02", "단시간 과도한 반복 활동",
         ["짧은 시간에 대량의 팔로우·좋아요·댓글을 반복하면 봇으로 의심.",
          "동일 문구 DM을 여러 계정에 동시 발송하는 것도 차단 원인.",
          "사람이 물리적으로 불가능한 속도의 활동은 AI가 즉시 감지."]),
        (IG_ORANGE, "03", "VPN 사용 및 잦은 기기 변경",
         ["VPN으로 IP가 자주 바뀌면 '해킹 의심'으로 계정 잠금 처리.",
          "여러 직원이 동시에 같은 계정에 다른 기기로 접속 시 위험.",
          "해외에서 갑자기 접속하거나 접속 국가가 바뀌어도 차단 대상."]),
    ]
    for col, num, tit, descs in causes:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_03.jpg"), "JPEG", quality=95)
    print("card_03.jpg 저장")

# ═══════════════════════════════════════════════════════════
# 카드 4 — 차단됐을 때 빠른 대처법
# ═══════════════════════════════════════════════════════════
def card04():
    PHOTO_H = 360
    img = make_canvas("recovery", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 4); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "RECOVERY  |  차단 후 대처", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "차단됐다면 지금 당장 이렇게", font(50, bold=True), MARGIN, y, DARK) + 14

    intro = "계정 문제는 시간이 지체될수록 복구 확률이 낮아집니다. 차단을 발견한 즉시 아래 순서대로 빠르게 대응하세요."
    y = put_wrap(draw, intro, font(28), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=10) + 16

    y = warn_box(draw, "⚠  신분증 인증은 2회 제한 — 실패 시 영구 정지 전환", y)
    y += 20

    steps = [
        (IG_PURPLE, "01", "즉시 모든 기기에서 로그아웃",
         ["모든 기기에서 로그아웃 후 24~48시간 활동 완전 중단.",
          "'저희의 실수라고 생각하신다면 알려주세요' 버튼이 보이면 즉시 클릭.",
          "이것이 AI 오탐을 사람이 재검토하게 하는 가장 빠른 방법."]),
        (IG_RED,    "02", "연결된 제3자 앱 즉시 차단",
         ["설정 > 앱 및 웹사이트에서 불필요한 외부 앱 연결 해제.",
          "비공식 팔로워·자동화 앱이 연결돼 있으면 즉시 삭제.",
          "비밀번호 변경 및 2단계 인증 설정 필수."]),
        (IG_ORANGE, "03", "Meta 공식 채널로 이의 신청",
         ["Meta Business Suite의 '계정 품질' 페이지에서 검토 요청.",
          "신분증 인증 시 계정명과 신분증 이름 일치 여부 반드시 확인.",
          "신분증은 스마트폰 저장 이미지 아닌 직접 촬영본 사용."]),
    ]
    for col, num, tit, descs in steps:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_04.jpg"), "JPEG", quality=95)
    print("card_04.jpg 저장")

# ═══════════════════════════════════════════════════════════
# 카드 5 — 영구 정지 시 비즈니스 유지
# ═══════════════════════════════════════════════════════════
def card05():
    PHOTO_H = 360
    img = make_canvas("ban", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 5); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "WORST CASE  |  영구 정지 대응", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "영구 정지, 사업은 계속해야 합니다", font(48, bold=True), MARGIN, y, DARK) + 14

    intro = "영구 정지 계정은 원칙적으로 복구 방법이 없습니다. 하지만 사업은 멈출 수 없습니다. 빠른 수습과 대체 채널 확보가 핵심입니다."
    y = put_wrap(draw, intro, font(28), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=10) + 16

    # 긍정 소식 박스
    good_news = "✅  오탐 판정 계정은 Meta가 일괄 복구한 사례 있음 (2026.05.16)"
    f_g = font(26, bold=True); bb = f_g.getbbox(good_news)
    bh_g = (bb[3] - bb[1]) + 24
    draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + bh_g], radius=12,
                            fill=(240, 255, 245), outline=(60, 180, 100), width=2)
    draw.text((MARGIN + 18, y + 12 - bb[1]), good_news, font=f_g, fill=(30, 140, 70))
    y += bh_g + 24

    points = [
        (IG_PURPLE, "01", "이의 신청 & 공식 복구 절차 진행",
         ["Meta 공식 고객센터에 이의 신청 즉시 접수.",
          "2026년 2월부터 전기통신사업법 개정으로",
          "Meta의 실시간 고객 상담 의무화 — 적극 활용할 것."]),
        (IG_RED,    "02", "고객에게 즉시 대체 연락처 안내",
         ["카카오채널·네이버 스마트스토어·문자로 기존 고객에게 공지.",
          "재개설 계정 또는 다른 SNS 채널로 빠르게 이동 안내.",
          "단골 고객 DB(연락처)가 있으면 복구 속도가 훨씬 빠름."]),
        (IG_ORANGE, "03", "신규 계정 개설 시 주의사항",
         ["영구 정지 계정과 동일 기기·IP 사용 시 연쇄 차단 위험.",
          "새 계정은 처음 2~4주간 활동량을 30% 수준으로 제한하며 워밍업.",
          "이전과 동일한 비공식 앱·도구 사용 금지."]),
    ]
    for col, num, tit, descs in points:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_05.jpg"), "JPEG", quality=95)
    print("card_05.jpg 저장")

# ═══════════════════════════════════════════════════════════
# 카드 6 — 안전한 인스타 운영 수칙
# ═══════════════════════════════════════════════════════════
def card06():
    PHOTO_H = 360
    img = make_canvas("prevent", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 6); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "PREVENTION  |  안전 운영 수칙", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "사업 계정, 이렇게 지키세요", font(54, bold=True), MARGIN, y, DARK) + 28

    rules = [
        (IG_PURPLE, "01", "공식 Meta API 도구만 사용",
         ["DM 자동화·예약 발송은 Meta 공식 파트너 도구만 허용.",
          "비공식 팔로워 증대 앱·자동 좋아요 서비스 즉시 삭제.",
          "Meta Business Suite에서 연결 앱 목록 주기적으로 점검."]),
        (IG_RED,    "02", "2단계 인증 & 접속 기기 관리",
         ["2단계 인증 설정으로 해킹·의심 접속 차단.",
          "직원과 계정을 공유할 때는 개인 계정 권한 부여 방식 사용.",
          "VPN 사용을 최소화하고, 해외 접속 시 사전에 접속 이력 확인."]),
        (IG_ORANGE, "03", "계정 품질 점수 주기적 점검",
         ["Meta Business Suite > 계정 품질 페이지를 월 1회 이상 확인.",
          "광고 비승인 이력 누적 시 계정 품질 점수 하락 → 차단 위험.",
          "프로필 링크가 스팸으로 분류되지 않았는지도 함께 확인."]),
    ]
    for col, num, tit, descs in rules:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col)

    source_line(draw)
    bottom_bar(img)
    img.save(os.path.join(OUTPUT, "card_06.jpg"), "JPEG", quality=95)
    print("card_06.jpg 저장")

# ═══════════════════════════════════════════════════════════
# 카드 7 — 멀티채널 전략 & CTA
# ═══════════════════════════════════════════════════════════
def card07():
    PHOTO_H = 360
    img = make_canvas("strategy", PHOTO_H)
    draw = ImageDraw.Draw(img)

    card_num(img, draw, 7); draw = ImageDraw.Draw(img)
    category_pill(img, draw, "STRATEGY  |  리스크 분산 전략", MARGIN, PHOTO_H - 66)
    draw = ImageDraw.Draw(img)

    y = PHOTO_H + 28
    y = put(draw, "인스타 하나에 전부 걸지 마세요", font(50, bold=True), MARGIN, y, DARK) + 14

    intro = "인스타그램은 강력한 채널이지만, 단일 채널에 매출을 100% 의존하는 것은 리스크입니다. 지금부터 백업 채널을 함께 운영하세요."
    y = put_wrap(draw, intro, font(28), MARGIN, y, DARK, max_w=W - MARGIN * 2, gap=10) + 18

    strategies = [
        (IG_PURPLE, "01", "고객 DB(연락처) 반드시 확보",
         ["DM 문의 고객의 연락처나 카카오채널 친구 추가를 유도.",
          "SNS 계정이 사라져도 직접 연락 가능한 DB가 가장 중요한 자산.",
          "네이버 스마트스토어·자사 홈페이지 회원 가입도 함께 유도."]),
        (IG_RED,    "02", "카카오채널·네이버 블로그 병행",
         ["카카오채널은 인스타 차단 시 즉각 대체 소통 채널로 활용 가능.",
          "네이버 블로그는 검색 유입 기반으로 인스타와 다른 고객층 확보.",
          "두 채널을 합산하면 인스타 의존도를 절반 이하로 줄일 수 있음."]),
        (IG_ORANGE, "03", "정기 콘텐츠 백업 습관화",
         ["게시물·릴스·스토리 하이라이트를 주기적으로 로컬에 저장.",
          "계정 설정 > 데이터 다운로드 기능으로 전체 백업 가능.",
          "콘텐츠 자산을 잃지 않아야 재개설 시 빠르게 복원 가능."]),
    ]
    for col, num, tit, descs in strategies:
        y = bullet_block(draw, num, tit, descs, MARGIN, y, col=col)

    # 마무리 요약 + CTA
    divider(draw, y); y += 20

    summary_items = [
        "차단 = 매출 중단. 예방이 최선의 대책",
        "공식 도구만 사용, 계정 품질 주기적 점검",
        "인스타 외 백업 채널 지금 바로 시작",
    ]
    f_s = font(26)
    for i, s in enumerate(summary_items):
        bb = f_s.getbbox(s); sh = bb[3] - bb[1]
        draw.ellipse([MARGIN, y, MARGIN + sh, y + sh], fill=COLS[i])
        f_n = font(16, bold=True); nb = f_n.getbbox(str(i+1))
        nw2 = draw.textlength(str(i+1), font=f_n)
        draw.text((MARGIN + (sh - nw2) / 2,
                   y + (sh - (nb[3]-nb[1])) / 2 - nb[1]),
                  str(i+1), font=f_n, fill=WHITE)
        draw.text((MARGIN + sh + 14, y - bb[1]), s, font=f_s, fill=DARK)
        y += sh + 12

    y += 20
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
print("\n완료! output 폴더를 확인하세요.")
