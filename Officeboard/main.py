import os
import io
import json
import re
import threading
import webbrowser
from contextlib import contextmanager
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
app.config['SESSION_COOKIE_SECURE'] = bool(os.environ.get('RAILWAY_ENVIRONMENT'))
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

# ── 스토리지 어댑터 ──────────────────────────────────────────────────────────
# PostgreSQL 어댑터와 JSON 파일 어댑터를 load_data/store_data 뒤에 숨깁니다.
# 라우트 핸들러는 어느 스토리지가 활성화됐는지 알 필요 없습니다.

@contextmanager
def _pg_conn():
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_data() -> dict:
    if DATABASE_URL:
        with _pg_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT data FROM office_data WHERE id = 1")
            row = cur.fetchone()
            return row[0] if row else {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def store_data(payload: str) -> None:
    if DATABASE_URL:
        with _pg_conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE office_data SET data = %s WHERE id = 1", (payload,))
    else:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            f.write(payload)


def init_db():
    if not DATABASE_URL:
        return
    with _pg_conn() as conn:
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


init_db()

# ── 인증 ────────────────────────────────────────────────────────────────────

_API_PATHS = ('/data', '/export', '/import', '/ping')


@app.before_request
def require_login():
    if not APP_PASSWORD:
        return
    if request.endpoint == 'login':
        return
    if not session.get('authenticated'):
        # API 엔드포인트는 302 redirect 대신 401 반환
        # → fetch()가 Content-Type 검사 없이 정확히 감지 가능
        if any(request.path.startswith(p) for p in _API_PATHS):
            return '', 401
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

# ── 헬스체크 ─────────────────────────────────────────────────────────────────

@app.route('/ping')
def ping():
    storage = 'postgres' if DATABASE_URL else 'file'
    if DATABASE_URL:
        try:
            with _pg_conn() as conn:
                conn.cursor().execute("SELECT 1")
        except Exception as e:
            return json.dumps({'ok': False, 'storage': storage, 'error': str(e)}), 500, \
                   {'Content-Type': 'application/json'}
    return json.dumps({'ok': True, 'storage': storage}), 200, {'Content-Type': 'application/json'}

# ── 데이터 API ───────────────────────────────────────────────────────────────

_JSON_HEADERS = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
}


@app.route('/data', methods=['GET'])
def get_data():
    try:
        body = json.dumps(load_data(), ensure_ascii=False)
        return body, 200, _JSON_HEADERS
    except Exception as e:
        return str(e), 500


@app.route('/data', methods=['POST'])
def save_data():
    raw = request.get_data(as_text=True)
    try:
        store_data(raw)
    except Exception as e:
        return str(e), 500
    return '', 204

# ── 엑셀 내보내기 ────────────────────────────────────────────────────────────

@app.route('/export', methods=['POST'])
def export_excel():
    body = request.get_json(force=True)
    data: dict = body.get('data', {})
    month: str = body.get('month', '')

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

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    today_str = datetime.now().strftime('%y%m%d')
    filename = f'{today_str} 공유오피스 운영 대시보드 백업.xlsx'
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )

# ── 엑셀 가져오기 ────────────────────────────────────────────────────────────

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

        return json.dumps(data, ensure_ascii=False), 200, {'Content-Type': 'application/json'}

    except Exception as e:
        return str(e), 400

# ── 로컬 실행 ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'dashboard.html')


def open_browser():
    webbrowser.open(f'http://127.0.0.1:{PORT}')


if __name__ == '__main__':
    threading.Timer(1.2, open_browser).start()
    app.run(host='127.0.0.1', port=PORT, debug=False)
