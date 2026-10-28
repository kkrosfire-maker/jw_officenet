"""카카오비즈니스센터 로그인용 창을 띄운다. 세션은 profile/ 에 저장된다. 로그인 후 창을 닫으면 종료."""
import os

from playwright.sync_api import sync_playwright

PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile")

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=False, no_viewport=True, chromium_sandbox=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://business.kakao.com/")
    print("로그인 후 창을 닫아 주세요.")
    ctx.wait_for_event("close", timeout=0)
