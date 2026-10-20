---
name: feedback-cardnews-design
description: 카드뉴스 디자인 피드백 — 확정된 스타일 규칙 및 수정 이력
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b03f6759-dce5-4fce-b208-756cd7eeef27
---

## 확정 디자인 규칙

- **배경**: 흰색 (white) 기본. 사진은 상단에만 배치.
- **상단 사진**: picsum.photos seed URL로 주제 연관 사진 다운로드 후 하단 55% 지점부터 흰색으로 페이드
- **번호 체계**: 모든 단락은 `01` / `02` / `03` 형식으로 통일 — STEP, ①②③, 체크마크 사용 금지
- **카드 수**: 항상 6장 이상 (현재 7장 표준)
- **카드 사이즈**: 1080×1350px (세로형)
- **카테고리 pill**: 사진 하단부에 배치 (photo_h - 66px)
- **그라디언트**: IG 공식 컬러 (퍼플→핑크→레드→오렌지→옐로우)
- **그라디언트 요소**: 반드시 `paste_grad_rounded()`로 마스크 적용 — 직사각형 삐짐 방지

## 수정 이력
- 텍스트-배경 정렬: `getbbox()`의 `bb[1]` offset 보정으로 수직 중앙 정렬
- 그라디언트 배지 삐짐: `paste_grad_rounded()` 헬퍼로 마스크 클리핑 처리
- 배경 → 흰색으로 변경 (사진 배경 제거 요청)

**Why:** 사용자가 단계적으로 피드백을 주며 확정한 스타일. 다음 카드뉴스 제작 시 동일 스크립트 구조 재사용.

**How to apply:** 새 카드뉴스 제작 시 `generate_cards.py` 구조를 기반으로 콘텐츠만 교체.
