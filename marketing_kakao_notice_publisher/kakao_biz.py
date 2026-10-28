"""카카오비즈니스센터 자동화: 소식 발행 + 채널 메시지 작성(발송 직전까지)."""
import os
import re
import shutil
import time
from typing import Callable, Optional

from playwright.sync_api import BrowserContext, Page

from paths import DATA_DIR

BASE = "https://business.kakao.com/space/892922/channel/_dlxfxcG/"
PROFILE = os.path.join(DATA_DIR, "profile")
DEBUG_DIR = os.path.join(DATA_DIR, "debug")
DEBUG_KEEP = 20  # 최근 실패 기록만 남긴다

MSG_TEMPLATE = (
    "안녕하십니까\n정원유니어스(주) 입니다.\n\n"
    "{date}일 공지사항 전달 드립니다.\n\n"
    "{body}\n\n"
    "자세한 내용은 하단의 공지사항을 확인해주세요.\n감사합니다."
)
MSG_LIMIT = 300  # 이미지 첨부 시 내용 제한


def open_context(p, headless=False) -> BrowserContext:
    return p.chromium.launch_persistent_context(
        PROFILE, channel="chrome", headless=headless, viewport={"width": 1400, "height": 1000},
        chromium_sandbox=True,  # 기본값이면 --no-sandbox가 붙어 경고 배너가 뜬다
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




# --- 실패 대응: 화면 기록 + 사용자 직접 처리
# guard(name, how, error, clip) : 실패한 단계를 사용자에게 직접 하도록 안내하고, 다 했다고 하면 돌아온다.
#   그만두기를 고르면 예외를 던진다. clip 은 클립보드에 넣어 줄 텍스트(없으면 None).
Guard = Callable[[str, str, Exception, Optional[str]], None]


def save_debug(page: Page, step: str, err: Exception) -> str:
    """실패 순간의 화면 사진·페이지 구조·오류를 debug/날짜_시각_단계/ 에 남긴다. 저장 폴더를 돌려준다."""
    safe = re.sub(r"[^\w가-힣]+", "_", step).strip("_")
    d = os.path.join(DEBUG_DIR, time.strftime("%y%m%d_%H%M%S_") + safe)
    os.makedirs(d, exist_ok=True)
    try:
        url = page.url
    except Exception:
        url = "?"
    with open(os.path.join(d, "error.txt"), "w", encoding="utf-8") as f:
        f.write(f"단계: {step}\n주소: {url}\n\n{type(err).__name__}: {err}\n")
    for name, fn in (("screen.png", lambda: page.screenshot(path=os.path.join(d, "screen.png"), full_page=True)),
                     ("page.html", lambda: open(os.path.join(d, "page.html"), "w", encoding="utf-8").write(page.content()))):
        try:
            fn()
        except Exception as e:  # 페이지가 닫힌 경우 등
            with open(os.path.join(d, "error.txt"), "a", encoding="utf-8") as f:
                f.write(f"\n({name} 저장 실패: {e})\n")
    # 오래된 기록 정리
    olds = sorted(os.listdir(DEBUG_DIR))[:-DEBUG_KEEP]
    for o in olds:
        shutil.rmtree(os.path.join(DEBUG_DIR, o), ignore_errors=True)
    return d


def _step(page: Page, guard: Optional[Guard], name: str, how: str, fn, clip: Optional[str] = None) -> None:
    try:
        fn()
    except Exception as e:
        save_debug(page, name, e)
        if guard is None:
            raise
        guard(name, how, e, clip)


def write_post(page: Page, date: str, body: str, images: list[str], submit: bool = False,
               guard: Optional[Guard] = None) -> None:
    """소식 작성 화면을 채운다. submit=True 일 때만 '등록'을 누른다.
    guard 가 있으면 막힌 단계는 사용자가 직접 처리하고 다음 단계부터 이어간다."""
    title = f"{date} 공지사항"
    text = blocks(body)
    title_sel = "input#title, input[placeholder='제목']"

    # 카카오 화면이 수시로 바뀐다: posts/new(카드형/블로그형 선택) 또는 posts(제목+본문 바로 입력) 둘 다 대응.
    def open_form():
        page.goto(BASE + "posts/new", wait_until="domcontentloaded")
        page.wait_for_selector(f"{title_sel}, :text-is('블로그형')", timeout=20000)
        blog = page.get_by_text("블로그형", exact=True).first
        if blog.count() > 0 and blog.is_visible():
            blog.click()
        page.locator(title_sel).first.wait_for(timeout=20000)

    _step(page, guard, "소식 작성 화면 열기",
          "'소식 작성' 화면을 열어 주세요. (블로그형/카드형 선택이 나오면 '블로그형')", open_form)
    _step(page, guard, "소식 제목 입력", f"제목 칸에 '{title}' 를 입력해 주세요. (클립보드에 복사해 뒀습니다)",
          lambda: page.locator(title_sel).first.fill(title, timeout=10000), clip=title)
    _step(page, guard, "소식 본문 입력", "본문 칸에 붙여넣기(Ctrl+V) 해 주세요. (클립보드에 복사해 뒀습니다)",
          lambda: page.locator("textarea#description, textarea[placeholder*='새 이야기']").first.fill(text, timeout=10000),
          clip=text)
    if images:
        def attach():
            page.locator("input[type='file']").first.set_input_files(images, timeout=10000)
            page.wait_for_timeout(1500 + 600 * len(images))
        folder = os.path.dirname(images[0])
        _step(page, guard, "소식 이미지 첨부",
              f"이미지 {len(images)}장을 첨부해 주세요.\n폴더: {folder}\n(폴더 경로를 클립보드에 복사해 뒀습니다)",
              attach, clip=folder)
    if not submit:
        return

    def click_submit():
        page.locator("button.g_emph:has-text('등록'), button[type='submit']:has-text('등록')").first.click(timeout=10000)
        # 2026-10: '일부 친구는 작성한 소식을 볼 수 없어요'(최신 카카오톡 전용 안내) 확인창이 뜬다.
        notice = page.locator(".layer_body:has-text('일부 친구는')")
        try:
            notice.wait_for(timeout=5000)
            notice.locator("xpath=ancestor-or-self::*[.//button[normalize-space()='확인']][1]") \
                .get_by_role("button", name="확인", exact=True).click()
        except Exception:
            pass  # 확인창이 안 뜨는 경우
        page.wait_for_timeout(5000)  # 업로드·발행 처리 (발행 후에도 주소는 posts/new 그대로)

    _step(page, guard, "소식 등록", "'등록' 버튼을 눌러 발행해 주세요. (확인창이 뜨면 '확인')", click_submit)

    # 실제 발행 여부는 '내 소식' 목록에 제목이 보이는지로 확인한다.
    def verify():
        if not has_post(page, date):
            raise RuntimeError(f"'{title}' 소식이 목록에 보이지 않습니다. 발행되지 않았을 수 있습니다.")

    _step(page, guard, "소식 발행 확인",
          f"'내 소식' 목록에 '{title}' 이 올라갔는지 확인해 주세요. 없으면 직접 발행한 뒤 계속을 눌러 주세요.", verify)


def write_message(page: Page, date: str, body: str, click_next: bool = False,
                  guard: Optional[Guard] = None) -> str:
    """직전 메시지를 복사해 내용·소식 첨부를 교체한다. 발송 직전(다음 버튼 앞)에서 멈춘다.
    복사본에서 정보성/로고 이미지/버튼 설정이 그대로 유지된다.
    guard 가 있으면 막힌 단계는 사용자가 직접 처리하고 다음 단계부터 이어간다."""
    text = build_message(date, body)
    if len(text) > MSG_LIMIT:
        raise ValueError(f"메시지가 {len(text)}자로 {MSG_LIMIT}자를 넘습니다. 발췌문을 줄여 주세요.")

    def copy_prev():
        page.goto(BASE + "messages/new/feed", wait_until="domcontentloaded")
        page.get_by_text("이전 메시지 불러오기").first.click()
        page.get_by_text("복사해서 작성").first.click()
        page.wait_for_selector("textarea[name='messageWrite']", timeout=20000)
        page.wait_for_timeout(1500)

    _step(page, guard, "이전 메시지 복사",
          "메시지 보내기 화면에서 '이전 메시지 불러오기' → 가장 최근 공지 메시지의 '복사해서 작성'을 눌러 주세요.",
          copy_prev)
    _step(page, guard, "메시지 내용 입력",
          "'내용' 칸을 모두 지우고 붙여넣기(Ctrl+V) 해 주세요. (클립보드에 복사해 뒀습니다)",
          lambda: page.locator("textarea[name='messageWrite']").first.fill(text, timeout=10000), clip=text)

    # 소식 첨부 교체: 삭제 -> 불러오기 -> 해당 날짜 소식 선택
    def swap_post():
        # 2026-10-27 개편: '소식 첨부 :' 줄이 없어지고 '메시지 버튼 1' 안의 소식 칸(postUpload)으로 옮겨짐.
        # 화면이 왔다갔다 하므로 두 화면 모두 대응한다.
        new_del = page.locator("div.upload_g:has(input[name='postUpload']) button", has_text="삭제")
        old_del = page.get_by_text("소식 첨부 :").locator("xpath=following::button[1]")
        new_del.or_(old_del).first.click(timeout=15000)
        page.get_by_role("button", name="불러오기", exact=True).click(timeout=10000)
        title = page.get_by_text(f"{date} 공지사항", exact=True).first
        title.wait_for(timeout=15000)
        title.locator("xpath=following::button[normalize-space()='선택'][1]").click(timeout=10000)
        page.wait_for_timeout(1500)

    _step(page, guard, "메시지 소식 첨부",
          f"메시지에 붙은 예전 소식을 '삭제'하고 '불러오기'에서 '{date} 공지사항'을 '선택'해 주세요.", swap_post)
    if click_next:
        page.get_by_role("button", name="다음").click()
        page.wait_for_timeout(3000)
    return text
