<#
  install.ps1
  새 PC에서 export.ps1로 만든 zip을 풀어 Claude Code 환경을 복원한다.
  - Node.js 없으면 winget으로 설치
  - Claude Code CLI 없으면 npm으로 설치
  - 전역 settings.json, 워크스페이스 CLAUDE.md / .claude/settings.local.json / .claude/skills 복원
  - 로그인은 브라우저 인증이 필요해 자동화할 수 없으므로 안내만 출력

  사용법 (파라미터 없이 그냥 실행하면 이 스크립트와 같은 폴더의
  claude-code-env.zip을 자동으로 찾아서 쓴다 - install.bat 더블클릭 권장):
    .\install.ps1
    .\install.ps1 -ZipPath "C:\Users\JW\Desktop\claude-code-env.zip"
    .\install.ps1 -WorkspacePath "D:\workspace"
#>

param(
    [string]$ZipPath = (Join-Path $PSScriptRoot "claude-code-env.zip"),
    [string]$WorkspacePath = (Join-Path ([Environment]::GetFolderPath("Desktop")) "workspace")
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ZipPath)) {
    Write-Host "[ERROR] zip 파일을 찾을 수 없음: $ZipPath"
    Write-Host "        install.ps1(또는 install.bat)과 같은 폴더에 claude-code-env.zip을 두거나,"
    Write-Host "        -ZipPath 로 경로를 직접 지정하세요."
    exit 1
}

Write-Host "zip: $ZipPath"
Write-Host "워크스페이스: $WorkspacePath"
Write-Host ""

# 0. 실행 정책을 계정 단위로 영구히 풀어둔다 (RemoteSigned).
#    이렇게 안 해두면 npm이 설치하는 claude.ps1 같은 로컬 스크립트가
#    새 PowerShell 창을 열 때마다 "보안 오류(UnauthorizedAccess)"로 막힌다.
try {
    $currentPolicy = Get-ExecutionPolicy -Scope CurrentUser
    if ($currentPolicy -eq "Restricted" -or $currentPolicy -eq "AllSigned" -or $currentPolicy -eq "Undefined") {
        Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
        Write-Host "[OK] 실행 정책을 CurrentUser/RemoteSigned로 변경 (앞으로 새 창에서도 claude 명령이 바로 동작함)"
    } else {
        Write-Host "[OK] 실행 정책 이미 충분함: $currentPolicy"
    }
} catch {
    Write-Host "[WARN] 실행 정책 변경 실패 (그룹 정책으로 잠겨있을 수 있음): $_"
    Write-Host "       claude 명령이 나중에 막히면 관리자에게 문의하거나 수동으로:"
    Write-Host "       Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force"
}

# PATH를 레지스트리 기준으로 다시 읽어온다 (winget/npm 설치 직후에도
# 같은 프로세스 안에서 바로 새 명령을 찾을 수 있게 하기 위함)
function Update-SessionPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = @($machinePath, $userPath) -join ";"
}

# 1. Node.js 확인/설치
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "Node.js가 없어 설치를 시작합니다 (winget)..."
    try {
        winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
        Update-SessionPath
        $node = Get-Command node -ErrorAction SilentlyContinue
        if ($node) {
            Write-Host "[OK] Node.js 설치 완료 및 이어서 진행: $($node.Version)"
        } else {
            Write-Host "[WARN] Node.js는 설치됐지만 이 창에서 바로 인식이 안 됩니다."
            Write-Host "       탐색기에서 이 폴더를 새로 열어 install.bat을 다시 실행해주세요."
            exit 1
        }
    } catch {
        Write-Host "[ERROR] winget으로 Node.js 설치 실패: $_"
        Write-Host "        https://nodejs.org 에서 LTS 버전을 수동 설치한 뒤 이 스크립트를 다시 실행하세요."
        exit 1
    }
} else {
    Write-Host "[OK] Node.js 이미 설치됨: $($node.Version)"
}

# 2. Claude Code CLI 확인/설치
$claude = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claude) {
    Write-Host "Claude Code CLI를 설치합니다 (npm install -g @anthropic-ai/claude-code)..."
    npm install -g @anthropic-ai/claude-code
    Update-SessionPath
    $claude = Get-Command claude -ErrorAction SilentlyContinue
    if ($claude) {
        Write-Host "[OK] Claude Code CLI 설치 완료"
    } else {
        Write-Host "[WARN] Claude Code CLI는 설치됐지만 이 창에서 바로 인식이 안 될 수 있습니다."
        Write-Host "       탐색기에서 이 폴더를 새로 열어 install.bat을 다시 실행해주세요."
    }
} else {
    Write-Host "[OK] Claude Code CLI 이미 설치됨"
}

# 3. zip 압축 해제
$extractDir = Join-Path $env:TEMP "claude-code-env-import-$(Get-Random)"
Expand-Archive -Path $ZipPath -DestinationPath $extractDir -Force
Write-Host "[OK] 압축 해제: $extractDir"

# 4. 전역 설정 복원
$globalTarget = "$env:USERPROFILE\.claude"
$globalSrc = Join-Path $extractDir "global-settings.json"
if (Test-Path $globalSrc) {
    if (-not (Test-Path $globalTarget)) { New-Item -ItemType Directory -Path $globalTarget | Out-Null }
    $dest = Join-Path $globalTarget "settings.json"
    if (Test-Path $dest) {
        Copy-Item $dest "$dest.bak" -Force
        Write-Host "[INFO] 기존 settings.json을 settings.json.bak으로 백업"
    }
    Copy-Item $globalSrc $dest -Force
    Write-Host "[OK] 전역 settings.json 복원"
}

# 5. 워크스페이스 복원
if (-not (Test-Path $WorkspacePath)) { New-Item -ItemType Directory -Path $WorkspacePath -Force | Out-Null }
$claudeDir = Join-Path $WorkspacePath ".claude"
New-Item -ItemType Directory -Path "$claudeDir\skills" -Force | Out-Null

$claudeMdSrc = Join-Path $extractDir "CLAUDE.md"
if (Test-Path $claudeMdSrc) {
    Copy-Item $claudeMdSrc (Join-Path $WorkspacePath "CLAUDE.md") -Force
    Write-Host "[OK] CLAUDE.md 복원"
}

$settingsLocalSrc = Join-Path $extractDir "claude\settings.local.json"
if (Test-Path $settingsLocalSrc) {
    Copy-Item $settingsLocalSrc (Join-Path $claudeDir "settings.local.json") -Force
    Write-Host "[OK] .claude/settings.local.json 복원"
}

$skillsSrc = Join-Path $extractDir "claude\skills"
if (Test-Path $skillsSrc) {
    Get-ChildItem $skillsSrc | ForEach-Object {
        Copy-Item $_.FullName (Join-Path "$claudeDir\skills" $_.Name) -Recurse -Force
    }
    Write-Host "[OK] 커스텀 스킬 복원 ($((Get-ChildItem $skillsSrc).Count)개)"
}

Remove-Item $extractDir -Recurse -Force

Write-Host ""
Write-Host "===================================================="
Write-Host " 설치 완료. 남은 수동 작업:"
Write-Host "   1) 탐색기에서 `"$WorkspacePath`" 폴더로 이동"
Write-Host "   2) 주소 표시줄 클릭 -> powershell 입력 -> Enter"
Write-Host "   3) claude   (실행하면 브라우저 로그인 창이 뜸 - 계정으로 로그인)"
Write-Host "===================================================="
