# 사진 분류 프로그램 - 실행파일 빌드 스크립트
# 실행: PowerShell 에서  .\build.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=== 빌드 시작 ===" -ForegroundColor Cyan

python -m PyInstaller `
    --onefile `
    --windowed `
    --name "사진분류프로그램" `
    main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=== 빌드 완료 ===" -ForegroundColor Green
    Write-Host "실행파일 위치: $ScriptDir\dist\사진분류프로그램.exe" -ForegroundColor Yellow
} else {
    Write-Host "=== 빌드 실패 ===" -ForegroundColor Red
}
