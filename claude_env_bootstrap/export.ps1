<#
  export.ps1
  이 PC에 세팅된 "Claude Code 환경"(프로젝트 파일 제외)을 zip으로 패키징한다.
  포함 대상:
    - ~/.claude/settings.json           (전역 설정)
    - 워크스페이스 CLAUDE.md             (환경/규칙 템플릿)
    - .claude/settings.local.json       (허용 명령어 목록)
    - .claude/skills/*                  (커스텀 스킬 전체, 심볼릭 링크는 실제 내용으로 풀어서 복사)

  사용법:
    .\export.ps1
    .\export.ps1 -OutputPath "D:\claude-code-env.zip"
#>

param(
    [string]$WorkspaceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputPath = (Join-Path $PSScriptRoot "claude-code-env.zip")
)

$ErrorActionPreference = "Stop"

$staging = Join-Path $env:TEMP "claude-code-env-export-$(Get-Random)"
New-Item -ItemType Directory -Path $staging | Out-Null
New-Item -ItemType Directory -Path "$staging\claude\skills" -Force | Out-Null

Write-Host "워크스페이스 루트: $WorkspaceRoot"

# 1. 전역 설정
$globalSettings = "$env:USERPROFILE\.claude\settings.json"
if (Test-Path $globalSettings) {
    Copy-Item $globalSettings "$staging\global-settings.json"
    Write-Host "[OK] 전역 settings.json 포함"
} else {
    Write-Host "[SKIP] 전역 settings.json 없음 ($globalSettings)"
}

# 2. CLAUDE.md 템플릿
$claudeMd = Join-Path -Path $WorkspaceRoot -ChildPath "CLAUDE.md"
if (Test-Path $claudeMd) {
    Copy-Item $claudeMd "$staging\CLAUDE.md"
    Write-Host "[OK] CLAUDE.md 포함"
} else {
    Write-Host "[SKIP] CLAUDE.md 없음"
}

# 3. 권한 허용 목록
$settingsLocal = Join-Path $WorkspaceRoot ".claude\settings.local.json"
if (Test-Path $settingsLocal) {
    Copy-Item $settingsLocal "$staging\claude\settings.local.json"
    Write-Host "[OK] .claude/settings.local.json 포함"
} else {
    Write-Host "[SKIP] .claude/settings.local.json 없음"
}

# 4. 커스텀 스킬 (심볼릭 링크는 실제 타깃 내용으로 풀어서 복사)
$skillsDir = Join-Path $WorkspaceRoot ".claude\skills"
if (Test-Path $skillsDir) {
    $entries = Get-ChildItem -Path $skillsDir
    foreach ($entry in $entries) {
        $dest = Join-Path "$staging\claude\skills" $entry.Name
        if ($entry.LinkType -eq "SymbolicLink" -or $entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $target = (Get-Item $entry.FullName).Target
            if (-not $target) { $target = $entry.Target }
            if ($target -and (Test-Path $target)) {
                Copy-Item -Path $target -Destination $dest -Recurse -Force
                Write-Host "[OK] 스킬(심볼릭 링크 해제): $($entry.Name)"
            } else {
                Write-Host "[WARN] 링크 타깃을 찾을 수 없음: $($entry.Name) -> $target"
            }
        } else {
            Copy-Item -Path $entry.FullName -Destination $dest -Recurse -Force
            Write-Host "[OK] 스킬: $($entry.Name)"
        }
    }
} else {
    Write-Host "[SKIP] .claude/skills 없음"
}

# 5. 압축
if (Test-Path $OutputPath) { Remove-Item $OutputPath -Force }
Compress-Archive -Path "$staging\*" -DestinationPath $OutputPath -CompressionLevel Optimal
Remove-Item $staging -Recurse -Force

Write-Host ""
Write-Host "완료: $OutputPath"
Write-Host "이 zip과 install.ps1을 새 PC로 옮겨서 실행하세요."
