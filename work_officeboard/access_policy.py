"""요청 접근 정책 결정 테이블. Flask/session에 의존하지 않는 순수 함수.

main.py의 require_login()은 이 함수의 결과를 Flask 응답으로 옮기기만 하는
얇은 어댑터다 — 실제 "누구를 어디로 보낼지" 판단은 전부 여기 있다.
"""

API_PATHS = ('/data', '/export', '/import', '/ping')
PUBLIC_FILES = ('/office-domain.js',)


def decide_access(path: str, endpoint: str | None, authenticated: bool,
                   password_configured: bool) -> str:
    """반환값: 'allow' | 'api_401' | 'redirect_login'."""
    if not password_configured:
        return 'allow'
    if endpoint == 'login':
        return 'allow'
    if path in PUBLIC_FILES:
        return 'allow'
    if authenticated:
        return 'allow'
    if any(path.startswith(p) for p in API_PATHS):
        return 'api_401'
    return 'redirect_login'
