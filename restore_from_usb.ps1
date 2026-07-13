# Claude Code USB Restore Script
# Run this on the NEW computer (double-click run_restore.bat)

. "$PSScriptRoot\claude-env.ps1"

try {

Write-Host ""
Write-Host "=== Claude Code USB Restore ===" -ForegroundColor Cyan
Write-Host ""

# This script's location = USB claude-backup folder
$usbRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Step counter
$step  = 0
$total = 7

# ── Read backup metadata ──────────────────────────────────────────────────────
$metaFile = "$usbRoot\meta.json"
$sourcePath = $null
if (Test-Path $metaFile) {
    $meta = Get-Content $metaFile -Raw | ConvertFrom-Json
    $sourcePath = $meta.sourceWorkspace
    Write-Host "Backup created: $($meta.backupDate)" -ForegroundColor Gray
    Write-Host "Source path:    $sourcePath" -ForegroundColor Gray
    Write-Host ""
}

# ── Workspace destination ─────────────────────────────────────────────────────
Write-Host "Where do you want to place the workspace on this computer?" -ForegroundColor Yellow
$defaultPath = "$env:USERPROFILE\Desktop\workspace"
if ($sourcePath -and ($sourcePath -ne $defaultPath)) {
    Write-Host "  (Backup source was: $sourcePath)" -ForegroundColor Gray
}
Write-Host "  Default: $defaultPath"
$userInput = Read-Host "Press Enter to use default, or type a full path"

if ([string]::IsNullOrWhiteSpace($userInput)) {
    $destWorkspace = $defaultPath
} else {
    $destWorkspace = $userInput.Trim()
}

Write-Host "  Workspace -> $destWorkspace" -ForegroundColor Gray

# Warn if restore path differs from backup source path
if ($sourcePath -and ($destWorkspace -ne $sourcePath)) {
    Write-Host ""
    Write-Host "  WARNING: Restore path differs from backup source." -ForegroundColor Yellow
    Write-Host "  Backup source: $sourcePath" -ForegroundColor Yellow
    Write-Host "  Restore path:  $destWorkspace" -ForegroundColor Yellow
    Write-Host "  Conversation memory will be stored under the new path and" -ForegroundColor Yellow
    Write-Host "  will NOT share history with the original computer." -ForegroundColor Yellow
}
Write-Host ""

$memKey    = Get-MemoryKey $destWorkspace
$claudeDir = "$env:USERPROFILE\.claude"

# ── 1. Claude Code CLI binary ─────────────────────────────────────────────────
$step++; Write-Host "[$step/$total]  Restoring Claude Code CLI..." -ForegroundColor Green

$cliBin    = "$env:USERPROFILE\.local\bin"
$cliTarget = "$cliBin\claude.exe"
$cliBackup = "$usbRoot\claude-cli\claude.exe"

New-Item -ItemType Directory -Force $cliBin | Out-Null

if (Test-Path $cliBackup) {
    Copy-Item $cliBackup $cliTarget -Force
    Write-Host "       Restored: $cliTarget" -ForegroundColor Gray

    # Prepend ~/.local/bin to PATH so CLI takes priority over any GUI app
    $userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -notlike "*$cliBin*") {
        [System.Environment]::SetEnvironmentVariable("PATH", "$cliBin;$userPath", "User")
        Write-Host "       Added to PATH (front): $cliBin" -ForegroundColor Gray
    }
    $env:PATH = "$cliBin;$env:PATH"
} else {
    Write-Host "       CLI binary not found in backup — installing via winget..." -ForegroundColor Yellow
    winget install Anthropic.Claude --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "       winget install failed. Download manually from https://claude.ai/download" -ForegroundColor Red
    }
}

# ── 2. Warp terminal ──────────────────────────────────────────────────────────
$step++; Write-Host "[$step/$total]  Warp terminal..." -ForegroundColor Green

$warpInstalled = Get-Command warp -ErrorAction SilentlyContinue
if ($warpInstalled) {
    Write-Host "       Already installed." -ForegroundColor Gray
} else {
    $installWarp = Read-Host "       Install Warp terminal? (y/n)"
    if ($installWarp -eq 'y') {
        Write-Host "       Installing via winget..." -ForegroundColor Yellow
        winget install Warp.Warp --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) {
            Write-Host "       Done." -ForegroundColor Gray
        } else {
            Write-Host "       winget install failed. Download manually from https://www.warp.dev" -ForegroundColor Yellow
        }
    } else {
        Write-Host "       Skipped." -ForegroundColor Gray
    }
}

# ── 3. Git Bash (required for Claude Code local sessions) ─────────────────────
$step++; Write-Host "[$step/$total]  Git Bash..." -ForegroundColor Green

$gitInstalled = Get-Command git -ErrorAction SilentlyContinue
if ($gitInstalled) {
    Write-Host "       Already installed. ($(git --version))" -ForegroundColor Gray
} else {
    Write-Host "       Installing via winget (required for Claude Code)..." -ForegroundColor Yellow
    winget install Git.Git --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -eq 0) {
        Write-Host "       Done. Restart terminal after setup to use 'git' command." -ForegroundColor Gray
    } else {
        Write-Host "       winget install failed. Download manually from https://git-scm.com" -ForegroundColor Yellow
    }
}

# ── 4. Workspace ──────────────────────────────────────────────────────────────
$step++; Write-Host "[$step/$total]  Restoring workspace to $destWorkspace..." -ForegroundColor Green

if (Test-Path $destWorkspace) {
    $overwrite = Read-Host "       '$destWorkspace' already exists. Overwrite? (y/n)"
    if ($overwrite -ne 'y') {
        Write-Host "       Skipped." -ForegroundColor Gray
    } else {
        New-Item -ItemType Directory -Force $destWorkspace | Out-Null
        robocopy "$usbRoot\workspace" $destWorkspace /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
        if ($LASTEXITCODE -gt 7) { throw "robocopy failed (exit $LASTEXITCODE)" }
        Write-Host "       Done." -ForegroundColor Gray
    }
} else {
    New-Item -ItemType Directory -Force $destWorkspace | Out-Null
    robocopy "$usbRoot\workspace" $destWorkspace /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -gt 7) { throw "robocopy failed (exit $LASTEXITCODE)" }
    Write-Host "       Done." -ForegroundColor Gray
}

# ── 5. Claude settings ────────────────────────────────────────────────────────
$step++; Write-Host "[$step/$total]  Restoring Claude settings..." -ForegroundColor Green

New-Item -ItemType Directory -Force $claudeDir | Out-Null
foreach ($f in @('settings.json', 'settings.local.json')) {
    if (Test-Path "$usbRoot\claude-settings\$f") {
        Copy-Item "$usbRoot\claude-settings\$f" $claudeDir -Force
        Write-Host "       Restored: $f" -ForegroundColor Gray
    }
}

# ── 6. Memory ─────────────────────────────────────────────────────────────────
$step++; Write-Host "[$step/$total]  Restoring memory..." -ForegroundColor Green

$memoryDest = "$claudeDir\projects\$memKey\memory"
New-Item -ItemType Directory -Force $memoryDest | Out-Null

if (Test-Path "$usbRoot\claude-settings\memory") {
    Copy-Item "$usbRoot\claude-settings\memory\*" $memoryDest -Recurse -Force
    Write-Host "       Stored at: $memoryDest" -ForegroundColor Gray
} else {
    Write-Host "       No memory files found in backup." -ForegroundColor Yellow
}

# ── 7. Skills ─────────────────────────────────────────────────────────────────
$step++; Write-Host "[$step/$total]  Verifying skills..." -ForegroundColor Green

$skillsDir = "$destWorkspace\.claude\skills"

# Collect all skill names: from skills-lock.json + any extra folders in .claude\skills
$lockSkills  = Get-SkillNames $destWorkspace
$folderSkills = if (Test-Path $skillsDir) {
    (Get-ChildItem $skillsDir -Directory).Name
} else { @() }
$allSkills = ($lockSkills + $folderSkills | Sort-Object -Unique)

if ($allSkills.Count -gt 0) {
    Write-Host "       $($allSkills.Count) skill(s) found:" -ForegroundColor Gray
    $allOk = $true
    foreach ($skill in $allSkills) {
        if (Test-Path "$skillsDir\$skill") {
            Write-Host "       [OK]      $skill" -ForegroundColor Green
        } else {
            Write-Host "       [MISSING] $skill" -ForegroundColor Yellow
            $allOk = $false
        }
    }
    if (-not $allOk) {
        Write-Host ""
        Write-Host "       Some skill files are missing." -ForegroundColor Yellow
        Write-Host "       Open a terminal in the workspace and run:  claude skills install" -ForegroundColor Yellow
    }
} else {
    Write-Host "       No skills found." -ForegroundColor Gray
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Restore complete!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next step:" -ForegroundColor Yellow
Write-Host "  Open a NEW terminal window and run 'claude' to log in."
Write-Host "  (Login cannot be automated for security reasons.)"
Write-Host ""

} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host ""
}

Read-Host "Press Enter to close"
