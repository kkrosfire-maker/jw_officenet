# 주간 할 일 안드로이드 앱 + 위젯 (work_daily_todo_android)

새 터미널에서 이 프로젝트를 이어갈 때 가장 먼저 읽는 문서. 지금까지의 결정과 배경을 정리했다.
한국어로 소통하고, 이 워크스페이스의 CLAUDE.md 규칙(로컬 실행은 직접 검증, PowerShell 문법 등)을 따른다.

## 1. 한 줄 요약
PC용 "오늘의 할 일" 앱(`../work_daily_todo`)의 안드로이드 버전. **폰 전용**(PC와 동기화 없음), **일주일(월~일) 단위** 화면 + **홈 화면 위젯(확인 전용)**.
일단 **테스트 프로그램**으로 만들어 보면서 수정한다(완성 전 시험 단계).

## 2. 이번에 확정한 요구사항 (폰 앱)
- PC 앱과 **방식이 다르다**. 하루가 아니라 **한 주(월요일~일요일) 전체가 한 화면에 보여야 한다.**
- **요일별 섹션**: 월요일, 화요일, … 일요일 제목이 각각 있고 그 아래에 그날 할 일이 쌓인다.
- **입력 방식**: 상단 입력창 없음. **요일을 누르면 입력창이 열리고, 입력하면 그 요일 목록의 맨 아래에 추가**된다.
- **체크박스**로 완료 표시(PC 앱과 동일한 개념).
- **완료일/마감일(D+/D-) 기능 없음.** 후속작업·밀린 일(이월) 표시는 요구 목록에 없었음 → 필요 여부 아래 미결정 사항 참고.
- **위젯**: 확인 전용(편집은 앱에서). 일주일치 내용이 보여야 한다. 위젯을 누르면 앱이 열린다.
- 비용: 아래 4번 참고, 사실상 0원.

## 3. 원본 PC 앱 (참고용, 수정하지 말 것)
위치: `C:\Users\JW\Desktop\workspace\work_daily_todo` (Python + pywebview + openpyxl, `app.py` + `index.html`).
- 목적: 해야 할 일을 적고 체크하며, 엑셀로 그동안 한 일·걸린 기간을 분석. 프로그램 보드 옆에 붙여 쓴다.
- 기능(PC): 오늘 날짜 표시, 밀린 일 상단(빨간색), 완료일(마감일) D+/D-/D-0 칩(빨강/파랑/녹색), 후속 작업(↳), 메모(한 줄 표시), 개별 삭제·전체삭제(앱 내 확인창), 엑셀 내보내기(요약/할일기록/일별요약, 저장하면 완료 항목은 목록에서 숨김·기록은 유지), JPG 내보내기(살구색 메모 이미지), 📌 항상 위 고정, 프로그램 보드 창 옆 자동 도킹.
- 데이터: `data/todos.json` 자동 저장. 항목 = id, text, date(등록일), created_at, done_at, note, parent(후속), due, archived.
- 디자인 테마: 프로그램 보드와 동일한 **녹색**. `--green:#0D4A32; --green-dark:#0A3A28; --green-tint:#5E8168; --border:#C6D3CC; --hover:#EAF1ED; --ink:#1F2A24; --late:#B3261E(밀림/삭제 빨강)`, 폰트 맑은 고딕, 흰 배경, 둥근 모서리, 섹션 제목 앞 세로 바(4px 녹색), 항목 사이 1px 녹색 구분선. 로고: `../work_daily_todo/assets/logo.png`, 아이콘: `../work_daily_todo/app.ico`.
- 디자인 원본 와이어프레임: `C:\Users\JW\Desktop\workspace\screenshots\2026-10\POWERPNT_5ID4hI1mea.png` (세로로 긴 창, 위에 "오늘의 할 일"+입력칸, 가운데 체크박스 목록, 하단 저장/종료). 폰 앱은 이 구조가 아니라 위 2번의 주간 구조를 따른다.
- 일부 PC 앱 화면 참고 이미지: `C:\Users\JW\Desktop\KakaoTalk_20261019_170304015.png` (JPG 내보내기 예시 - 살구색 배경에 날짜 제목 + 줄글 목록).

## 4. 비용과 환경 (확인 완료)
- 개발 도구(Kotlin/Jetpack Glance 위젯/Gradle) 무료, 서버·DB 불필요(폰 내부 저장), 내 폰에는 APK 직접 설치(무료). 구글 플레이 등록은 불필요(하려면 1회 $25). Claude 작업은 구독 사용량 안(앱이 AI API를 호출하지 않으므로 API 과금 없음).
- 이 PC에 이미 있음: `ANDROID_HOME=C:\Android\Sdk` (platforms: android-36, build-tools: 35.0.0·36.0.0, cmdline-tools, emulator, system-images, platform-tools), `JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.12.8-hotspot\`. Android Studio는 **없음**(필요 없음, 명령줄 Gradle로 빌드). `gradle`/`adb` 명령은 PATH에 없을 수 있어 `C:\Android\Sdk\platform-tools\adb.exe` 경로로 호출하거나 Gradle wrapper를 프로젝트에 생성해서 사용.
- 에뮬레이터 이미지가 있으므로 폰 없이도 앱·위젯 표시 확인이 가능할 가능성이 높다(아직 시험 안 함).
- 이전 Capacitor(HTML 래핑) 방식 앱 경험: `../work_contract_lookup`(appId com.jw.contractcalc). 단, **홈 화면 위젯은 Capacitor로 불가능 → 네이티브 Kotlin 앱 필수.**

## 5. 권장 기술 방향
- 네이티브 Kotlin + Jetpack Compose(앱 화면) + Jetpack Glance(위젯), 저장은 앱 내부(Room 또는 DataStore/JSON). 위젯은 같은 저장소를 읽어 일주일치를 표시, 앱에서 수정하면 위젯 갱신.
- 새 폴더 안에 Gradle 프로젝트를 만든다(이 폴더가 프로젝트 루트). PC 앱 폴더와 섞지 않는다.
- 사용자는 작은 테스트 단계부터 확인하며 수정하길 원한다 → 처음엔 "요일 섹션 + 요일 눌러 입력 + 체크 + 저장"만 작동하는 최소 앱 → 에뮬레이터/폰 확인 → 위젯 → 다듬기 순서 권장.

## 6. 아직 정하지 않은 것 (진행하며 사용자에게 확인)
1. **주(week) 전환**: 새 주가 되면 지난 주 내용을 어떻게 할지(자동 비우기/보관/주 이동 화살표로 지난·다음 주 보기).
2. 체크 안 된 일을 **다음 날/다음 주로 넘길지**(PC 앱의 "밀린 일" 개념을 폰에서 쓸지).
3. 오늘 요일 **강조 표시**(오늘 섹션 색/상단 고정 여부), 상단에 오늘 날짜 표기(PC 앱은 날짜를 크게 표시했음).
4. 항목 **수정·삭제·순서 변경** 방식(길게 누르기/스와이프 등), 메모·후속 작업 포함 여부.
5. **엑셀/JPG 내보내기**를 폰에서도 넣을지(PC 분석용으로 폰 기록을 옮기려면 필요, 맨 마지막 단계 권장).
6. 위젯 크기·모양(일주일치를 한 번에 보여 줄 레이아웃, 항목이 많을 때 스크롤/생략), 완료 항목 표시 방식.

## 7. 다음에 할 일 (새 터미널에서)
1. 위 6번 중 1~3번만 사용자에게 간단히 확인(나머지는 기본값으로 시작하고 수정).
2. Kotlin + Compose 프로젝트 골격 생성 → 주간 화면(월~일 섹션, 요일 탭→입력→하단 추가, 체크박스, 앱 내부 저장) 구현.
3. APK 빌드 후 에뮬레이터로 실행·스크린샷 확인(사용자 폰 설치는 APK를 옮겨 직접 설치).
4. Glance 위젯(일주일치 확인 전용) 추가.
5. 사용자 피드백으로 수정 반복.

## 8. 진행 상태 (2026-10-21)
**1차 앱+위젯 구현 완료, 에뮬레이터(test_phone)에서 검증함.** 확정 사항: 주 이동 화살표(‹ ›, 가운데 탭=이번 주), 이월 없음, 오늘 요일 강조, 꾹 누르면 오른쪽에 수정/삭제 + 그대로 끌면 순서 변경, 내보내기 없음, 위젯 레이아웃은 만든 뒤 의논(6번 f).
- 코드: `app/src/main/java/com/jw/weeklytodo/` — `TodoStore.kt`(SharedPreferences JSON), `MainActivity.kt`(TodoState), `WeekScreen.kt`(Compose 화면), `TodoWidget.kt`(Glance 위젯, 4x4).
- 빌드: `.\gradlew.bat assembleDebug` → `app/build/outputs/apk/debug/app-debug.apk` (AGP 8.9.1, Gradle 8.11.1, compileSdk 36).
- 에뮬레이터: `emulator -avd test_phone`, 설치 `adb install -r`. 스크린샷은 `adb shell screencap` 후 `adb pull`(PowerShell 리다이렉트는 PNG가 깨짐). 한글 파일은 PowerShell Set-Content 말고 Write 도구로(인코딩 깨짐).
- 남은 것: 위젯 크기·모양 의논, 사용자 피드백 수정, 실제 폰 설치.
- (2026-10-21 2차) 위젯: 녹색 바탕+흰 카드 6개(3x2, 토·일은 한 카드를 절반씩), 요일 누르면 앱이 그 요일로 스크롤(`weeklytodo://day/날짜` 인텐트, launchMode=singleTask). 상단 고정 `저장` 버튼, 상태바는 시스템에 맡김(statusBarsPadding). 위젯 갱신은 `TodoWidget.refresh()`(상태 stamp 변경으로 재조합) — provideGlance에서 데이터를 미리 읽어 두면 앱에서 바꿔도 위젯이 안 바뀌는 함정 있음.
- (3차) 위젯 카드는 스크롤 목록(LazyColumn)이 아니라 일반 Column + 바깥 Box 클릭으로 바꿈 — 스크롤 목록은 빈 영역 터치를 삼켜서 카드 전체 클릭이 안 됨. 대신 카드 높이로 줄 수를 계산해 넘치면 "+N개 더" 표시(SizeMode.Exact, `capFor`).

## 9. 보류 (2026-10-21)
사용자 결정으로 **프로젝트 보류**. 안드로이드 앱+위젯은 에뮬레이터 검증까지 끝난 상태(미커밋, 실제 폰 설치 전). 재개 시: 실제 폰 설치(APK 전달) → 피드백 수정. 아이폰 버전은 검토만 함(별도 SwiftUI+WidgetKit 필요, Mac/클라우드Mac 필요, APK 설치 불가) — 진행 안 함.
