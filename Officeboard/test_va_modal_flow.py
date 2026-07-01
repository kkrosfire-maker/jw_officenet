"""
회귀 테스트 — 비상주 등록/수정 모달 내비게이션
실행: python main.py 로 서버를 띄운 뒤 (localhost:5050) 별도 창에서 python test_va_modal_flow.py

버그: 비상주 "목록"에서 고객을 열어 저장/취소하면 목록으로 돌아와야 하는데
      대시보드 첫 화면으로 빠지던 문제 (dashboard.js openVirtualAdd/closeVirtualAdd).
      dashboard.js는 순수 함수 seam이 없는 DOM 결합 코드라 test_bugs.js(node, DOM 없음)로는
      재현이 불가능 — 이 파일은 Playwright로 실제 브라우저를 구동해 그 seam을 대신한다.
"""
import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = 'http://127.0.0.1:5050'

pass_count = 0
fail_count = 0


def assert_state(label, actual, expected):
    global pass_count, fail_count
    ok = actual == expected
    mark = '✓' if ok else '✗ FAIL'
    print(f'  {mark} {label}: got={actual} expected={expected}')
    if ok:
        pass_count += 1
    else:
        fail_count += 1


def overlay_state(page):
    add_active = page.eval_on_selector('#virtual-add-overlay', 'el => el.classList.contains("active")')
    list_active = page.eval_on_selector('#virtual-modal-overlay', 'el => el.classList.contains("active")')
    return add_active, list_active


def main():
    global fail_count
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors = []
        page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)

        try:
            page.goto(BASE_URL, timeout=5000)
        except Exception as e:
            print(f'서버에 접속할 수 없습니다 ({BASE_URL}). 먼저 `python main.py`로 서버를 띄워주세요.')
            print(f'상세: {e}')
            sys.exit(2)
        page.wait_for_timeout(800)

        # 케이스 1: 목록 -> 행 클릭(수정) -> 취소 -> 목록으로 복귀해야 함
        print('\n[케이스 1] 목록 -> 수정 -> 취소 -> 목록 복귀')
        page.click("div.stat-card:has-text('비상주')")
        page.wait_for_timeout(300)
        page.click('table.virtual-table tbody tr:first-child')
        page.wait_for_timeout(300)
        page.click('#virtual-add-overlay button.btn-cancel')
        page.wait_for_timeout(400)
        assert_state('취소 후 (등록모달, 목록)', overlay_state(page), (False, True))
        page.click('#virtual-modal-overlay .btn-close')
        page.wait_for_timeout(300)

        # 케이스 2: 목록 -> 행 클릭(수정) -> 저장 -> 목록으로 복귀해야 함
        print('\n[케이스 2] 목록 -> 수정 -> 저장 -> 목록 복귀')
        page.click("div.stat-card:has-text('비상주')")
        page.wait_for_timeout(300)
        page.click('table.virtual-table tbody tr:first-child')
        page.wait_for_timeout(300)
        page.click('#virtual-add-overlay button.btn-primary')
        page.wait_for_timeout(600)
        assert_state('저장 후 (등록모달, 목록)', overlay_state(page), (False, True))
        page.click('#virtual-modal-overlay .btn-close')
        page.wait_for_timeout(300)

        # 케이스 3: 대시보드에서 바로 등록 -> 취소 -> 목록이 뜨면 안 됨 (목록을 연 적 없으므로)
        print('\n[케이스 3] 대시보드 직접 등록 -> 취소 -> 대시보드 유지')
        page.click("button:has-text('비상주 등록하기')")
        page.wait_for_timeout(300)
        page.click('#virtual-add-overlay button.btn-cancel')
        page.wait_for_timeout(400)
        assert_state('취소 후 (등록모달, 목록)', overlay_state(page), (False, False))

        if console_errors:
            print('\n콘솔 에러 발생:')
            for e in console_errors:
                print('  ', e)
            fail_count += len(console_errors)

        browser.close()

    print(f'\n결과: PASS {pass_count} / FAIL {fail_count}')
    sys.exit(1 if fail_count else 0)


if __name__ == '__main__':
    main()
