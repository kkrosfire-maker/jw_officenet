import os
import io
import json
import threading
import webbrowser
from datetime import datetime

from flask import Flask, send_from_directory, request, send_file, session, redirect

import openpyxl
from excel_io import parse_workbook, build_workbook
from storage import get_storage

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

storage = get_storage(DATABASE_URL, DATA_FILE)
storage.init()

# ── 인증 ────────────────────────────────────────────────────────────────────

_API_PATHS = ('/data', '/export', '/import', '/ping')


_PUBLIC_FILES = ('/office-domain.js',)

@app.before_request
def require_login():
    if not APP_PASSWORD:
        return
    if request.endpoint == 'login':
        return
    if request.path in _PUBLIC_FILES:
        return
    if not session.get('authenticated'):
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
    ok, error = storage.ping()
    if not ok:
        return json.dumps({'ok': False, 'storage': storage.name, 'error': error}), 500, \
               {'Content-Type': 'application/json'}
    return json.dumps({'ok': True, 'storage': storage.name}), 200, {'Content-Type': 'application/json'}

# ── 데이터 API ───────────────────────────────────────────────────────────────

_JSON_HEADERS = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
}


@app.route('/data', methods=['GET'])
def get_data():
    try:
        body = json.dumps(storage.load(), ensure_ascii=False)
        return body, 200, _JSON_HEADERS
    except Exception as e:
        return str(e), 500


@app.route('/data', methods=['POST'])
def save_data():
    raw = request.get_data(as_text=True)
    try:
        json.loads(raw)
    except json.JSONDecodeError as e:
        return f'잘못된 JSON 형식: {e}', 400
    try:
        storage.save(raw)
    except Exception as e:
        return str(e), 500
    return '', 204

# ── 엑셀 내보내기 ────────────────────────────────────────────────────────────

@app.route('/export', methods=['POST'])
def export_excel():
    body = request.get_json(force=True)
    data: dict = body.get('data', {})
    month: str = body.get('month', '')

    wb = build_workbook(data, month)
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

@app.route('/import', methods=['POST'])
def import_excel():
    try:
        file = request.files.get('file')
        if not file:
            return 'No file', 400
        wb = openpyxl.load_workbook(file, data_only=True)
        data = parse_workbook(wb)
        return json.dumps(data, ensure_ascii=False), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return str(e), 400

# ── 로컬 실행 ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'dashboard.html')


@app.route('/office-domain.js')
def office_domain():
    return send_from_directory(BASE_DIR, 'office-domain.js')


@app.route('/dashboard.js')
def dashboard_js():
    return send_from_directory(BASE_DIR, 'dashboard.js')


def open_browser():
    webbrowser.open(f'http://127.0.0.1:{PORT}')


if __name__ == '__main__':
    threading.Timer(1.2, open_browser).start()
    app.run(host='127.0.0.1', port=PORT, debug=False)
