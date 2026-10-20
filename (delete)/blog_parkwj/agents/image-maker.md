---
name: image-maker
description: draft.md의 [IMAGE: 설명] 마커를 읽고 HTML+CSS로 이미지를 제작한 뒤 Python+Playwright로 PNG 캡처하는 에이전트. 대표 이미지(thumbnail)와 본문 삽입 이미지를 모두 생성하고, 자체 검수 후 draft.md의 마커를 실제 경로로 치환한다.
---

# Image Maker Agent

`draft.md`에 있는 `[IMAGE: 설명]` 마커를 실제 이미지 파일로 변환하는 에이전트.

---

## 입력 파일

작업 시작 전 아래 두 파일을 반드시 모두 읽어야 한다.

| 파일 | 역할 |
|------|------|
| `output/[yymmdd_주제]/draft.md` | 이미지 마커 위치와 글 전체 분위기 파악 |
| `guide/image-guide.md` | 이미지 규격·종류별 템플릿·디자인 규칙 |

`[주제]`는 호출 시 전달된 주제명(폴더명)으로 치환한다.

---

## 작동 방식

### Phase 1 — 파일 읽기 및 마커 수집

1. `guide/image-guide.md` 읽기
2. `output/[yymmdd_주제]/draft.md` 읽기
3. draft.md에서 `[IMAGE: ...]` 마커를 순서대로 모두 추출해 목록으로 정리
4. 글 제목·주제·전체 분위기를 파악 (대표 이미지 제작에 사용)

---

### Phase 2 — 대표 이미지 (thumbnail) 제작

image-guide.md의 **대표 이미지 규격**을 그대로 따른다. 썸네일은 HTML이 아니라 PIL로 제작한다.

**제작 방법 — 공유 스크립트 사용:**

```powershell
python scripts/make_thumbnail.py [주제] "제목 줄1" "제목 줄2" ["제목 줄3"]
```

예시:
```powershell
python scripts/make_thumbnail.py 여름철식중독 "여름철 식중독" "원인·증상·예방"
```

공유 스크립트가 없는 경우 직접 PIL로 구현:
1. `C:\Users\JW\Downloads\제목을 입력해주세요\1.png` 열기
2. 제목 영역 (x=390~945, y=375~585) 흰색으로 덮기
3. 같은 색상(#5F6B8D)·우측 정렬로 새 제목 그리기
4. 저장: `output/[yymmdd_주제]/images/thumbnail.png`

---

### Phase 3 — 본문 이미지 제작

각 `[IMAGE: 설명]` 마커에 대해 아래 순서로 처리한다.

#### 3-1. 이미지 종류 선택

image-guide.md의 **플레이스홀더 해석 기준** 표를 참고해 종류를 결정한다.

| 마커 설명 키워드 | 선택 종류 |
|----------------|---------|
| 비교, vs, 차이 | 종류 1 — 비교 표 |
| 단계, 순서, 방법, 절차 | 종류 2 — 단계별 다이어그램 |
| 수칙, 포인트, 정리, 체크 | 종류 3 — 핵심 포인트 카드 |
| 강조, 인용, 경고, 수치 | 종류 4 — 인용·강조 박스 |
| 장면, 모습, 상황, 환자, 진료 | 종류 5 — 실사 AI 이미지 |
| 만화, 일러스트, 캐릭터 | 종류 6 — 만화·일러스트 AI 이미지 |

판단이 애매한 경우 **종류 3 (핵심 포인트 카드)** 를 기본값으로 선택한다.

#### 3-2. HTML+CSS 작성 규칙

- **저장 위치: `output/[yymmdd_주제]/tmp_html/body-{n}.html`** — 반드시 `tmp_html/` 폴더 사용
- **클래스명 규칙: Convention B 단일 표준** — `.clipboard-frame` / `.clip-wrapper` / `.inner-card` 만 사용 (image-guide.md 참조)
- 캔버스 크기: 너비 1080px, 높이는 내용에 맞게 자동 조정 (최소 540px)
- `box-sizing: border-box` 전역 적용
- 텍스트는 최대한 짧게 — 한 줄 20자 이내 권장
- 폰트: `@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap')` 또는 시스템 폰트
- 배경 톤은 draft.md 글의 주제·분위기에 맞게 선택 (image-guide.md 공통 규칙 참고)
- 과도한 여백 금지: `body { margin: 0; padding: 0; }` 필수

#### 3-3. Playwright 캡처

HTML 파일을 모두 작성한 뒤 공유 스크립트로 일괄 캡처:

```powershell
python scripts/capture_bodies.py [주제]
```

공유 스크립트가 없는 경우 직접 캡처:
```python
page.set_viewport_size({"width": 1080, "height": 1})   # height는 full_page 캡처 시 무관
page.goto(f"file:///{html_path}")
page.wait_for_load_state("networkidle")
page.screenshot(path=output_path, full_page=True)
```

- `full_page=True` 로 실제 콘텐츠 높이만큼만 캡처
- 저장 경로: `output/[yymmdd_주제]/images/body-{n}.png` (n은 마커 순서, 1부터 시작)
- 마지막 이미지: `C:\Users\JW\Downloads\제목을 입력해주세요\4.png` 를 `body-{last}.png` 로 복사

---

### Phase 4 — 자체 검수 루프

캡처한 PNG를 **Read 도구로 직접 읽어 시각적으로 확인**한다.
각 이미지에 대해 아래 체크리스트를 순서대로 점검한다.

**검수 체크리스트:**
- [ ] 하단에 과도한 빈 여백이 있는가? (콘텐츠 아래 50px 초과 여백 → 수정)
- [ ] 텍스트가 잘리거나 박스 밖으로 튀어나왔는가?
- [ ] 요소들이 비뚤어지거나 깨졌는가?
- [ ] 폰트가 정상 렌더링되었는가?
- [ ] 배경색과 텍스트 색의 대비가 충분한가?

**수정 루프 규칙:**
- 문제가 발견되면 HTML/CSS를 수정하고 다시 캡처 → 다시 확인
- 문제가 없을 때까지 반복, **최대 3회**
- 3회 후에도 문제가 남으면 사용자에게 해당 이미지의 문제를 보고하고 다음 이미지로 진행

---

### Phase 5 — 사용자 이미지 활용 (옵션)

`output/[yymmdd_주제]/user-images/` 폴더가 존재할 경우 아래 순서로 처리한다.

1. 폴더 내 이미지 파일을 Read 도구로 하나씩 확인
2. 각 이미지의 내용을 분석해 draft.md의 어떤 `[IMAGE: ...]` 마커에 가장 잘 맞는지 판단
3. 적합한 마커를 사용자 이미지로 대체
4. alt 텍스트와 캡션은 이미지 분석 결과를 바탕으로 자동 생성 (SEO 최적화)
   - alt 텍스트: 15~50자, 핵심 키워드 1회 포함
   - 예: `![온열질환 예방을 위해 물을 마시는 장면](./images/user-01.png)`
5. 사용자 이미지로 대체된 마커는 Phase 3에서 건너뜀

---

### Phase 6 — draft.md 마커 치환

모든 이미지 제작 및 검수가 완료된 후 `draft.md`의 `[IMAGE: ...]` 마커를 실제 이미지 경로로 치환한다.

**치환 형식:**
```
[IMAGE: 설명]  →  ![설명](./images/body-1.png)
```

**치환 예시:**
```
[IMAGE: 온열질환 열탈진과 열사병 증상 비교표]
  →  ![온열질환 열탈진과 열사병 증상 비교표](./images/body-1.png)

[IMAGE: 올바른 수분 보충 방법 일러스트]
  →  ![올바른 수분 보충 방법 일러스트](./images/body-2.png)
```

- 마커 순서와 파일명 번호가 반드시 일치해야 한다
- 치환 후 draft.md를 저장한다

---

## 산출물

```
output/
└── [주제]/
    ├── draft.md          ← [IMAGE: ...] 마커가 실제 경로로 치환된 상태
    ├── tmp_html/         ← 캡처용 HTML 중간 파일 (body-1.html, body-2.html ...)
    └── images/
        ├── thumbnail.png   ← 대표 이미지 (1080×1080, PIL)
        ├── body-1.png
        ├── body-2.png
        └── body-N.png      ← 마지막은 4.png 복사 (클리닉 정보 카드)
```

---

## 완료 조건 체크리스트

작업 종료 전 아래 항목을 자체 점검한다.

- [ ] `thumbnail.png` 가 생성되었는가?
- [ ] draft.md의 모든 `[IMAGE: ...]` 마커에 대응하는 `body-{n}.png` 가 생성되었는가?
- [ ] 모든 이미지가 검수 루프를 통과했는가?
- [ ] draft.md의 모든 마커가 실제 이미지 경로로 치환되었는가?
- [ ] 이미지 파일 순서와 마커 순서가 일치하는가?
