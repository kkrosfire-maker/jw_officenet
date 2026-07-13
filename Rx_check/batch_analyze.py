"""
처방약 배치 분석기 (Tesseract OCR, API 불필요)
입력대기 폴더의 이미지 파일들을 의원별로 분석 후 CSV 저장
"""
import sys
import csv
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from rx_analyzer import DrugDataStore, run_analysis, aggregate
from tess_analyzer import TesseractImageAnalyzer

INPUT_DIR  = Path(r"C:\Users\JW\Desktop\정원유니어스\02.마감\05월 마감")
OUTPUT_DIR = Path(r"C:\Users\JW\Desktop\정원유니어스\02.마감\05월 마감\3.입력완료")


def group_files_by_clinic(folder: Path) -> dict[str, list[Path]]:
    """파일명 첫 단어(의원명)로 그룹핑. JPG/PNG 모두 지원."""
    groups: dict[str, list[Path]] = defaultdict(list)
    for ext in ('*.jpg', '*.jpeg', '*.png'):
        for p in sorted(folder.glob(ext)):
            clinic = p.stem.split()[0] if ' ' in p.stem else p.stem
            groups[clinic].append(p)
    return dict(groups)


def save_csv(store: DrugDataStore, clinic: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{clinic}_5월_분석결과.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["제약사", "품목명", "통계수량", "소모수량", "합계"])
        for company in store.companies():
            for drug in store.drugs(company):
                s, u = store.totals(company, drug)
                w.writerow([company, drug, s or 0, u or 0, s + u])
            w.writerow([f"{company} 소계", "", "", "", store.company_total(company)])
            w.writerow([])
    return out_path


def main(target_clinic: str | None = None) -> None:
    analyzer = TesseractImageAnalyzer()

    groups = group_files_by_clinic(INPUT_DIR)

    if not groups:
        print(f"[오류] {INPUT_DIR} 폴더에 이미지 파일이 없습니다.")
        return

    if target_clinic:
        groups = {k: v for k, v in groups.items() if target_clinic in k}
        if not groups:
            print(f"[오류] '{target_clinic}' 의원 파일 없음. 전체 목록: {list(groups.keys())}")
            return

    for clinic, files in groups.items():
        print(f"\n{'='*55}")
        print(f"[{clinic}] {len(files)}개 파일 분석 시작")
        store = DrugDataStore()
        failed = []

        for i, f in enumerate(files):
            print(f"  ({i+1}/{len(files)}) {f.name} ...", end=' ', flush=True)
            try:
                data = analyzer.analyze(str(f))
                if data:
                    # 회사명 미인식 시 파일명으로 구분
                    if data.get('company') == '미인식':
                        data['company'] = f"미인식_{f.stem.replace(' ', '')}"
                    aggregate(data, store)
                    print(f"✓  회사={data['company']}  {len(data['items'])}개 품목")
                else:
                    print("✗  데이터 추출 실패")
                    failed.append(f.name)
            except Exception as e:
                print(f"✗  오류: {e}")
                failed.append(f.name)

        if failed:
            print(f"\n  [주의] 분석 실패 파일 {len(failed)}개: {', '.join(failed)}")

        if store.is_empty():
            print(f"  [경고] 추출된 데이터 없음 — CSV 저장 생략")
            continue

        out = save_csv(store, clinic, OUTPUT_DIR)

        print(f"\n  ▶ 결과 요약: {len(store.companies())}개 제약사  "
              f"{store.item_count()}개 품목  합계 {store.grand_total():,}정")
        print(f"  ▶ CSV 저장: {out}")
        print()
        print(f"  {'제약사':<22} {'품목명':<30} {'통계':>6} {'소모':>6} {'합계':>7}")
        print(f"  {'-'*70}")
        for company in store.companies():
            for i, drug in enumerate(store.drugs(company)):
                s, u = store.totals(company, drug)
                label = company if i == 0 else ''
                print(f"  {label:<22} {drug:<30} {s or '-':>6} {u or '-':>6} {s+u:>7,}")
            print(f"  {'':22} {'[소계]':>30} {'':>6} {'':>6} "
                  f"{store.company_total(company):>7,}")
            print()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    main(target)
