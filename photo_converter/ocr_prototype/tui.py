"""
PROTOTYPE TUI — throwaway. core.py를 감싸는 얇은 터미널 셸.
실행: python ocr_prototype/tui.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # photo_converter/ (imageio_utils용)

import core
from imageio_utils import read_image

B, DIM, RESET = "\x1b[1m", "\x1b[2m", "\x1b[0m"

DEFAULT_IMAGE = str(Path(__file__).resolve().parent.parent / "인성의원 6월 셀트리온.png")

DEFAULT_COL_RANGES = {
    "처방명": (0.23, 0.69),
    "사용량": (0.69, 0.75),
}


class State:
    def __init__(self):
        self.image_path = DEFAULT_IMAGE
        self.img_bgr = None
        self.rects = []
        self.sel_idx = 0
        self.lang = "kor+eng"
        self.psm = 6
        self.contrast = True
        self.scale = 1.0
        self.col_ranges = dict(DEFAULT_COL_RANGES)
        self.last_mode = None
        self.last_result = None
        self.status = ""


def load_image(st: State, path: str):
    st.image_path = path
    st.img_bgr = read_image(path)
    st.rects = core.find_red_rects(st.img_bgr) if st.img_bgr is not None else []
    st.sel_idx = 0
    st.last_mode = None
    st.last_result = None
    st.status = f"이미지 로드: {path}" if st.img_bgr is not None else f"로드 실패: {path}"


def selected_crop_pil(st: State):
    if not st.rects:
        return None
    box = st.rects[st.sel_idx]
    crop_bgr = core.crop(st.img_bgr, box)
    return core.preprocess(crop_bgr, enhance_contrast=st.contrast, scale=st.scale)


def render(st: State):
    print("\x1b[2J\x1b[H", end="")
    print(f"{B}=== OCR 그리드 프로토타입 (3단계 방향 탐색) ==={RESET}")
    print(f"{B}이미지{RESET}: {st.image_path}  {DIM}({'로드됨' if st.img_bgr is not None else '없음'}){RESET}")
    if st.img_bgr is not None:
        h, w = st.img_bgr.shape[:2]
        print(f"{DIM}크기: {w}x{h}{RESET}")
    print(f"{B}빨간 테두리{RESET}: {len(st.rects)}개 감지됨")
    for i, box in enumerate(st.rects):
        marker = f"{B}> " if i == st.sel_idx else "  "
        x0, y0, x1, y1 = box
        print(f"{marker}[{i}] ({x0},{y0})-({x1},{y1})  {DIM}{x1-x0}x{y1-y0}{RESET}{RESET}")
    print(f"{B}lang{RESET}={st.lang}  {B}psm{RESET}={st.psm}  "
          f"{B}contrast{RESET}={st.contrast}  {B}scale{RESET}={st.scale}")
    print(f"{B}컬럼 범위{RESET}: " + ", ".join(f"{k}=({lo:.2f}~{hi:.2f})" for k, (lo, hi) in st.col_ranges.items()))
    print()
    if st.status:
        print(f"{DIM}{st.status}{RESET}")
        print()
    if st.last_mode:
        print(f"{B}--- 결과: {st.last_mode} ---{RESET}")
        print(st.last_result)
        print()
    print(f"{B}명령{RESET} {DIM}(엔터로 실행){RESET}")
    print(f"  {B}img <path>{RESET}      이미지 로드 (생략 시 샘플 재로드)")
    print(f"  {B}detect{RESET}          빨간 테두리 재감지")
    print(f"  {B}sel <n>{RESET}         테두리 선택")
    print(f"  {B}run{RESET}             선택 영역에 raw/lines/cols 3가지 전부 실행")
    print(f"  {B}raw{RESET} / {B}lines{RESET} / {B}cols{RESET}   전략 하나만 실행")
    print(f"  {B}contrast{RESET}        대비강조 토글")
    print(f"  {B}scale <f>{RESET}       업스케일 배율 (예: scale 2.0)")
    print(f"  {B}psm <n>{RESET}         tesseract --psm 값 변경")
    print(f"  {B}setcol <name> <lo> <hi>{RESET}  컬럼 범위 추가/수정 (rel_x 0~1)")
    print(f"  {B}delcol <name>{RESET}   컬럼 범위 삭제")
    print(f"  {B}savecrop{RESET}        선택 영역 크롭을 스크래치패드에 PNG로 저장 (육안 확인용)")
    print(f"  {B}q{RESET}               종료")


def run_raw(st: State):
    pil = selected_crop_pil(st)
    if pil is None:
        st.status = "선택된 테두리 없음"
        return
    st.last_mode = "raw (image_to_string)"
    st.last_result = core.ocr_raw_text(pil, lang=st.lang, psm=st.psm)
    st.status = ""


def run_lines(st: State):
    pil = selected_crop_pil(st)
    if pil is None:
        st.status = "선택된 테두리 없음"
        return
    words = core.ocr_words(pil, lang=st.lang, psm=st.psm)
    rows = core.cluster_rows(words)
    lines = core.rows_to_lines(rows)
    st.last_mode = f"lines (row-cluster, {len(rows)}행)"
    st.last_result = "\n".join(f"[{i}] {ln}" for i, ln in enumerate(lines)) or "(없음)"
    st.status = ""


def run_cols(st: State):
    pil = selected_crop_pil(st)
    if pil is None:
        st.status = "선택된 테두리 없음"
        return
    words = core.ocr_words(pil, lang=st.lang, psm=st.psm)
    rows = core.cluster_rows(words)
    parsed = core.extract_columns(rows, st.col_ranges)
    st.last_mode = f"cols (컬럼 파싱, {len(parsed)}행)"
    st.last_result = "\n".join(str(p) for p in parsed) or "(없음)"
    st.status = ""


def run_all(st: State):
    pil = selected_crop_pil(st)
    if pil is None:
        st.status = "선택된 테두리 없음"
        return
    raw = core.ocr_raw_text(pil, lang=st.lang, psm=st.psm)
    words = core.ocr_words(pil, lang=st.lang, psm=st.psm)
    rows = core.cluster_rows(words)
    lines = core.rows_to_lines(rows)
    parsed = core.extract_columns(rows, st.col_ranges)
    st.last_mode = "run (raw + lines + cols)"
    parts = [
        f"{B}[raw]{RESET}\n{raw.strip()}",
        f"{B}[lines, {len(rows)}행]{RESET}\n" + "\n".join(f"  [{i}] {ln}" for i, ln in enumerate(lines)),
        f"{B}[cols, {len(parsed)}행]{RESET}\n" + "\n".join(f"  {p}" for p in parsed),
    ]
    st.last_result = "\n\n".join(parts)
    st.status = ""


def main():
    st = State()
    load_image(st, DEFAULT_IMAGE)
    while True:
        render(st)
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        parts = line.split()
        cmd, args = parts[0], parts[1:]

        if cmd == "q":
            break
        elif cmd == "img":
            load_image(st, " ".join(args) if args else DEFAULT_IMAGE)
        elif cmd == "detect":
            st.rects = core.find_red_rects(st.img_bgr) if st.img_bgr is not None else []
            st.sel_idx = 0
            st.status = f"{len(st.rects)}개 감지"
        elif cmd == "sel":
            if args and args[0].isdigit() and int(args[0]) < len(st.rects):
                st.sel_idx = int(args[0])
                st.status = f"[{st.sel_idx}] 선택"
            else:
                st.status = "sel <n> 형식, n은 유효한 인덱스"
        elif cmd == "run":
            run_all(st)
        elif cmd == "raw":
            run_raw(st)
        elif cmd == "lines":
            run_lines(st)
        elif cmd == "cols":
            run_cols(st)
        elif cmd == "contrast":
            st.contrast = not st.contrast
            st.status = f"contrast={st.contrast}"
        elif cmd == "scale":
            if args:
                try:
                    st.scale = float(args[0])
                except ValueError:
                    st.status = "scale <숫자>"
        elif cmd == "psm":
            if args and args[0].isdigit():
                st.psm = int(args[0])
        elif cmd == "setcol":
            if len(args) == 3:
                try:
                    st.col_ranges[args[0]] = (float(args[1]), float(args[2]))
                    st.status = f"{args[0]} 범위 설정됨"
                except ValueError:
                    st.status = "setcol <name> <lo> <hi>, lo/hi는 0~1 사이 숫자"
            else:
                st.status = "setcol <name> <lo> <hi>"
        elif cmd == "delcol":
            if args and args[0] in st.col_ranges:
                del st.col_ranges[args[0]]
                st.status = f"{args[0]} 삭제됨"
        elif cmd == "savecrop":
            pil = selected_crop_pil(st)
            if pil is None:
                st.status = "선택된 테두리 없음"
            else:
                out = Path(__file__).resolve().parent / f"_crop_preview_{st.sel_idx}.png"
                pil.save(out)
                st.status = f"저장됨: {out}"
        else:
            st.status = f"알 수 없는 명령: {cmd}"


if __name__ == "__main__":
    main()
