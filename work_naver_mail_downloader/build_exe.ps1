# 네이버 메일 다운로더 빌드 스크립트
# 실행: .\build_exe.ps1

Write-Host "패키지 설치 확인 중..." -ForegroundColor Cyan
python -m pip install pyinstaller openpyxl tkinterdnd2 pywin32 --quiet

Write-Host "PyInstaller 빌드 시작..." -ForegroundColor Cyan

python -m PyInstaller `
    --onefile `
    --windowed `
    --name "네이버메일다운로더" `
    --collect-data tkinterdnd2 `
    --hidden-import "win32com" `
    --hidden-import "win32com.client" `
    --hidden-import "win32api" `
    --hidden-import "win32con" `
    --hidden-import "pywintypes" `
    --hidden-import "pythoncom" `
    --hidden-import "openpyxl" `
    --clean `
    naver_mail_downloader.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "빌드 성공!" -ForegroundColor Green
    Write-Host "실행 파일: dist\네이버메일다운로더.exe" -ForegroundColor Yellow
} else {
    Write-Host "빌드 실패. 위 오류 메시지를 확인하세요." -ForegroundColor Red
}
