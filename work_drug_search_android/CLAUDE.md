# 동일약품 검색기 (안드로이드) — work_drug_search_android

PC용 요율표 검색기(`../work_drug_search`)의 안드로이드 버전. 네이티브 Kotlin + Jetpack Compose.
요율표 엑셀을 앱에 **내장**(서버·네트워크 없음). 한국어로 소통하고 루트 CLAUDE.md 규칙을 따른다.

## 확정된 디자인·동작 (시안: 바탕화면 `동일약품 검색기 모바일 앱 화면_(261124).png`, 소스 `../work_drug_search/mobile_design/mockup.html`)
- 이름 `동일약품 검색기`, 제목 옆에 `(요율표 26.11)` 회색(제목 절반 크기). 기준 엑셀 선택 칸 없음.
- 검색 버튼 오른쪽 ▼ = 검색 대상 드롭다운(제품명·성분·대조의약품, 정확히 일치). 기본: 앞 3개 체크, 정확히 일치 해제. 최소 1개는 유지.
- 표시할 항목: **항상 접힌 상태로 시작**(`7/8` 개수 표시). 기본값은 대조의약품만 끔(요율 켬). 바꾸면 결과에 바로 반영.
- 정렬: 성분순(기본, 성분→약가↑→요율↓) / 약가순(낮은 순) / 요율순(높은 순) / 사용자 설정(**준비 중**, 비활성). 정렬 규칙은 PC 버전 `default_sort_key` 와 동일(단일제→복합제, 함량순, 동률은 제품명).
- 카드: 제품명(제목) → 성분 → 대조의약품 → 보험코드·제약사명 → 비고, 오른쪽에 약가·요율 배지. 엑셀에서 빨간 글씨였던 행은 제목이 빨강.
- 하단 버튼: `공유하기`(검색 결과를 줄글로 공유 시트에 전달, 최대 300건) / `클립보드 복사`(현재 화면 캡처를 이미지로 복사) / `이미지 저장`(현재 화면 PNG를 다운로드 폴더에 저장).
- 초성 검색: 검색어에 초성 자음(ㄱ~ㅎ)이 섞이면 글자별 초성 비교(`ㅇㅌㄹㅂㅅㅌㅌ`, `아ㅌㄹ` 가능). 영문인 성분에는 적용 안 됨. 쉼표(,)로 OR 검색.
- 톱니바퀴(설정)는 아직 "준비 중" 토스트만.

## 구조
- `app/src/main/java/com/jw/drugsearch/`
  - `Data.kt` Row 모델·`rates.json` 로드 / `Search.kt` 검색(초성)·정렬·표시 포맷 / `MainActivity.kt` Compose 화면 / `Actions.kt` 캡처(PixelCopy)·클립보드(FileProvider)·다운로드 저장(MediaStore)·공유
- 데이터: `app/src/main/assets/rates.json` (`tools/export_rates.py` 로 생성)
- minSdk 29(다운로드 폴더 저장에 MediaStore 사용), targetSdk 36, 패키지 `com.jw.drugsearch`

## 요율표 갱신 방법 (매달)
1. `python -X utf8 tools/export_rates.py "<새 요율표.xlsx>"` — 엑셀 읽기는 PC 검색기 `excel_utils.load_rate_sheet` 를 그대로 사용. 파일명 `(26.12)` 에서 버전을 뽑아 제목 옆에 표시.
2. `.\gradlew.bat assembleDebug` 로 APK 재빌드 → 폰에 설치.
- 약가/요율 칸에 `'208'` 같은 숫자 문자열이 있으면 숫자로 변환해서 내보낸다(PC 버전은 이 값을 "값 없음"으로 정렬하지만 모바일은 숫자로 정렬). `-`, `미정` 은 문자열 그대로 보여주고 정렬은 맨 뒤.

## 빌드·검증
- `$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-21.0.12.8-hotspot'; .\gradlew.bat assembleDebug` → `app/build/outputs/apk/debug/app-debug.apk` (디버그 서명, 폰에서 "알 수 없는 앱 설치" 허용 필요)
- 에뮬레이터: `C:\Android\Sdk\emulator\emulator.exe -avd test_phone`, 설치 `adb install -r`. 첫 실행은 데이터 로딩(JSON 2MB)에 몇 초 걸려 "불러오는 중…"이 먼저 보일 수 있으니 8초 이상 기다린 뒤 캡처.
- **검증용 훅**: `adb shell am start -n com.jw.drugsearch/.MainActivity --es q "검색어"` — adb 로는 한글 입력이 안 돼서, 이 값으로 검색어를 넣고 바로 검색한다.
- 스크린샷은 `adb shell screencap -p` 후 `adb pull`(PowerShell 리다이렉트는 PNG가 깨짐). 팝업 메뉴를 탭한 직후 바로 캡처하면 닫힌 화면이 찍히는 경우가 있어, 열린 상태는 `uiautomator dump` 로 함께 확인.

## 검증된 것 / 안 된 것 (2026-11-24, 에뮬레이터 test_phone)
- 확인: 초성 검색(372건), 검색 대상 드롭다운, 표시할 항목 펼치기, 정렬 메뉴·요율순 정렬, 이미지 저장(다운로드 폴더에 PNG 생성), 클립보드 이미지 복사(시스템 "Copied" 미리보기 표시).
- 아직 안 해 본 것: 공유하기 실제 시트, 표시 항목을 끄고 카드가 바뀌는 모습, 실제 폰 설치, 사용자 설정 정렬(기능 없음).
