"""tess_analyzer 분석 결과 확인"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tess_analyzer import TesseractImageAnalyzer

BASE = Path(r'C:\Users\JW\Desktop\정원유니어스\02.마감\05월 마감')
analyzer = TesseractImageAnalyzer()

for n in range(1, 9):
    path = BASE / f'서린 ({n}).jpg'
    if not path.exists():
        print(f'\n서린 ({n}).jpg  — 파일 없음')
        continue
    print(f'\n{"="*55}')
    print(f'서린 ({n}).jpg')
    result = analyzer.analyze(str(path))
    if not result:
        print('  → 분석 실패 (회사명 또는 약품 없음)')
        continue
    print(f'  회사명: {result["company"]}')
    total = 0
    for item in result['items']:
        print(f'    {item["name"]:<35} {item["quantity"]:>6,}')
        total += item['quantity']
    print(f'  {"합계":>37} {total:>6,}')
