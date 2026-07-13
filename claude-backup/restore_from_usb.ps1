# Claude Code USB Restore Script
# Run this on the NEW computer (double-click run_restore.bat)

try {

Write-Host ""
Write-Host "=== Claude Code USB Restore ===" -ForegroundColor Cyan
Write-Host ""

# This script's location = USB claude-backup folder
$usbRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── Workspace destination ────────────────────────────────────────────────────
Write-Host "Where do you want to place the workspace on this computer?" -ForegroundColor Yellow
Write-Host "  Default: $env:USERPROFILE\Desktop\workspace"
$userInput = Read-Host "Press Enter to use default, or type a full path"

if ([string]::IsNullOrWhiteSpace($userInput)) {
    $destWorkspace = "$env:USERPROFILE\Desktop\workspace"
} else {
    $destWorkspace = $userInput.Trim()
}

Write-Host "  Workspace -> $destWorkspace" -ForegroundColor Gray
Write-Host ""

# Derive memory key from chosen workspace path
# e.g.  C:\Users\NewUser\Desktop\workspace  ->  C--Users-NewUser-Desktop-workspace
$drive  = $destWorkspace.Substring(0, 1)
$rest   = $destWorkspace.Substring(2) -replace '\\', '-'
$memKey = "$drive-$rest"

# ── 1. Claude Code CLI binary ────────────────────────────────────────────────
Write-Host "[1/8]  Restoring Claude Code CLI..." -ForegroundColor Green

$cliBin    = "$env:USERPROFILE\.local\bin"
$cliTarget = "$cliBin\claude.exe"
$cliBackup = "$usbRoot\claude-cli\claude.exe"

New-Item -ItemType Directory -Force $cliBin | Out-Null

if (Test-Path $cliBackup) {
    Copy-Item $cliBackup $cliTarget -Force
    Write-Host "       Restored: $cliTarget" -ForegroundColor Gray

    # Prepend ~/.local/bin to user PATH so CLI takes priority over GUI app
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

# ── 2. Warp installation ─────────────────────────────────────────────────────
Write-Host "[2/8]  Warp terminal..." -ForegroundColor Green

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

# ── 3. Git Bash installation (required for Claude Code local sessions) ────────
Write-Host "[3/8]  Git Bash..." -ForegroundColor Green

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

# ── 4. Workspace restore ─────────────────────────────────────────────────────
Write-Host "[4/8]  Restoring workspace to $destWorkspace..." -ForegroundColor Green

if (Test-Path $destWorkspace) {
    $overwrite = Read-Host "       '$destWorkspace' already exists. Overwrite? (y/n)"
    if ($overwrite -eq 'y') {
        Copy-Item "$usbRoot\workspace\*" $destWorkspace -Recurse -Force
        Write-Host "       Done." -ForegroundColor Gray
    } else {
        Write-Host "       Skipped." -ForegroundColor Gray
    }
} else {
    New-Item -ItemType Directory -Force $destWorkspace | Out-Null
    Copy-Item "$usbRoot\workspace\*" $destWorkspace -Recurse -Force
    Write-Host "       Done." -ForegroundColor Gray
}

# ── 5. Claude global settings ────────────────────────────────────────────────
Write-Host "[5/8]  Restoring Claude settings..." -ForegroundColor Green

$claudeDir = "$env:USERPROFILE\.claude"
New-Item -ItemType Directory -Force $claudeDir | Out-Null

foreach ($f in @('settings.json', 'settings.local.json')) {
    if (Test-Path "$usbRoot\claude-settings\$f") {
        Copy-Item "$usbRoot\claude-settings\$f" $claudeDir -Force
        Write-Host "       Restored: $f" -ForegroundColor Gray
    }
}

# ── 6. Memory restore ────────────────────────────────────────────────────────
Write-Host "[6/8]  Restoring memory..." -ForegroundColor Green

$memoryDest = "$claudeDir\projects\$memKey\memory"
New-Item -ItemType Directory -Force $memoryDest | Out-Null

if (Test-Path "$usbRoot\claude-settings\memory") {
    Copy-Item "$usbRoot\claude-settings\memory\*" $memoryDest -Recurse -Force
    Write-Host "       Stored at: $memoryDest" -ForegroundColor Gray
} else {
    Write-Host "       No memory files found in backup." -ForegroundColor Yellow
}

# ── 7. Skills verification ───────────────────────────────────────────────────
Write-Host "[7/8]  Verifying skills..." -ForegroundColor Green

$skillsLock = "$destWorkspace\skills-lock.json"
$agentsDir  = "$destWorkspace\.agents\skills"

if (Test-Path $skillsLock) {
    $skills = (Get-Content $skillsLock -Raw | ConvertFrom-Json).skills.PSObject.Properties.Name
    Write-Host "       $($skills.Count) skill(s) found in skills-lock.json:" -ForegroundColor Gray

    $allOk = $true
    foreach ($skill in $skills) {
        if (Test-Path "$agentsDir\$skill") {
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
    Write-Host "       No skills-lock.json found — no skills to verify." -ForegroundColor Gray
}

# ── 8. Done ──────────────────────────────────────────────────────────────────
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
