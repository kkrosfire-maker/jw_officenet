"""GUI에서 호출하는 이미지 생성 + 최종 조립 오케스트레이션 (API 미사용).

리서치·글쓰기·이미지 HTML 디자인(tmp_html/body-N.html)은 지금처럼 Claude Code
대화로 미리 완성해둔다는 전제 하에, 이 모듈은 그 결과물을 읽어 기존
scripts/*.py(make_thumbnail, capture_bodies, build_final)를 그대로 실행하는
결정론적 작업만 담당한다. scripts/ 폴더는 수정하지 않는다.
"""
import itertools
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLOG_ROOT = os.path.dirname(HERE)
SCRIPTS_DIR = os.path.join(BLOG_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from config import topic_dir, OUTPUT_BASE  # noqa: E402
from make_thumbnail import make_thumbnail  # noqa: E402
from capture_bodies import run as capture_bodies_run  # noqa: E402
from build_final import run as build_final_run  # noqa: E402

IMAGE_MARKER_RE = re.compile(r"\[IMAGE:\s*(.+?)\]")


def list_topics() -> list[str]:
    """output/ 아래 주제 폴더 목록을 최신순으로 반환한다."""
    if not os.path.isdir(OUTPUT_BASE):
        return []
    dirs = [
        d for d in os.listdir(OUTPUT_BASE)
        if os.path.isdir(os.path.join(OUTPUT_BASE, d))
    ]
    return sorted(dirs, reverse=True)


def extract_markers(draft_md: str) -> list[str]:
    return [m.strip() for m in IMAGE_MARKER_RE.findall(draft_md)]


def load_draft(topic: str) -> str | None:
    path = os.path.join(topic_dir(topic), "draft.md")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def check_readiness(topic: str) -> dict:
    """draft.md와 tmp_html/body-N.html이 준비됐는지 확인한다.

    반환: {"ok": bool, "draft_md": str|None, "marker_count": int, "missing": list[str], "reason": str|None}
    """
    draft_md = load_draft(topic)
    if draft_md is None:
        return {
            "ok": False,
            "draft_md": None,
            "marker_count": 0,
            "missing": [],
            "reason": "draft.md가 없습니다. 먼저 Claude Code 대화로 리서치·글쓰기를 완료하세요.",
        }

    markers = extract_markers(draft_md)
    html_dir = os.path.join(topic_dir(topic), "tmp_html")
    missing = [
        f"body-{n}.html"
        for n in range(1, len(markers) + 1)
        if not os.path.exists(os.path.join(html_dir, f"body-{n}.html"))
    ]
    reason = None
    if missing:
        reason = (
            f"tmp_html/ 에 {len(missing)}개 파일이 없습니다 ({', '.join(missing)}). "
            "Claude Code 대화로 image-maker 단계(HTML 디자인)를 먼저 완료하세요."
        )
    return {
        "ok": not missing,
        "draft_md": draft_md,
        "marker_count": len(markers),
        "missing": missing,
        "reason": reason,
    }


def run_images(topic: str, title_lines: list[str], draft_md: str, log=print) -> str:
    """썸네일 생성 + 본문 이미지 캡처 + draft.md 마커 치환 (API 미사용)."""
    markers = extract_markers(draft_md)

    log("썸네일 생성 중...")
    try:
        make_thumbnail(topic, title_lines)
    except SystemExit as e:
        raise RuntimeError(f"썸네일 생성 실패: {e}")

    if markers:
        log(f"Playwright로 본문 이미지 {len(markers)}개 캡처 중...")
        try:
            capture_bodies_run(topic)
        except SystemExit as e:
            raise RuntimeError(f"본문 이미지 캡처 실패: {e}")

        counter = itertools.count(1)

        def _replace(match: re.Match) -> str:
            n = next(counter)
            desc = match.group(1).strip()
            return f"![{desc}](./images/body-{n}.png)"

        draft_md = IMAGE_MARKER_RE.sub(_replace, draft_md)
        with open(os.path.join(topic_dir(topic), "draft.md"), "w", encoding="utf-8") as f:
            f.write(draft_md)
        log("draft.md 이미지 경로 치환 완료")
    else:
        log("[IMAGE: ...] 마커가 없어 본문 이미지 캡처를 건너뜁니다.")

    log("이미지 단계 완료")
    return draft_md


def run_assemble(topic: str, log=print) -> str:
    log("최종 조립 중...")
    try:
        build_final_run(topic)
    except SystemExit as e:
        raise RuntimeError(f"최종 조립 실패: {e}")
    final_html = os.path.join(topic_dir(topic), "final.html")
    log(f"완료: {final_html}")
    return final_html
