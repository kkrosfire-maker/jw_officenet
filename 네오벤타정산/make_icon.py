"""앱 아이콘(app.ico)을 만든다. 한 번만 실행하면 된다.

네이비 바탕에 정산서 느낌의 표와 원화 기호. 별도 이미지 파일 없이 그려서 만든다.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "app.ico"

BG = (27, 42, 74)          # 네이비
PAPER = (255, 255, 255)
LINE = (186, 196, 212)
ACCENT = (240, 180, 41)    # 노랑
TEAL = (38, 166, 154)


def draw(size: int) -> Image.Image:
    # 큰 크기로 그린 뒤 줄여서 계단현상을 없앤다.
    scale = 8
    s = size * scale
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)

    # 둥근 네이비 배경
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=BG)

    # 종이
    m = int(s * 0.18)
    paper = [m, int(s * 0.14), s - m, s - int(s * 0.14)]
    d.rounded_rectangle(paper, radius=int(s * 0.04), fill=PAPER)

    left, top, right, bottom = paper
    width = right - left
    height = bottom - top

    # 머리글 띠
    d.rounded_rectangle(
        [left, top, right, top + int(height * 0.16)],
        radius=int(s * 0.04),
        fill=TEAL,
    )
    d.rectangle([left, top + int(height * 0.10), right, top + int(height * 0.16)], fill=TEAL)

    # 표 줄
    rows = 4
    gap = height * 0.15
    y = top + height * 0.28
    for i in range(rows):
        thickness = max(1, int(s * 0.018))
        x_end = right - width * (0.12 if i % 2 == 0 else 0.34)
        d.rounded_rectangle(
            [left + width * 0.10, y, x_end, y + thickness * 2],
            radius=thickness,
            fill=LINE,
        )
        y += gap

    # 합계 강조 줄 (노랑)
    d.rounded_rectangle(
        [left + width * 0.10, y, left + width * 0.55, y + int(s * 0.036)],
        radius=int(s * 0.018),
        fill=ACCENT,
    )

    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [draw(size) for size in sizes]
    images[-1].save(OUT, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"만들었습니다: {OUT}")


if __name__ == "__main__":
    main()
