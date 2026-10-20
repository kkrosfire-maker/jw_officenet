"""
마인오피스 카드뉴스 v3
- 실제 블로그 이미지 합성
- 고정 y 좌표로 텍스트 overflow 방지
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image, ImageDraw, ImageFont
import os
from card_renderer import font, lerp, th

W, H      = 1080, 1080
MARGIN    = 72
LOGO_Y    = 958
SAFE_BOT  = 948

OUTPUT   = r"C:\Users\JW\Desktop\workspace\office_news\output\mineoffice_v3"
IMG_DIR  = r"C:\Users\JW\Desktop\workspace\office_news\output\wons0_0_224168110325"
PFX      = "집_주소_노출_걱정_끝!_김포비상주사무실_직접_발품_팔아_결정한_마인오피스_후기_이미지_"
LOGO_PATH= r"C:\Users\JW\Desktop\정원유니어스\정원로고.png"
os.makedirs(OUTPUT, exist_ok=True)

# ── 색상 ─────────────────────────────────────────────────────
DARK      = (10, 10, 18)
DARK_RED  = (22, 8, 8)
DARK_GRN  = (8, 20, 14)
CARD_BOX  = (26, 22, 46)
RED       = (218, 38, 38)
RED_DARK  = (140, 16, 16)
RED_GLOW  = (255, 64, 64)
YELLOW    = (245, 210, 40)
TEAL      = (38, 195, 145)
WHITE     = (255, 255, 255)
GRAY      = (160, 165, 185)
GRAY_DIM  = (80, 88, 108)

def make_bg(top=None, bot=None):
    top = top or DARK_RED
    bot = bot or DARK
    s = Image.new("RGB", (1, H))
    px = s.load()
    for y in range(H):
        px[0, y] = lerp(top, bot, y/H)
    return s.resize((W, H))

def blog_img(n):
    return Image.open(os.path.join(IMG_DIR, f"{PFX}{n:02d}.jpg")).convert("RGB")

def crop_center(img, w, h):
    iw, ih = img.size
    sc = max(w/iw, h/ih)
    nw, nh = int(iw*sc)+1, int(ih*sc)+1
    img = img.resize((nw, nh), Image.LANCZOS)
    return img.crop(((nw-w)//2, (nh-h)//2, (nw-w)//2+w, (nh-h)//2+h))

def paste_photo(base, photo_n, x, y, w, h, dark=0.5, radius=14):
    """블로그 이미지를 크롭해서 base에 합성"""
    ph = crop_center(blog_img(photo_n), w, h)
    overlay = Image.new("RGB", (w, h), (0, 0, 0))
    ph = Image.blend(ph, overlay, dark)
    mask = Image.new("L", (w, h), 0)
    md   = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, w-1, h-1], radius=radius, fill=255)
    base.paste(ph, (x, y), mask=mask)

def full_bg_photo(photo_n, dark=0.62, tint=None):
    """사진을 1080x1080 배경으로, 어두운 오버레이 적용"""
    ph = crop_center(blog_img(photo_n), W, H)
    overlay = Image.new("RGB", (W, H), tint or (0,0,0))
    return Image.blend(ph, overlay, dark)

def put(draw, text, f, x, y, fill, align="left"):
    bb = f.getbbox(text)
    lw = draw.textlength(text, font=f)
    if align == "center": x = (W - lw) / 2
    elif align == "right": x = W - MARGIN - lw
    draw.text((x, y - bb[1]), text, font=f, fill=fill)
    return y + (bb[3] - bb[1])

def wrap_lines(draw, text, f, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur+" "+w).strip()
        if draw.textlength(t, font=f) <= max_w: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def put_wrap(draw, text, f, x, y, fill, max_w, gap=7, align="left"):
    for line in wrap_lines(draw, text, f, max_w):
        y = put(draw, line, f, x, y, fill, align=align) + gap
    return y

def left_bar(draw, y_top, h, color=RED):
    draw.rectangle([MARGIN, y_top, MARGIN+7, y_top+h], fill=color)

def badge(draw, text, x, y, bg=RED, fg=WHITE):
    f  = font(26, bold=True)
    bb = f.getbbox(text)
    lw = int(draw.textlength(text, font=f))
    pw, ph = lw+36, (bb[3]-bb[1])+14
    draw.rounded_rectangle([x, y, x+pw, y+ph], radius=5, fill=bg)
    draw.text((x+18, y+7-bb[1]), text, font=f, fill=fg)
    return pw, ph

def draw_logo(img, draw):
    ICON = 50
    fb   = font(26, bold=True)
    brand= "JUNGWON OFFICE NET"
    bw   = int(draw.textlength(brand, font=fb))
    sx   = (W - ICON - 12 - bw) // 2
    iy   = LOGO_Y
    draw.rounded_rectangle([sx, iy, sx+ICON, iy+ICON], radius=9, fill=(22,90,55))
    try:
        lo   = Image.open(LOGO_PATH).convert("RGBA")
        sc   = ICON / max(lo.width, lo.height)
        lw2, lh2 = int(lo.width*sc), int(lo.height*sc)
        lo   = lo.resize((lw2, lh2), Image.LANCZOS)
        img.paste(lo, (sx+(ICON-lw2)//2, iy+(ICON-lh2)//2), mask=lo.split()[3])
    except:
        fj = font(20, bold=True)
        jb = fj.getbbox("JW")
        draw.text((sx+(ICON-int(draw.textlength("JW",font=fj)))//2,
                   iy+(ICON-(jb[3]-jb[1]))//2-jb[1]), "JW", font=fj, fill=WHITE)
    bb = fb.getbbox(brand)
    draw.text((sx+ICON+12, iy+(ICON-(bb[3]-bb[1]))//2-bb[1]),
              brand, font=fb, fill=GRAY)

def hline(draw, y, color=RED_DARK, width=2):
    draw.line([(MARGIN, y), (W-MARGIN, y)], fill=color, width=width)

def box(draw, x, y, w, h, fill=CARD_BOX, bar_color=None, radius=14):
    draw.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=fill)
    if bar_color:
        draw.rectangle([x, y, x+7, y+h], fill=bar_color)


# ═══ 카드 00 — 표지 ══════════════════════════════════════════
def card00():
    # img_01 (로비) 배경 + 빨간 오버레이
    img  = full_bg_photo(1, dark=0.58, tint=(30, 5, 5))
    draw = ImageDraw.Draw(img)

    # 사선 경고 스트라이프 (반투명)
    ol = Image.new("RGBA", (W, H), (0,0,0,0))
    d2 = ImageDraw.Draw(ol)
    for x in range(-H, W+H, 110):
        d2.polygon([(x,0),(x+50,0),(x+50+H,H),(x+H,H)], fill=(160,0,0,22))
    img.paste(Image.alpha_composite(img.convert("RGBA"), ol).convert("RGB"))
    draw = ImageDraw.Draw(img)

    # 상단 배지 (y=72)
    bw1, bh = badge(draw, "⚠  경고", MARGIN, 72, bg=RED)
    badge(draw, "사업자등록증 집 주소 위험", MARGIN+bw1+12, 72,
          bg=(55,18,18), fg=RED_GLOW)

    # 메인 타이틀 (고정 y=148)
    f90 = font(90, bold=True)
    put(draw, "당신의 집 주소는", f90, 0, 148, WHITE, align="center")
    put(draw, "안전합니까?",       f90, 0, 256, RED_GLOW, align="center")

    # 소제목 (고정 y=370)
    f38 = font(38)
    put_wrap(draw, "사업자등록증 속 집 주소가 시한폭탄인 이유",
             f38, 0, 370, YELLOW, W-MARGIN*2, gap=0, align="center")

    # 하단 강조 박스 (y=800)
    box(draw, MARGIN, 800, W-MARGIN*2, 110, fill=(50,10,10), bar_color=RED, radius=16)
    f36b = font(34, bold=True)
    put(draw, "5컷으로 보는 집주소 위험과 해결책", f36b, 0, 820, WHITE, align="center")
    f30  = font(30)
    put(draw, "마인공유오피스 · 김포 비상주사무실", f30, 0, 868, GRAY, align="center")

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "00_표지.png"))
    print("00_표지.png ✓")


# ═══ 카드 01 — 사생활 증발 ══════════════════════════════════
def card01():
    img  = make_bg(top=(22, 8, 8), bot=DARK)
    draw = ImageDraw.Draw(img)

    # 배지 (y=72)
    bw1, bh = badge(draw, "1컷", MARGIN, 72, bg=(55,18,18), fg=RED_GLOW)
    badge(draw, "사생활 증발: 24시간 전국민 공개", MARGIN+bw1+10, 72, bg=RED)

    # 좌측 타이틀 바 + 핵심 문구 (y=134)
    left_bar(draw, 134, 9, RED)
    f64 = font(64, bold=True)
    put(draw, '“누가 우리 집',   f64, MARGIN+18, 134, WHITE)
    put(draw, ' 초인종을 눌렀다”', f64, MARGIN+18, 210, RED_GLOW)

    # 우측: img_02 (마인오피스 안내판) — 주소지 실존 증거
    paste_photo(img, 2, W-MARGIN-310, 134, 310, 340, dark=0.15, radius=14)
    # 안내판 위 레이블
    lf = font(22, bold=True)
    lt = "실제 사업장 주소지"
    draw.rounded_rectangle([W-MARGIN-310, 134+306, W-MARGIN, 134+340],
                            radius=8, fill=(30,10,10))
    lw2 = draw.textlength(lt, font=lf)
    draw.text((W-MARGIN-155-lw2//2, 134+312-lf.getbbox(lt)[1]),
              lt, font=lf, fill=RED_GLOW)

    # 좌측 텍스트 블록 2개 (y=294~, 폭=600)
    TW = W - MARGIN - 310 - MARGIN - 16  # ≈ 590
    f30 = font(30)
    f28 = font(28)

    # 블록 1 (y=294, h=148)
    box(draw, MARGIN, 294, TW, 148, bar_color=RED)
    put(draw, "📌  쇼핑몰·홈택스 조회로 집 주소 인터넷 노출",
        font(28, bold=True), MARGIN+18, 308, WHITE)
    put_wrap(draw, "누구나 사업자 정보를 검색하면 사업장 주소(= 내 집 주소)가 그대로 나옵니다.",
             f28, MARGIN+18, 352, GRAY, TW-36, gap=6)

    # 블록 2 (y=454, h=148)
    box(draw, MARGIN, 454, TW, 148, bar_color=RED)
    put(draw, "📌  악성 민원인·스토커가 가족 공간까지 찾아옴",
        font(28, bold=True), MARGIN+18, 468, WHITE)
    put_wrap(draw, "한 번 노출된 주소는 이사 후에도 인터넷 기록에 영구히 남습니다.",
             f28, MARGIN+18, 512, GRAY, TW-36, gap=6)

    # 하단 강조 바 (y=618)
    box(draw, MARGIN, 618, W-MARGIN*2, 64, fill=RED_DARK, radius=12)
    f34b = font(34, bold=True)
    em = "지금 이 순간도 내 집 주소는 인터넷에 공개 중입니다"
    ew = draw.textlength(em, font=f34b)
    draw.text(((W-ew)//2, 630-f34b.getbbox(em)[1]), em, font=f34b, fill=YELLOW)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "01_사생활증발.png"))
    print("01_사생활증발.png ✓")


# ═══ 카드 02 — 신뢰도 추락 ══════════════════════════════════
def card02():
    img  = make_bg(top=(16, 12, 6), bot=DARK)
    draw = ImageDraw.Draw(img)

    # 상단 img_04 (회의실) 배경 영역 (y=0~290)
    paste_photo(img, 4, 0, 0, W, 290, dark=0.55, radius=0)
    # 상단 영역 위에 그라디언트 하단 페이드
    fade = Image.new("RGBA", (W, 80), (0,0,0,0))
    fd = ImageDraw.Draw(fade)
    for i in range(80):
        fd.line([(0, i), (W, i)], fill=(10,10,10, int(255*(i/80)**1.5)))
    img.paste(fade, (0, 210), mask=fade.split()[3])
    draw = ImageDraw.Draw(img)

    # 이미지 위 텍스트
    bw1, bh = badge(draw, "2컷", MARGIN, 18, bg=(50,35,5), fg=YELLOW)
    badge(draw, "신뢰도 추락: 아파트 주소의 한계", MARGIN+bw1+10, 18,
          bg=YELLOW, fg=(30,20,0))
    left_bar(draw, 66, 9, YELLOW)
    f62 = font(62, bold=True)
    put(draw, '“○○아파트 주민이',   f62, MARGIN+18, 66, WHITE)
    put(draw, ' 비즈니스 파트너?”', f62, MARGIN+18, 140, YELLOW)

    # 말풍선 (이미지 위 우측)
    bub_x, bub_y, bub_w, bub_h = 680, 24, 330, 68
    draw.rounded_rectangle([bub_x, bub_y, bub_x+bub_w, bub_y+bub_h],
                            radius=12, fill=(40,32,5))
    draw.rounded_rectangle([bub_x, bub_y, bub_x+bub_w, bub_y+bub_h],
                            outline=YELLOW, width=2, radius=12)
    fb = font(25, bold=True)
    draw.text((bub_x+14, bub_y+12-fb.getbbox("어")[1]),
              "어… 이거 아파트 주소인데?", font=fb, fill=YELLOW)
    # 말풍선 꼬리
    draw.polygon([(bub_x+50, bub_y+bub_h),
                  (bub_x+70, bub_y+bub_h),
                  (bub_x+58, bub_y+bub_h+16)], fill=(40,32,5))

    # y=300 이하: 어두운 배경 위 텍스트
    hline(draw, 302, color=YELLOW, width=2)

    # 박스 2개 (y=316, h=152)
    BW = (W - MARGIN*2 - 18) // 2
    box(draw, MARGIN,         316, BW, 152, bar_color=YELLOW)
    box(draw, MARGIN+BW+18,   316, BW, 152, bar_color=(180,150,20))

    f30b = font(30, bold=True)
    f27  = font(27)
    # 박스 ①
    put(draw, "계약 직전 거래처가",     f30b, MARGIN+16, 330, YELLOW)
    put(draw, "주소 검색 → 아파트 노출", f30b, MARGIN+16, 368, WHITE)
    put_wrap(draw, "첫인상에서 신뢰가 무너집니다.",
             f27, MARGIN+16, 408, GRAY, BW-32, gap=5)

    bx2 = MARGIN+BW+18
    put(draw, "아무리 좋은 사업 아이템도", f30b, bx2+16, 330, (220,190,30))
    put(draw, "구멍가게처럼 보입니다",     f30b, bx2+16, 368, WHITE)
    put_wrap(draw, "주소 하나가 수백만 원 계약을 날립니다.",
             f27, bx2+16, 408, GRAY, BW-32, gap=5)

    # 강조 바 (y=482)
    box(draw, MARGIN, 482, W-MARGIN*2, 64, fill=(50,42,6), radius=12)
    draw.rounded_rectangle([MARGIN, 482, W-MARGIN, 546],
                            outline=YELLOW, width=2, radius=12)
    f34b = font(34, bold=True)
    em = "주소 한 줄이 당신의 브랜드를 말해줍니다"
    ew = draw.textlength(em, font=f34b)
    draw.text(((W-ew)//2, 494-f34b.getbbox(em)[1]), em, font=f34b, fill=YELLOW)

    # 보충 설명 (y=566)
    f32  = font(32)
    f32b = font(32, bold=True)
    put(draw, "번듯한 상업용 주소지 = 파트너에게 보내는 신뢰 신호",
        f32b, MARGIN, 574, WHITE)
    put_wrap(draw, "계약 성사율, 입찰 통과율, 파트너 미팅 성공률이 달라집니다.",
             f32, MARGIN, 622, GRAY, W-MARGIN*2, gap=0)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "02_신뢰도추락.png"))
    print("02_신뢰도추락.png ✓")


# ═══ 카드 03 — 유령 사무실 주의 ═════════════════════════════
def card03():
    img  = make_bg(top=(22, 8, 8), bot=DARK)
    draw = ImageDraw.Draw(img)

    # 배지 (y=72)
    bw1, bh = badge(draw, "3컷", MARGIN, 72, bg=(55,18,18), fg=RED_GLOW)
    badge(draw, "가짜 비상주 주의!", MARGIN+bw1+10, 72, bg=RED)

    # 타이틀 (y=134)
    left_bar(draw, 134, 9, RED)
    f60 = font(60, bold=True)
    put(draw, '“싼 게 비지떡?',      f60, MARGIN+18, 134, WHITE)
    put(draw, ' 유령 사무실의 함정”', f60, MARGIN+18, 206, RED_GLOW)

    # ── 도장 + img_05 나란히 (y=284, h=230) ──────────────────
    STAMP_W, STAMP_H = 280, 230

    # 도장 그래픽 (좌, x=MARGIN)
    draw.rounded_rectangle([MARGIN, 284, MARGIN+STAMP_W, 284+STAMP_H],
                            radius=14, fill=(42,10,10))
    draw.rounded_rectangle([MARGIN+3, 287, MARGIN+STAMP_W-3, 284+STAMP_H-3],
                            outline=RED_DARK, width=3, radius=11)
    cx, cy = MARGIN + STAMP_W//2, 284 + STAMP_H//2
    draw.ellipse([cx-118, cy-82, cx+118, cy+82], outline=RED, width=3)
    draw.ellipse([cx-110, cy-74, cx+110, cy+74], outline=RED_DARK, width=1)
    f22b = font(22, bold=True)
    f46b = font(46, bold=True)
    f20  = font(20)
    for txt, fs, fc, dy in [
        ("사업자 등록", f22b, GRAY,     -56),
        ("반  려",      f46b, RED_GLOW, -10),
        ("주소지 실사 불일치", f20,  GRAY_DIM,  50),
    ]:
        tw = draw.textlength(txt, font=fs)
        bb = fs.getbbox(txt)
        draw.text((cx-tw//2, cy+dy-bb[1]), txt, font=fs, fill=fc)

    # img_05 (마인오피스 입구 동판) — 우측
    IMG_X = MARGIN + STAMP_W + 20
    IMG_W = W - MARGIN - IMG_X
    paste_photo(img, 5, IMG_X, 284, IMG_W, STAMP_H, dark=0.1, radius=14)
    # "실제 공간 증명" 레이블
    lf2 = font(24, bold=True)
    lt2 = "✅  실제 공간 증명"
    lw2 = draw.textlength(lt2, font=lf2)
    lx2 = IMG_X + (IMG_W - lw2) // 2
    draw.rounded_rectangle([lx2-12, 284+STAMP_H-46, lx2+lw2+12, 284+STAMP_H-6],
                            radius=8, fill=(10,60,36))
    draw.text((lx2, 284+STAMP_H-40-lf2.getbbox(lt2)[1]),
              lt2, font=lf2, fill=WHITE)

    # ── 체크 3개 (y=530, bh=120, gap=10) ──────────────────────
    BW = W - MARGIN*2
    BH = 120
    GAP = 10
    items = [
        ("①", "실제 사무 공간이 있는가?",
         "관공서 실사 때 빈 공간이면 사업자 등록 취소 위험"),
        ("②", "본사 100% 직영인가?",
         "중개·대행 업체는 문제 발생 시 책임 소재 불분명"),
        ("③", "우편·택배 관리 시스템?",
         "주소지 우편물 미관리 → 세금계산서·공문 분실 위험"),
    ]
    for i, (num, title, desc) in enumerate(items):
        by = 530 + i*(BH+GAP)
        box(draw, MARGIN, by, BW, BH, bar_color=None)
        # 번호 원
        cx2, cy2, r = MARGIN+42, by+BH//2, 28
        draw.ellipse([cx2-r, cy2-r, cx2+r, cy2+r], fill=RED)
        fn = font(26, bold=True)
        nw = draw.textlength(num, font=fn)
        nb = fn.getbbox(num)
        draw.text((cx2-nw//2, cy2-(nb[3]-nb[1])//2-nb[1]), num, font=fn, fill=WHITE)
        # 텍스트
        f34b2 = font(34, bold=True)
        f27b  = font(27)
        put(draw, title, f34b2, MARGIN+88, by+18, WHITE)
        put_wrap(draw, desc, f27b, MARGIN+88, by+60, GRAY, BW-100, gap=0)

    # 경고 바 (y=530+3*130=920, 실제 y=900)
    WARN_Y = 530 + 3*(BH+GAP)  # = 530+390 = 920
    if WARN_Y + 40 <= SAFE_BOT:
        box(draw, MARGIN, WARN_Y, W-MARGIN*2, 40, fill=RED_DARK, radius=8)
        f28b = font(28, bold=True)
        wt = "3가지 중 하나라도 빠지면 → 사업자 취소 위험!"
        ww = draw.textlength(wt, font=f28b)
        draw.text(((W-ww)//2, WARN_Y+8-f28b.getbbox(wt)[1]), wt, font=f28b, fill=YELLOW)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "03_유령사무실.png"))
    print("03_유령사무실.png ✓")


# ═══ 카드 04 — 결론 CTA ══════════════════════════════════════
def card04():
    img  = make_bg(top=(8, 22, 16), bot=DARK)
    draw = ImageDraw.Draw(img)

    # 상단 img_03 (깔끔한 사무실) 배경 영역 (0~285)
    paste_photo(img, 3, 0, 0, W, 285, dark=0.45, radius=0)
    # 하단 페이드
    fade = Image.new("RGBA", (W, 80), (0,0,0,0))
    fd = ImageDraw.Draw(fade)
    for i in range(80):
        fd.line([(0,i),(W,i)], fill=(8,22,16, int(255*(i/80)**1.5)))
    img.paste(fade, (0, 205), mask=fade.split()[3])
    draw = ImageDraw.Draw(img)

    # 이미지 위 텍스트 (y=14~)
    bw1, bh = badge(draw, "4컷", MARGIN, 14, bg=(10,40,26), fg=TEAL)
    badge(draw, "지금 바로 해결하세요", MARGIN+bw1+10, 14, bg=TEAL, fg=(5,30,20))
    left_bar(draw, 62, 9, TEAL)
    f60 = font(60, bold=True)
    put(draw, '“소 잃고 외양간',   f60, MARGIN+18, 62, WHITE)
    put(draw, ' 고치면 늦습니다”', f60, MARGIN+18, 134, TEAL)

    # 안전 레이블 (이미지 우측 하단)
    sl = font(24, bold=True)
    st = "✅  안전한 사업장 주소"
    sw = draw.textlength(st, font=sl)
    draw.rounded_rectangle([W-MARGIN-sw-24, 248, W-MARGIN, 282],
                            radius=8, fill=(12,70,46))
    draw.text((W-MARGIN-sw-12, 252-sl.getbbox(st)[1]), st, font=sl, fill=WHITE)

    hline(draw, 298, color=TEAL, width=2)

    # 포인트 박스 2개 (y=312, h=138)
    BW = (W - MARGIN*2 - 18) // 2
    box(draw, MARGIN,       312, BW, 138, bar_color=RED)
    box(draw, MARGIN+BW+18, 312, BW, 138, bar_color=TEAL)

    f30b = font(30, bold=True)
    f27  = font(27)
    put(draw, "한 번 노출 = 영구 기록",   f30b, MARGIN+16, 326, RED_GLOW)
    put(draw, "이사 후에도 검색됩니다",   f30b, MARGIN+16, 364, WHITE)
    put_wrap(draw, "인터넷 기록은 삭제되지 않습니다.",
             f27, MARGIN+16, 404, GRAY, BW-32, gap=0)

    bx2 = MARGIN+BW+18
    put(draw, "월 몇만 원의 선택이",  f30b, bx2+16, 326, TEAL)
    put(draw, "가족·사업 모두를 지킴", f30b, bx2+16, 364, WHITE)
    put_wrap(draw, "비상주 사무실 = 가장 싼 보험입니다.",
             f27, bx2+16, 404, GRAY, BW-32, gap=0)

    # CTA 버튼 (y=466, h=154)
    draw.rounded_rectangle([MARGIN, 466, W-MARGIN, 620],
                            radius=20, fill=(14,90,60))
    draw.rounded_rectangle([MARGIN, 466, W-MARGIN, 620],
                            outline=TEAL, width=3, radius=20)
    f40b = font(40, bold=True)
    f30  = font(30)
    cta1 = "안전한 비상주 주소지로 지금 변경하세요!"
    cta2 = "마인공유오피스  |  보증금 0원 · 관리비 0원 · 직영 운영"
    c1w = draw.textlength(cta1, font=f40b)
    c2w = draw.textlength(cta2, font=f30)
    draw.text(((W-c1w)//2, 488-f40b.getbbox(cta1)[1]), cta1, font=f40b, fill=WHITE)
    draw.text(((W-c2w)//2, 548-f30.getbbox(cta2)[1]),  cta2, font=f30,  fill=TEAL)

    # 하단 보충 (y=636)
    f30gd = font(30)
    put_wrap(draw,
             "김포 풍무역 4분 · 보증금·관리비 0원 · 법인설립·사업자등록 무료 대행",
             f30gd, MARGIN, 644, GRAY, W-MARGIN*2, gap=7, align="center")

    # 해시태그 (y=720)
    f26 = font(26)
    tags = "#김포비상주사무실  #마인오피스  #비상주사무실추천  #사업자등록주소지"
    tw = draw.textlength(tags, font=f26)
    draw.text(((W-tw)//2, 726-f26.getbbox(tags)[1]), tags, font=f26, fill=GRAY_DIM)

    draw_logo(img, draw)
    img.save(os.path.join(OUTPUT, "04_결론CTA.png"))
    print("04_결론CTA.png ✓")


# ── 실행 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("마인오피스 카드뉴스 v3 생성 중...\n")
    card00()
    card01()
    card02()
    card03()
    card04()
    print(f"\n완료 → {OUTPUT}")
