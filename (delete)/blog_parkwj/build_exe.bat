@echo off
chcp 65001 > nul
echo.
echo  박원종내과 블로그 파이프라인 EXE 빌드
echo  =====================================
echo.

where python > nul 2>&1
if %errorlevel% neq 0 (
    echo  [오류] Python을 찾을 수 없습니다. PATH를 확인하세요.
    pause
    exit /b 1
)

echo  [1/2] PyInstaller 설치 확인...
pip install pyinstaller --quiet

echo  [2/2] EXE 빌드 중...
echo.

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "블로그파이프라인" ^
  --clean ^
  blog_pipeline_gui.py

echo.
if exist "dist\블로그파이프라인.exe" (
    echo  ✅ 빌드 완료
    echo.
    echo  파일: dist\블로그파이프라인.exe
    echo.
    echo  ※ exe를 이 폴더 (output/, scripts/와 같은 위치)로 복사한 뒤 실행하세요.
    echo     복사 명령: copy dist\블로그파이프라인.exe 블로그파이프라인.exe
    echo.
) else (
    echo  ❌ 빌드 실패. 위 오류 메시지를 확인하세요.
)
pause
