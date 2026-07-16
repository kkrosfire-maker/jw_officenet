---
name: image-maker
description: draft.md의 [IMAGE: 설명] 마커를 읽고 연세예스내과 신규 프레임 시스템(Template A/B)으로 본문 이미지를 제작하는 에이전트. 대표 이미지(thumbnail)와 본문 삽입 이미지를 모두 생성하고, 자체 검수 후 draft.md의 마커를 실제 경로로 치환한다.
---

# Image Maker Agent

`draft.md`에 있는 `[IMAGE: 설명]` 마커를 실제 이미지 파일로 변환하는 에이전트.

> ⚠️ 2026-07-15: 본문 이미지 시스템이 **좌우분할 클립보드 방식 → Template A(리스트형)/B(본문형) +
> 우상단 코너 라벨** 방식으로 전면 교체되었다. Phase 2(썸네일)·Phase 3(본문 이미지) 모두 신규 시스템
> 기준으로 다시 작성되었다.

---

## 입력 파일

작업 시작 전 아래 파일을 반드시 모두 읽어야 한다.

| 파일 | 역할 |
|------|------|
| `output/[yymmdd_주제]/draft.md` | 이미지 마커 위치와 글 전체 분위기 파악 |
| `guide/image-guide-yonsei.md` | 프레임 좌표·타이포그래피·Template A/B 규칙·코너 라벨 규칙 (SSOT) |

`[주제]`는 호출 시 전달된 주제명(폴더명)으로 치환한다.

---

## 작동 방식

### Phase 1 — 파일 읽기 및 마커 수집

1. `guide/image-guide-yonsei.md` 읽기 (특히 §2 좌표/템플릿, §3 타이포그래피, §4 일러스트 규칙)
2. `output/[yymmdd_주제]/draft.md` 읽기
3. draft.md에서 `[IMAGE: ...]` 마커를 순서대로 모두 추출해 목록으로 정리
4. 글 제목·주제·전체 분위기를 파악 (대표 이미지 제작에 사용)

---

### Phase 2 — 대표 이미지 (thumbnail) 제작

`guide/image-guide-yonsei.md` §5(썸네일 규칙)를 따른다.

#### 2-1. 축약 제목 확인 (필수, §5-1)

포스팅 전체 제목(H1)을 그대로 쓰지 않는다. 축약형을 자동으로 확정하지 말고, 반드시 사용자에게 확인받는다
(예: "썸네일 제목은 뭐로 할까요? 자동 축약하면 'OO'인데 이대로 괜찮을까요?").

#### 2-2. `thumbnail.json` 작성

`output/[yymmdd_주제]/thumbnail.json` 파일을 작성한다 (스키마 전문은 `scripts/make_thumbnail_yonsei.py`
상단 docstring 참고):

```json
{
  "title_lines": ["확인받은 축약 제목 (1~2줄, 2줄이면 배열에 2개)"],
  "illustration_desc": "한글 장면 설명 (placeholder 문구로도 쓰임)",
  "illustration_file": null
}
```

- 일러스트도 §4-1 규칙(배경 없음, 인물 원칙 포함, 전신/상반신)을 그대로 따른다
- 처음에는 `illustration_file`을 `null`로 두고 렌더링해 프레임+제목만 확인한다

#### 2-3. 렌더링 (공유 스크립트 사용)

```powershell
python scripts/make_thumbnail_yonsei.py [주제]
```

`illustration_file`이 `null`이면 placeholder 박스로, 채워지면 실제 이미지가 §5-2의
`THUMB_IMAGE_BOX` 자리에 합성되어 `output/[yymmdd_주제]/images/thumbnail.png`에 저장된다.

#### 2-4. 사용자 검수 및 프롬프트 저장

Phase 3-4와 동일한 흐름을 따른다 — placeholder 상태를 사용자에게 승인받은 뒤, 일러스트 프롬프트를
`illustration_prompts.txt`에 `[thumbnail] 축약 제목 — 가로 자리, 770x490px` 헤더로 추가하고, 사용자가
이미지를 전달하면 `thumbnail.json`의 `illustration_file`을 채워 다시 렌더링한다.

---

### Phase 3 — 본문 이미지 제작 (Template A/B, 신규 시스템)

각 `[IMAGE: 설명]` 마커를 draft.md의 해당 섹션 내용과 함께 분석해 아래 순서로 처리한다.

#### 3-1. 섹션별 Template A/B 판단

`guide/image-guide-yonsei.md` §2-4/§2-5 기준:

- 해당 섹션이 **번호 매길 수 있는 목록**(체크리스트, 원인/주의사항 나열, 불릿) → **Template A (리스트형)**
- 해당 섹션이 **서술형 문단**(정의·설명, 개념 비교) → **Template B (본문형)**
- 마크다운 표(table)가 있는 섹션은 표를 그대로 쓰지 않는다 — 표 내용을 "항목: 설명" 형태의 리스트 문장으로
  재구성해 Template A로 변환한다 (2026-07-15 확정 — 레퍼런스에 표 형태가 없었음).

#### 3-2. `variants.json` 작성 (필수 — 렌더링 스크립트의 입력)

`output/[yymmdd_주제]/variants.json` 파일을 아래 스키마로 작성한다 (스키마 전문은
`scripts/render_body_yonsei.py` 상단 docstring 참고):

```json
{
  "corner_label_text": "포스팅 시리즈 문구 — 병원명은 제외 (예: 사용자가 준 소스 문구에서 병원명만 뺀 것)",
  "variants": [
    {
      "frame": "fraim1.png",
      "template": "B",
      "seq": 1,
      "title": "제목 (2줄이면 <br>로 직접 줄바꿈 위치 지정)",
      "body_html": "Template B 전용 — 문단 HTML, <strong> 등 인라인 태그 허용",
      "illustration_desc": "한글 장면 설명",
      "illustration_file": null
    }
  ]
}
```

- `frame`: `fraim1.png` → `fraim2.png` → `fraim3.png` 순서로 **이미지 개수만큼 순환 배정** (5장이면
  1,2,3,4,5번에 각각 fraim1,2,3,1,2)
- `seq`: 프레임 순환과 무관하게 **포스팅 내 이미지 순서**(1,2,3,4,5...) — 코너 라벨 원형 순번에 그대로 쓰인다
- `illustration_file`: 아직 사용자로부터 이미지를 받기 전에는 반드시 `null` — Phase 3-4(프레임 렌더링)에서
  placeholder로 렌더링된다

#### 3-3. 프레임 렌더링 (공유 스크립트 사용)

```powershell
python scripts/render_body_yonsei.py [주제]
```

- `variants.json`의 `illustration_file`이 `null`인 항목은 점선 placeholder 박스(한글 설명 텍스트 포함)로,
  경로가 채워진 항목은 실제 이미지로 합성되어 `output/[yymmdd_주제]/images/body-{n}.png`에 저장된다
- 최초 실행 시에는 모든 `illustration_file`을 `null`로 둔 상태로 실행해 **프레임+텍스트만** 만든다

#### 3-4. 사용자 검수 (필수)

`guide/image-guide-yonsei.md` §6 워크플로를 그대로 따른다:

1. placeholder 상태의 `body-{n}.png`를 사용자에게 보여주고 제목·리스트 문구·Template 선택이 맞는지 승인받는다
2. 승인 후 §4 규칙에 맞는 인물 일러스트 프롬프트(한글 설명 + 영어 프롬프트 + 정확한 이미지 크기)를
   `output/[yymmdd_주제]/illustration_prompts.txt`에 저장한다
3. 사용자가 이미지를 만들어 전달하면, 어떤 파일이 어떤 자리에 대응하는지 이미지 내용을 직접 확인해 매칭한 뒤
   `variants.json`의 해당 `illustration_file`을 실제 파일명으로 채운다
4. `python scripts/render_body_yonsei.py [주제]`를 다시 실행해 최종 합성본을 만든다
5. 최종본을 Read 도구로 다시 확인 (겹침·잘림·placeholder 잔존 여부 점검)

---

### Phase 5 — 사용자 이미지 활용 (옵션)

`output/[yymmdd_주제]/user-images/` 폴더가 존재할 경우, Phase 3-4와 별개로 사용자가 처음부터 완성된
이미지를 제공한 경우를 다룬다.

1. 폴더 내 이미지 파일을 Read 도구로 하나씩 확인
2. 각 이미지의 내용을 분석해 어떤 마커(`variants.json`의 어떤 항목)에 가장 잘 맞는지 판단
3. 해당 `illustration_file`을 그 이미지 경로로 채우고 Phase 3-3을 재실행

---

### Phase 6 — draft.md 마커 치환

모든 이미지 제작 및 검수가 완료된 후 `draft.md`의 `[IMAGE: ...]` 마커를 실제 이미지 경로로 치환한다.

**치환 형식:**
```
[IMAGE: 설명]  →  ![설명](./images/body-1.png)
```

- 마커 순서와 `variants.json`의 항목 순서(= 파일명 번호)가 반드시 일치해야 한다
- 치환 후 draft.md를 저장한다 — **치환됐다고 보고하기 전에 Read 도구로 직접 draft.md를 다시 읽어
  마커가 실제로 남아있지 않은지 확인한다** (과거 세션에서 치환을 빠뜨린 채 완료 보고한 사례가 있었음)

---

## 산출물

```
output/
└── [주제]/
    ├── draft.md              ← [IMAGE: ...] 마커가 실제 경로로 치환된 상태
    ├── thumbnail.json          ← 썸네일 렌더링 입력
    ├── variants.json           ← Template A/B 렌더링 입력 (본문 이미지)
    ├── illustration_prompts.txt  ← 인물 일러스트 프롬프트 (한글 설명 + 영어 프롬프트, 썸네일 포함)
    └── images/
        ├── thumbnail.png       ← 대표 이미지
        ├── body-1.png
        ├── body-2.png
        └── body-N.png          ← 마지막은 클리닉 정보 카드로 대체되는 경우 있음
```

---

## 완료 조건 체크리스트

작업 종료 전 아래 항목을 자체 점검한다.

- [ ] `thumbnail.json`이 작성되고 축약 제목을 사용자에게 확인받았는가?
- [ ] `thumbnail.png`가 placeholder가 아닌 실제 이미지로 최종 합성되었는가?
- [ ] `variants.json`이 draft.md의 모든 `[IMAGE: ...]` 마커에 대응해 작성되었는가?
- [ ] 모든 `body-{n}.png`가 실제 이미지(placeholder 아님)로 최종 합성되었는가?
- [ ] draft.md를 Read 도구로 다시 읽어 모든 마커가 실제 경로로 치환된 것을 직접 확인했는가?
- [ ] 이미지 파일 순서와 마커 순서가 일치하는가?
- [ ] `illustration_prompts.txt`의 모든 프롬프트에 여백 최소화 문구(§4-1 규칙 5, "~5px margin on all four sides,
      no extra padding or empty space around the subject, tightly cropped full-bleed composition")가 포함되었는가?
