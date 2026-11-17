@echo off
chcp 65001 >nul
title 정원오피스넷 고객정보 입력 - 설치
cd /d "%~dp0"
echo.
echo ===== 정원오피스넷 고객정보 입력 설치 =====
echo.

set PY=
where python >nul 2>nul && set PY=python
if not defined PY where py >nul 2>nul && set PY=py -3
if not defined PY goto nopython

echo [1/5] Python 확인
%PY% --version
echo.

echo [2/5] 필요한 패키지 설치 (인터넷 필요)
%PY% -m pip install --disable-pip-version-check openpyxl pywin32
if errorlevel 1 goto pipfail
echo.

echo [3/5] Word / Excel / Chrome 확인
reg query "HKCR\Word.Application" >nul 2>nul || echo   [경고] Word가 설치되어 있지 않은 것 같아요. 계약서 PDF 변환이 안 돼요.
reg query "HKCR\Excel.Application" >nul 2>nul || echo   [경고] Excel이 설치되어 있지 않은 것 같아요. 고객list 등록이 안 돼요.
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" >nul 2>nul || reg query "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" >nul 2>nul || echo   [경고] Chrome이 설치되어 있지 않은 것 같아요. 기본 브라우저로 열려요.
echo.

echo [4/5] 고객list 엑셀 위치 확인
set XLSX=
for /f "usebackq delims=" %%P in (`%PY% -X utf8 -c "import json;print(json.load(open('app_config.json',encoding='utf-8')).get('xlsx',''))" 2^>nul`) do set XLSX=%%P
if not defined XLSX goto noxlsxcfg
if exist "%XLSX%" goto xlsxok
echo   [경고] 엑셀 파일을 찾지 못했어요: %XLSX%
echo   N드라이브 동기화를 확인하거나 app_config.json 의 "xlsx" 경로를 이 PC에 맞게 고쳐 주세요.
goto xlsxdone
:noxlsxcfg
echo   [경고] app_config.json 이 없어요. 엑셀 위치를 정해 주세요. 예: {"xlsx": "N:\폴더\정원오피스넷_고객관리_통합본.xlsx"}
goto xlsxdone
:xlsxok
echo   OK: %XLSX%
:xlsxdone
echo.

echo [5/5] 바탕화면 바로가기 만들기
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\고객정보 입력.lnk'); $s.TargetPath='%~dp0run.bat'; $s.WorkingDirectory='%~dp0'; $s.Save()"
if errorlevel 1 (echo   바로가기 만들기 실패 - run.bat 을 직접 실행하세요.) else (echo   바탕화면에 '고객정보 입력' 바로가기를 만들었어요.)
echo.
echo ===== 설치 완료. 바탕화면의 '고객정보 입력' 또는 run.bat 으로 실행하세요 =====
echo 처음 저장할 때 officeboard 비밀번호를 한 번 물어봐요.
echo.
pause
exit /b 0

:nopython
echo [오류] Python이 설치되어 있지 않아요.
echo   https://www.python.org/downloads/ 에서 설치하세요. 설치할 때 'Add python.exe to PATH' 를 꼭 체크하세요.
echo   설치 후 이 설치.bat 을 다시 실행하세요.
start "" https://www.python.org/downloads/
pause
exit /b 1

:pipfail
echo [오류] 패키지 설치에 실패했어요. 인터넷 연결을 확인하고 다시 실행하세요.
pause
exit /b 1
