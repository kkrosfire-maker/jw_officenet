# 프로그램 보드 용어

- **프로그램(항목)** — `programs.json` 의 한 줄. `type` 은 `exe`(PC 파일: exe·bat·lnk) 또는 `url`(웹).
- **주제(group)** — 카드를 묶는 제목. 비어 있으면 `기타`.
- **목록 저장소(store.py)** — 프로그램 목록을 고치는 규칙(`apply`). 파일·HTTP 를 모르는 순수 함수. 아이콘 가져오기는 `icons` 어댑터로 주입하며, 실패해도 저장은 막지 않는다.
- **아이콘 어댑터(icons.py)** — `icon_for(p) → 'icons/<id>.png' | ''`. 웹은 사이트에서, exe 는 파일 자체 아이콘에서 만든다.

시험: `python -m pytest tests`
