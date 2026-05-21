import os
import sys
import io
import json
import threading
import webbrowser

from flask import Flask, send_from_directory, request, send_file

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')
PORT = 5050

app = Flask(__name__)


@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'dashboard.html')


@app.route('/data', methods=['GET'])
def get_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return f.read(), 200, {'Content-Type': 'application/json'}
    return '{}', 200, {'Content-Type': 'application/json'}


@app.route('/data', methods=['POST'])
def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        f.write(request.get_data(as_text=True))
    return '', 204


@app.route('/export', methods=['POST'])
def export_excel():
    body = request.get_json(force=True)
    data: dict = body.get('data', {})
    month: str = body.get('month', '')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '입주현황'

    # ── 헤더 ──────────────────────────────────────────
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill('solid', fgColor='2C2C2C')
    header_align = Alignment(horizontal='center', vertical='center')

    headers = [
        '호실', '표시명', '입주자', '연락처',
        '계약시작', '계약종료', '월세(원)', '계약유형',
        f'{month} 납부', '메모',
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
    ws.row_dimensions[1].height = 20

    # ── 데이터 ────────────────────────────────────────
    paid_key = f'paid_{month}'
    for row_idx, room_id in enumerate(sorted(data.keys()), 2):
        d = data[room_id]
        if d.get('name'):
            paid_val = '완납' if d.get(paid_key) else '미납'
        else:
            paid_val = ''
        row_data = [
            room_id,
            d.get('displayName', ''),
            d.get('name', ''),
            d.get('phone', ''),
            d.get('start', ''),
            d.get('end', ''),
            d.get('rent', 0) or '',
            d.get('contractType', ''),
            paid_val,
            d.get('memo', ''),
        ]
        for col, val in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col, value=val)

    # ── 열 너비 자동 조정 ─────────────────────────────
    for col in ws.columns:
        width = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = width + 4

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f'공유오피스_입주현황_{month}.xlsx'
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


def open_browser():
    webbrowser.open(f'http://127.0.0.1:{PORT}')


if __name__ == '__main__':
    threading.Timer(1.2, open_browser).start()
    app.run(host='127.0.0.1', port=PORT, debug=False)
