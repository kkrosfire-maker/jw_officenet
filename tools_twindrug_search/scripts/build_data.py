"""심평원 공개 자료 2개를 받아 웹에서 쓰는 public/data.json 을 만든다.

1. 약제급여목록및급여상한금액표 (매달 1일 기준, 전체 급여 약)
2. 저가약 대체조제 장려금 지급대상 의약품 목록 (생동인정·생동대조약 표시)

사용법:  python scripts/build_data.py          # 최신 자료를 내려받아 만들기
         python scripts/build_data.py --local  # data_raw 에 있는 파일로만 만들기
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data_raw"
OUT = ROOT / "public" / "data.json"

HIRA = "https://www.hira.or.kr"
BOARD_PRICE = "HIRAA030014050000"  # 약제급여목록표
BOARD_SUBST = "HIRAA030015000000"  # 저가약 대체조제
UA = {"User-Agent": "Mozilla/5.0"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def latest_post(pgmid: str, title_word: str) -> tuple[str, str]:
    """게시판 첫 페이지에서 제목에 title_word 가 든 가장 최근 글 (번호, 제목)."""
    s = fetch(f"{HIRA}/bbsDummyKR.do?pgmid={pgmid}").decode("utf-8", "ignore")
    for m in re.finditer(r"brdBltNo=(\d+)[^>]*>(.*?)</a>", s, re.S):
        title = re.sub(r"\s+", " ", re.sub("<[^>]+>", "", html.unescape(m.group(2)))).strip()
        if title_word in title:
            return m.group(1), title
    raise RuntimeError(f"게시판 {pgmid} 에서 '{title_word}' 글을 못 찾음")


def download_xlsx(pgmid: str, title_word: str, save_as: Path) -> str:
    no, title = latest_post(pgmid, title_word)
    s = fetch(
        f"{HIRA}/bbsDummyKR.do?pgmid={pgmid}&brdScnBltNo=4&brdBltNo={no}&pageIndex=1&pageIndex2=1"
    ).decode("utf-8", "ignore")
    for args in re.findall(r"downLoadBbs\('(\d+)','(\d+)','(\d+)','(\d+)'\)", s):
        url = (
            f"{HIRA}/bbs/bbsCDownLoad.do?apndNo={args[0]}&apndBrdBltNo={args[1]}"
            f"&apndBrdTyNo={args[2]}&apndBltNo={args[3]}"
        )
        data = fetch(url)
        if data[:2] == b"PK":  # xlsx (hwp 안내문은 건너뜀)
            save_as.write_bytes(data)
            print(f"받음: {title} -> {save_as.name}")
            return title
    raise RuntimeError(f"'{title}' 글에 엑셀 첨부가 없음")


def header_index(row) -> dict:
    return {re.sub(r"\s+", "", str(v)): i for i, v in enumerate(row) if v is not None}


def read_price_list(path: Path):
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    h = header_index(next(rows))
    col = lambda name: h[name]  # noqa: E731
    for r in rows:
        if not r[col("제품코드")]:
            continue
        yield {
            "route": r[col("투여")],
            "group": str(r[col("주성분코드_동일제형")]).strip(),
            "ing": re.sub(r"\s+", " ", str(r[col("주성분명")] or "")).strip(),
            "code": str(r[col("제품코드")]).strip(),
            "name": str(r[col("제품명")]).strip(),
            "maker": str(r[col("업체명")] or "").strip(),
            "spec": str(r[col("규격")] or "").strip(),
            "unit": str(r[col("단위")] or "").strip(),
            "price": r[col("상한금액표금액")],
            "rx": r[col("전일")],
            "note": str(r[col("비고")] or "").strip(),
        }


def read_subst_list(path: Path) -> dict:
    """제품코드 -> (생동인정, 생동대조약)"""
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    h = None
    out = {}
    for r in rows:
        if h is None:
            if "제품코드" in [str(v).strip() for v in r]:
                h = header_index(r)
            continue
        code = r[h["제품코드"]]
        if not code:
            continue
        be = r[h["생동인정여부(공고번호)"]]
        ref = r[h["생동대조약여부"]]
        out[str(code).strip()] = (bool(be and "○" in str(be)), bool(ref and "○" in str(ref)))
    return out


def main():
    RAW.mkdir(exist_ok=True)
    price_path = RAW / "price_list.xlsx"
    subst_path = RAW / "substitution.xlsx"
    if "--local" in sys.argv:
        price_title = subst_title = "(내 PC 파일)"
    else:
        price_title = download_xlsx(BOARD_PRICE, "약제급여목록", price_path)
        subst_title = download_xlsx(BOARD_SUBST, "대체조제 장려금", subst_path)

    subst = read_subst_list(subst_path)
    groups: dict[str, list] = {}
    items = []
    for d in read_price_list(price_path):
        g = groups.setdefault(d["group"], [d["ing"], d["route"]])
        be, ref = subst.get(d["code"], (False, False))
        flags = (1 if be else 0) | (2 if ref else 0) | (4 if d["rx"] == "일반" else 0)
        items.append([
            d["code"], d["name"], d["maker"], d["group"],
            d["price"] if isinstance(d["price"], (int, float)) else None,
            d["unit"], d["spec"], flags, d["note"],
        ])

    # 기준일: 시트 이름 "2026년11월01일_(…)" 에서 (없으면 게시글 제목에서)
    sheet = openpyxl.load_workbook(price_path, read_only=True).worksheets[0].title
    date_m = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", sheet) or re.search(
        r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", price_title
    )
    data = {
        # 만든 날짜는 넣지 않는다 — 자료가 같으면 파일도 똑같아야 자동 갱신이 헛커밋을 안 한다
        "basis": f"{date_m.group(1)}-{int(date_m.group(2)):02d}-{int(date_m.group(3)):02d}" if date_m else "",
        "sources": [price_title, subst_title],
        "groups": groups,
        "items": items,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"완료: 약 {len(items):,}개, 묶음 {len(groups):,}개, 생동대조약 {sum(1 for i in items if i[7] & 2):,}개")
    print(f"파일: {OUT}  ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
