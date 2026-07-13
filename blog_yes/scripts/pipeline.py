"""
블로그 포스팅 전체 빌드 파이프라인 (Step 2~4 자동 실행)

사용법:
  python scripts/pipeline.py <주제폴더명> <제목줄1> [제목줄2] [제목줄3]

예시:
  python scripts/pipeline.py 260622_여름철수면건강 "열대야 불면증" "수면 건강 지키는 법"
  python scripts/pipeline.py 여름철식중독 "여름철 식중독" "원인·증상·예방"

단계:
  Step 2 — 썸네일 생성   (make_thumbnail.py)
  Step 3 — 본문 이미지 합성 (capture_bodies.py)
  Step 4 — 최종 파일 빌드  (build_final.py)

Step 1(리서치), 이미지 HTML 작성은 에이전트가 먼저 완료해야 한다.
"""
import sys
import os
import time

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)


def step(label: str, fn, *args):
    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"{'='*50}")
    t0 = time.time()
    fn(*args)
    print(f"  완료 ({time.time()-t0:.1f}s)")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    topic = sys.argv[1]
    title_lines = sys.argv[2:]

    from make_thumbnail import make_thumbnail
    from capture_bodies import run as capture_bodies
    from build_final import run as build_final

    step("Step 2 — 썸네일 생성", make_thumbnail, topic, title_lines)
    step("Step 3 — 본문 이미지 합성", capture_bodies, topic)
    step("Step 4 — 최종 파일 빌드", build_final, topic)

    print(f"\n✓ 파이프라인 완료 — output/{topic}/final.html 을 브라우저로 확인하세요.")


if __name__ == "__main__":
    main()
