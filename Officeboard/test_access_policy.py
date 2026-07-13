"""
회귀 테스트 — access_policy.py 결정 테이블
실행: python test_access_policy.py

Flask 요청 컨텍스트 없이 decide_access() 하나만으로 인증 정책을
전부 검증한다.
"""
import sys

sys.stdout.reconfigure(encoding='utf-8')

from access_policy import decide_access

pass_count = 0
fail_count = 0


def check(label, path, endpoint, authenticated, password_configured, expected):
    global pass_count, fail_count
    actual = decide_access(path, endpoint, authenticated, password_configured)
    ok = actual == expected
    mark = '✓' if ok else '✗ FAIL'
    print(f'  {mark} {label}: got={actual!r} expected={expected!r}')
    if ok:
        pass_count += 1
    else:
        fail_count += 1


def main():
    print('[비밀번호 미설정] 무엇을 하든 항상 allow')
    check('/data, 미인증', '/data', 'get_data', False, False, 'allow')
    check('/, 미인증', '/', 'index', False, False, 'allow')

    print('\n[로그인 페이지] endpoint가 login이면 allow')
    check('/login GET', '/login', 'login', False, True, 'allow')

    print('\n[퍼블릭 파일] office-domain.js는 인증 없이 allow')
    check('/office-domain.js', '/office-domain.js', 'office_domain', False, True, 'allow')

    print('\n[인증됨] 어느 경로든 allow')
    check('/data, 인증됨', '/data', 'get_data', True, True, 'allow')
    check('/, 인증됨', '/', 'index', True, True, 'allow')

    print('\n[미인증 + API 경로] 401')
    for p in ('/data', '/export', '/import', '/ping'):
        check(f'{p}, 미인증', p, p.strip("/"), False, True, 'api_401')

    print('\n[미인증 + 페이지 경로] 로그인으로 리다이렉트')
    check('/, 미인증', '/', 'index', False, True, 'redirect_login')
    check('/dashboard.js, 미인증', '/dashboard.js', 'dashboard_js', False, True, 'redirect_login')

    print(f'\n결과: PASS {pass_count} / FAIL {fail_count}')
    sys.exit(1 if fail_count else 0)


if __name__ == '__main__':
    main()
