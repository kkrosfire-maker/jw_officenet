"""카카오비즈니스센터 자동화: 소식 발행 + 채널 메시지 작성(발송 직전까지)."""
import os

from playwright.sync_api import BrowserContext, Page

from paths import DATA_DIR

BASE = "https://business.kakao.com/space/892922/channel/_dlxfxcG/"
PROFILE = os.path.join(DATA_DIR, "profile")

MSG_TEMPLATE = (
    "안녕하십니까\n정원유니어스(주) 입니다.\n\n"
    "{date}일 공지사항 전달 드립니다.\n\n"
    "{body}\n\n"
    "자세한 내용은 하단의 공지사항을 확인해주세요.\n감사합니다."
)
MSG_LIMIT = 300  # 이미지 첨부 시 내용 제한


def open_context(p, headless=False) -> BrowserContext:
    return p.chromium.launch_persistent_context(
        PROFILE, channel="chrome", headless=headless, viewport={"width": 1400, "height": 1000}
    )


def is_logged_in(page: Page) -> bool:
    page.goto(BASE + "posts", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    return "/posts" in page.url and "login" not in page.url


def blocks(body: str) -> str:
    """'▶' 줄 앞에 빈 줄을 넣어 항목 블록을 구분한다. (이미 정리된 텍스트에 다시 적용해도 같은 결과)"""
    out = []
    for ln in body.splitlines():
        ln = ln.rstrip()
        if not ln:
            continue
        if ln.startswith("▶") and out:
            out.append("")
        out.append(ln)
    return "\n".join(out)


def build_message(date: str, body: str) -> str:
    return MSG_TEMPLATE.format(date=date, body=blocks(body))


def write_post(page: Page, date: str, body: str, images: list[str], submit: bool = False) -> None:
    """소식 작성 화면을 채운다. submit=True 일 때만 '등록'을 누른다."""
    # 2026-10 개편: 작성 화면이 posts/new 로 분리, 기본이 '카드형'(제목 없음)이라 '블로그형'을 고른다.
    page.goto(BASE + "posts/new", wait_until="domcontentloaded")
    page.get_by_text("블로그형", exact=True).first.click()
    page.wait_for_selector("input#title", timeout=20000)
    page.fill("input#title", f"{date} 공지사항")
    page.fill("textarea#description", blocks(body))
    if images:
        page.locator("input[type='file']").first.set_input_files(images)
        page.wait_for_timeout(1500 + 600 * len(images))
    if submit:
        page.locator("button.g_emph:has-text('등록')").first.click()
        page.wait_for_timeout(4000)


def write_message(page: Page, date: str, body: str, click_next: bool = False) -> str:
    """직전 메시지를 복사해 내용·소식 첨부를 교체한다. 발송 직전(다음 버튼 앞)에서 멈춘다.
    복사본에서 정보성/로고 이미지/버튼 설정이 그대로 유지된다."""
    text = build_message(date, body)
    if len(text) > MSG_LIMIT:
        raise ValueError(f"메시지가 {len(text)}자로 {MSG_LIMIT}자를 넘습니다. 발췌문을 줄여 주세요.")
    page.goto(BASE + "messages/new/feed", wait_until="domcontentloaded")
    page.get_by_text("이전 메시지 불러오기").first.click()
    page.get_by_text("복사해서 작성").first.click()
    page.wait_for_selector("textarea[name='messageWrite']", timeout=20000)
    page.wait_for_timeout(1500)
    page.fill("textarea[name='messageWrite']", text)
    # 소식 첨부 교체: 삭제 -> 불러오기 -> 해당 날짜 소식 선택
    page.get_by_text("소식 첨부 :").first.locator("xpath=following::button[1]").click()
    page.get_by_role("button", name="불러오기", exact=True).click()
    title = page.get_by_text(f"{date} 공지사항", exact=True).first
    title.wait_for(timeout=15000)
    title.locator("xpath=following::button[normalize-space()='선택'][1]").click()
    page.wait_for_timeout(1500)
    if click_next:
        page.get_by_role("button", name="다음").click()
        page.wait_for_timeout(3000)
    return text
