"""카카오비즈니스센터 자동화: 소식 발행 + 채널 메시지 작성(발송 직전까지)."""
import os
import re

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


def has_post(page: Page, date: str) -> bool:
    """'내 소식' 목록이 다 뜬 뒤 '{date} 공지사항' 소식이 있는지 확인한다."""
    page.goto(BASE + "posts", wait_until="domcontentloaded")
    # 목록 항목 메뉴 버튼 이름이 '소식 관리 메뉴' <-> '더보기 메뉴'로 수시로 바뀐다 (2026-10 두 번).
    # 이름에 기대지 않도록 '...메뉴' 버튼 또는 '공지사항' 제목 중 먼저 뜨는 것을 기다린다.
    menu = page.get_by_role("button", name=re.compile(r"메뉴$"))
    item = page.get_by_text(re.compile(r"^\d{1,2}/\d{1,2} 공지사항$"))
    menu.or_(item).first.wait_for(timeout=20000)
    page.wait_for_timeout(1000)
    return page.get_by_text(f"{date} 공지사항", exact=True).count() > 0


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
    # 카카오 화면이 수시로 바뀐다: posts/new(카드형/블로그형 선택) 또는 posts(제목+본문 바로 입력) 둘 다 대응.
    page.goto(BASE + "posts/new", wait_until="domcontentloaded")
    title_box = page.locator("input#title, input[placeholder='제목']").first
    blog = page.get_by_text("블로그형", exact=True).first
    page.wait_for_selector("input#title, input[placeholder='제목'], :text-is('블로그형')", timeout=20000)
    if blog.count() > 0 and blog.is_visible():
        blog.click()
    title_box.wait_for(timeout=20000)
    title_box.fill(f"{date} 공지사항")
    page.locator("textarea#description, textarea[placeholder*='새 이야기']").first.fill(blocks(body))
    if images:
        page.locator("input[type='file']").first.set_input_files(images)
        page.wait_for_timeout(1500 + 600 * len(images))
    if submit:
        page.locator("button.g_emph:has-text('등록'), button[type='submit']:has-text('등록')").first.click()
        # 2026-10: '일부 친구는 작성한 소식을 볼 수 없어요'(최신 카카오톡 전용 안내) 확인창이 뜬다.
        notice = page.locator(".layer_body:has-text('일부 친구는')")
        try:
            notice.wait_for(timeout=5000)
            notice.locator("xpath=ancestor-or-self::*[.//button[normalize-space()='확인']][1]") \
                .get_by_role("button", name="확인", exact=True).click()
        except Exception:
            pass  # 확인창이 안 뜨는 경우
        page.wait_for_timeout(5000)  # 업로드·발행 처리 (발행 후에도 주소는 posts/new 그대로)
        # 실제 발행 여부는 '내 소식' 목록에 제목이 보이는지로 확인한다.
        if not has_post(page, date):
            raise RuntimeError(f"'{date} 공지사항' 소식이 목록에 보이지 않습니다. 발행되지 않았을 수 있습니다.")


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
