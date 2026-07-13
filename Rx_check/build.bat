@echo off
chcp 65001 > nul
echo.
echo =====================================================
echo   처방약 분석기 EXE 빌드 스크립트
echo =====================================================
echo.

echo [1/3] 필요 패키지 설치 중...
pip install anthropic Pillow pyinstaller --quiet
if %errorlevel% neq 0 (
    echo 패키지 설치 실패. pip 및 인터넷 연결을 확인하세요.
    pause
    exit /b 1
)

echo.
echo [2/3] EXE 빌드 중... (수 분 소요될 수 있습니다)
pyinstaller --onefile --windowed ^
  --name "처방약분석기" ^
  --hidden-import "anthropic" ^
  --hidden-import "httpx" ^
  --hidden-import "PIL" ^
  --hidden-import "PIL.Image" ^
  rx_analyzer.py

if %errorlevel% neq 0 (
    echo.
    echo 빌드 실패. 오류 메시지를 확인하세요.
    pause
    exit /b 1
)

echo.
echo [3/3] 완료!
echo.
echo ============================================
echo  실행 파일: dist\처방약분석기.exe
echo ============================================
echo.
pause
