import os
import sys
import io
import json
import threading
import webbrowser
from datetime import date, datetime

from flask import Flask, send_from_directory, request, send_file, session, redirect

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')
PORT = 5050
DATABASE_URL = os.environ.get('DATABASE_URL')
APP_PASSWORD = os.environ.get('APP_PASSWORD')
SECRET_KEY = os.environ.get('SECRET_KEY', 'local-dev-key')

app = Flask(__name__)
app.secret_key = SECRET_KEY


@app.before_request
def require_login():
    if not APP_PASSWORD:
        return
    if request.endpoint == 'login':
        return
    if not session.get('authenticated'):
        return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == APP_PASSWORD:
            session['authenticated'] = True
            return redirect('/')
        return redirect('/login?error=1')
    return send_from_directory(BASE_DIR, 'login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


def _db_conn():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        return
    conn = _db_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS office_data (
            id INTEGER PRIMARY KEY,
            data JSONB NOT NULL DEFAULT '{}'
        )
    """)
    cur.execute("""
        INSERT INTO office_data (id, data) VALUES (1, '{}')
        ON CONFLICT (id) DO NOTHING
    """)
    conn.commit()
    cur.close()
    conn.close()


init_db()


@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'dashboard.html')


@app.route('/data', methods=['GET'])
def get_data():
    try:
        if DATABASE_URL:
            conn = _db_conn()
            cur = conn.cursor()
            cur.execute("SELECT data FROM office_data WHERE id = 1")
            row = cur.fetchone()
            cur.close()
            conn.close()
            return json.dumps(row[0] if row else {}), 200, {'Content-Type': 'application/json'}
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return f.read(), 200, {'Content-Type': 'application/json'}
        return '{}', 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return str(e), 500


@app.route('/data', methods=['POST'])
def save_data():
    raw = request.get_data(as_text=True)
    try:
        if DATABASE_URL:
            conn = _db_conn()
            cur = conn.cursor()
            cur.execute("UPDATE office_data SET data = %s WHERE id = 1", (raw,))
            conn.commit()
            cur.close()
            conn.close()
        else:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                f.write(raw)
    except Exception as e:
        return str(e), 500
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


def _to_date_str(val):
    if val is None:
        return ''
    if isinstance(val, (date, datetime)):
        return val.strftime('%Y-%m-%d')
    s = str(val).strip()
    return s.split(' ')[0] if ' ' in s else s


@app.route('/import', methods=['POST'])
def import_excel():
    try:
        file = request.files.get('file')
        if not file:
            return 'No file', 400

        wb = openpyxl.load_workbook(file, data_only=True)
        ws = wb.active

        headers = [str(c.value).strip() if c.value else '' for c in ws[1]]

        # 납부 컬럼에서 월 추출 (예: "2026-05 납부" → "2026-05")
        paid_col_idx = None
        paid_month = None
        for i, h in enumerate(headers):
            if '납부' in h:
                paid_col_idx = i
                paid_month = h.replace('납부', '').strip()
                break

        col = {h: i for i, h in enumerate(headers)}

        data = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            room_id = str(row[col.get('호실', 0)] or '').strip()
            if not room_id:
                continue

            name = str(row[col.get('입주자', 2)] or '').strip()
            display_name = str(row[col.get('표시명', 1)] or '').strip()

            if not name and not display_name:
                continue

            rent_val = row[col.get('월세(원)', 6)]
            try:
                rent = int(float(str(rent_val))) if rent_val else 0
            except (ValueError, TypeError):
                rent = 0

            entry = {
                'displayName': display_name,
                'name': name,
                'phone': str(row[col.get('연락처', 3)] or '').strip(),
                'start': _to_date_str(row[col.get('계약시작', 4)]),
                'end': _to_date_str(row[col.get('계약종료', 5)]),
                'rent': rent,
                'contractType': str(row[col.get('계약유형', 7)] or '입주').strip(),
                'memo': str(row[col.get('메모', 9)] or '').strip(),
            }

            if paid_month and paid_col_idx is not None:
                paid_val = row[paid_col_idx]
                entry['paid_' + paid_month] = (str(paid_val).strip() == '완납')

            data[room_id] = entry

        return json.dumps(data, ensure_ascii=False), 200, {'Content-Type': 'application/json'}

    except Exception as e:
        return str(e), 400


def open_browser():
    webbrowser.open(f'http://127.0.0.1:{PORT}')


if __name__ == '__main__':
    threading.Timer(1.2, open_browser).start()
    app.run(host='127.0.0.1', port=PORT, debug=False)
