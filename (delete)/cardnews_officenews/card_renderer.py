"""공통 PIL 렌더링 유틸. office_news 하위 모든 카드 제너레이터가 공유한다."""
from PIL import Image, ImageDraw, ImageFont

FONT_REG  = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def lerp(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def th(f: ImageFont.FreeTypeFont) -> int:
    """한글 글자 높이."""
    bb = f.getbbox("가")
    return bb[3] - bb[1]


def put(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont,
        x: int, y: int, fill: tuple, align: str = "left",
        canvas_w: int = 1080) -> int:
    """텍스트를 그리고 다음 줄 y를 반환한다."""
    bb = f.getbbox(text)
    lw = draw.textlength(text, font=f)
    ox = x
    if align == "center":
        ox = (canvas_w - lw) / 2
    draw.text((ox, y - bb[1]), text, font=f, fill=fill)
    return y + (bb[3] - bb[1])


def put_wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont,
             x: int, y: int, fill: tuple, max_w: int, gap: int = 8) -> int:
    """단어 단위 줄바꿈 텍스트를 그리고 다음 y를 반환한다."""
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
        y = put(draw, line, f, x, y, fill) + gap
    return y


def make_bg(w: int, h: int, top: tuple, bot: tuple) -> Image.Image:
    """위→아래 선형 그라디언트 배경 이미지를 반환한다."""
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        px[0, y] = lerp(top, bot, y / h)
    return strip.resize((w, h))
