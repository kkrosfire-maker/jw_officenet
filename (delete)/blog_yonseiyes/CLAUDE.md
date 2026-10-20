# 연세예스내과 블로그 자동화 파이프라인

연세예스내과 네이버 블로그 글을 4단계 서브 에이전트 파이프라인으로 자동 생성하는 시스템.

---

## 폴더 구조

```
blog_yes/
├── agents/          ← 각 단계 에이전트 지시서
│   ├── researcher.md
│   ├── writer.md
│   ├── image-maker.md
│   └── assembler.md
├── guide/           ← 에이전트가 참조하는 규칙 가이드
│   ├── compliance-rules.md      ← 의료광고 금지 표현 (SSOT)
│   ├── image-guide-yonsei.md    ← 본문 이미지 규칙 (SSOT, Template A/B 신규 프레임 시스템)
│   ├── image-guide.md           ← 구 클립보드 시스템 (더 이상 사용 안 함, 참고용으로만 보존)
│   ├── seo-guide.md
│   └── style-guide.md
├── scripts/         ← 공유 Python 스크립트
│   ├── render_body_yonsei.py     ← 본문 이미지 렌더링 (Template A/B)
│   ├── make_thumbnail_yonsei.py  ← 썸네일 렌더링 (신규 프레임 시스템)
│   ├── make_thumbnail.py         ← 구 클립보드 시스템 (더 이상 사용 안 함)
│   ├── capture_bodies.py         ← 구 클립보드 시스템 (더 이상 사용 안 함)
│   └── build_final.py
└── output/[yymmdd_주제]/   ← 주제별 산출물
    ├── research.md
    ├── draft.md
    ├── thumbnail.json     ← 썸네일 렌더링 입력
    ├── variants.json      ← 본문 이미지 렌더링 입력 (Template A/B)
    ├── images/
    ├── final.md
    └── final.html
```

---

## 작업 순서

사용자가 주제를 던지면 아래 4단계를 순서대로 실행한다.  
**메인(오케스트레이터)은 직접 글을 쓰거나 리서치하지 않는다. 반드시 서브 에이전트에게 위임한다.**

### Step 1 — 리서치
`agents/researcher.md` 지시에 따라 리서치 수행  
산출물: `output/[yymmdd_주제]/research.md`

완료 후 사용자에게 알리고 Step 2 진행 여부 확인.

### Step 2 — 글쓰기
`agents/writer.md` 지시에 따라 블로그 글 작성  
산출물: `output/[yymmdd_주제]/draft.md`

완료 후 사용자에게 알리고 Step 3 진행 여부 확인.

### Step 3 — 이미지 생성
`agents/image-maker.md` 지시에 따라 썸네일 + 본문 이미지 생성  
draft.md의 `[IMAGE: ...]` 마커를 실제 경로로 치환  
산출물: `output/[yymmdd_주제]/images/`, `variants.json`

완료 후 사용자에게 알리고 Step 4 진행 여부 확인.

### Step 4 — 통합
`agents/assembler.md` 지시에 따라 최종 파일 생성  
산출물: `output/[yymmdd_주제]/final.md`, `output/[yymmdd_주제]/final.html`

완료 후 final.html을 직접 브라우저로 열어서 확인 (사용자에게 열라고 안내하지 않는다).

---

## 규칙

- 단계 사이마다 "Step N 완료 — 다음 단계 진행할까요?" 형태로 사용자에게 알릴 것
- 의료광고 규정은 `guide/compliance-rules.md` 참조 (각 에이전트가 직접 읽음)
- 본문 이미지 규칙은 `guide/image-guide-yonsei.md` 참조 (SSOT) — Template A(리스트형)/B(본문형) +
  우상단 코너 라벨 구조. `.clipboard-frame` 등 구 Convention B 클래스명 체계는 더 이상 쓰지 않는다
  (2026-07-15 전면 교체, §2 참고)
- 공유 스크립트(`scripts/`)는 절대 주제별로 복사하지 않고 CLI 인자로 주제명을 전달
