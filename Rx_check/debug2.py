"""이미지 8 및 전체 결과 상세 디버그"""
import sys, re, os
from pathlib import Path
import pytesseract
from PIL import Image, ImageEnhance

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
os.environ['TESSDATA_PREFIX'] = os.path.expanduser('~/tessdata')
_CFG = '--psm 6 --oem 3'

BASE = Path(r'C:\Users\JW\Desktop\정원유니어스\02.마감\05월 마감')


def analyze_image(n):
    path = BASE / f'서린 ({n}).jpg'
    if not path.exists():
        print(f'파일 없음: {path}')
        return
    img = Image.open(path).convert('RGB')
    img = ImageEnhance.Contrast(img).enhance(1.4)
    w, h = img.size

    raw = pytesseract.image_to_data(img, lang='kor+eng', config=_CFG,
                                     output_type=pytesseract.Output.DICT)
    full_text = pytesseract.image_to_string(img, lang='kor+eng', config=_CFG)

    print(f'\n{"="*60}')
    print(f'서린 ({n}).jpg  크기={w}x{h}')

    print('\n[image_to_string 앞 12줄]')
    for line in full_text.split('\n')[:12]:
        if line.strip():
            print(f'  {repr(line.strip())}')

    words = []
    for i in range(len(raw['text'])):
        txt = raw['text'][i].strip()
        conf = raw['conf'][i]
        if conf > 10 and txt:
            words.append({
                'text': txt, 'x': raw['left'][i], 'y': raw['top'][i],
                'rel_x': raw['left'][i] / w, 'rel_y': raw['top'][i] / h,
            })

    s = sorted(words, key=lambda x: x['y'])
    rows = [[s[0]]] if s else []
    for wrd in s[1:]:
        avg_y = sum(x['y'] for x in rows[-1]) / len(rows[-1])
        if abs(wrd['y'] - avg_y) <= 12:
            rows[-1].append(wrd)
        else:
            rows.append([wrd])
    rows = [sorted(r, key=lambda x: x['x']) for r in rows]

    print('\n[약품코드(0.22~0.38) + 총사용량(0.58~0.64) 행]')
    for row in rows:
        avg_rel_y = sum(wrd['rel_y'] for wrd in row) / len(row)
        if not (0.12 < avg_rel_y < 0.62):
            continue
        codes = [wrd for wrd in row
                 if 0.22 <= wrd['rel_x'] <= 0.38
                 and re.fullmatch(r'\d{2,10}', wrd['text'])]
        qtys = [wrd for wrd in row
                if 0.58 <= wrd['rel_x'] <= 0.64
                and re.fullmatch(r'[\d,.]+', wrd['text'])]
        if codes or qtys:
            rt = ' '.join(wrd['text'] for wrd in row[:7])
            code_str = ','.join(wrd['text'] for wrd in codes)
            qty_str = ','.join(f'{wrd["text"]}(rx={wrd["rel_x"]:.3f})' for wrd in qtys)
            print(f'  rel_y={avg_rel_y:.2f}  code=[{code_str}]  qty=[{qty_str}]  row={rt!r}')


# 이미지 7과 8만 집중 분석
for n in [7, 8]:
    analyze_image(n)
