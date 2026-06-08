"""엑셀 파싱/내보내기 로직. Flask 라우트와 완전히 분리."""
import re
from datetime import date, datetime

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment


def _to_date_str(val) -> str:
    if val is None:
        return ''
    if isinstance(val, (date, datetime)):
        return val.strftime('%Y-%m-%d')
    s = str(val).strip()
    return s.split(' ')[0] if ' ' in s else s


def parse_workbook(wb: openpyxl.Workbook) -> dict:
    """openpyxl Workbook → 대시보드 data dict 변환.

    Returns:
        {"호실ID": {...entry...}, ...}
    """
    data = {}
    for ws in wb.worksheets:
        headers = [str(c.value).strip() if c.value else '' for c in ws[1]]
        if '호실' not in headers:
            continue

        paid_col_idx = None
        paid_month = None
        for i, h in enumerate(headers):
            if '납부' in h:
                paid_col_idx = i
                paid_month = h.replace('납부', '').strip()
                break

        col = {h: i for i, h in enumerate(headers)}

        for row in ws.iter_rows(min_row=2, values_only=True):
            room_id = str(row[col.get('호실', 0)] or '').strip()
            if not room_id:
                continue

            name = str(row[col.get('상호명', col.get('입주자', 1))] or '').strip()
            tenant_name = str(row[col.get('입주자 이름', col.get('입주자', 2))] or '').strip()
            if not name and not tenant_name:
                continue

            rent_col = col.get('월세(원)')
            rent_val = row[rent_col] if rent_col is not None else None
            try:
                rent = int(float(str(rent_val))) if rent_val else 0
            except (ValueError, TypeError):
                rent = 0

            vat_col = col.get('VAT')
            vat_str = str(row[vat_col] or '') if vat_col is not None else ''
            vat = (vat_str.strip() == '유')

            disc_col = col.get('할인율')
            discount_str = str(row[disc_col] or '').strip() if disc_col is not None else ''
            if discount_str and discount_str != '표준가' and discount_str.endswith('%'):
                try:
                    discount = float(discount_str.replace('%', '')) / 100
                except (ValueError, TypeError):
                    discount = 0.0
            else:
                discount = 0.0

            contract_type = str(row[col.get('계약유형', 9)] or '입주').strip()
            if re.match(r'^V\d+$', room_id):
                contract_type = '비상주'

            entry = {
                'name': name,
                'tenantName': tenant_name,
                'phone': str(row[col.get('연락처', 3)] or '').strip(),
                'start': _to_date_str(row[col.get('계약시작', 4)]),
                'end': _to_date_str(row[col.get('계약종료', 5)]),
                'vat': vat,
                'discount': discount,
                'rent': rent,
                'contractType': contract_type,
                'memo': str(row[col.get('메모', 11)] or '').strip(),
            }

            if '계약상태' in col:
                cs = str(row[col['계약상태']] or '').strip()
                if cs in ('계약중', '계약만료', '계약해지'):
                    entry['contractStatus'] = cs

            if paid_month and paid_col_idx is not None:
                paid_val = row[paid_col_idx]
                entry['paid_' + paid_month] = (str(paid_val).strip() == '완납')

            data[room_id] = entry

    return data


def build_workbook(data: dict, month: str) -> openpyxl.Workbook:
    """data dict → 엑셀 Workbook 생성 (export 용)."""
    headers = [
        '호실', '상호명', '입주자 이름', '연락처',
        '계약시작', '계약종료', 'VAT', '할인율', '월세(원)', '계약유형',
        f'{month} 납부', '메모',
    ]
    paid_key = f'paid_{month}'
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill('solid', fgColor='2C2C2C')
    header_align = Alignment(horizontal='center', vertical='center')

    def write_sheet(ws, room_ids, extra_col=None):
        sheet_headers = headers + ([extra_col] if extra_col else [])
        for col, h in enumerate(sheet_headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
        ws.row_dimensions[1].height = 20
        for row_idx, room_id in enumerate(sorted(room_ids), 2):
            d = data[room_id]
            if d.get('name') or d.get('tenantName'):
                paid_val = '완납' if (d.get('prepaid') or d.get(paid_key)) else '미납'
            else:
                paid_val = ''
            discount_pct = int(float(d.get('discount', 0)) * 100)
            discount_str = f'{discount_pct}%' if discount_pct else '표준가'
            row_data = [
                room_id, d.get('name', ''), d.get('tenantName', ''),
                d.get('phone', ''), d.get('start', ''), d.get('end', ''),
                '유' if d.get('vat') else '무', discount_str,
                d.get('rent', 0) or '', d.get('contractType', ''),
                paid_val, d.get('memo', ''),
            ]
            if extra_col == '계약상태':
                row_data.append(d.get('contractStatus', '계약중'))
            for col, val in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col, value=val)
        for col in ws.columns:
            width = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = width + 4

    resident_ids = [r for r in data if data[r].get('contractType') != '비상주']
    virtual_ids  = [r for r in data if data[r].get('contractType') == '비상주']

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = '상주'
    write_sheet(ws1, resident_ids)

    ws2 = wb.create_sheet('비상주')
    write_sheet(ws2, virtual_ids, extra_col='계약상태')
    return wb
