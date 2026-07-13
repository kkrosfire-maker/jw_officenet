# Claude Code USB Backup Script
# Run this on the CURRENT computer

param(
    [string]$DriveLetter = ""
)

try {

Write-Host ""
Write-Host "=== Claude Code USB Backup ===" -ForegroundColor Cyan
Write-Host ""

# Auto-detect USB drives
$usbDrives = Get-PSDrive -PSProvider FileSystem | Where-Object {
    $_.Root -match '^[D-Z]:\\$' -and (Test-Path $_.Root)
} | Select-Object Name, Root, @{N='Label';E={(Get-Volume -DriveLetter $_.Name -ErrorAction SilentlyContinue).FileSystemLabel}}

if ($usbDrives.Count -eq 0) {
    Write-Host "No USB drives found. Insert a USB drive and run again." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "Detected drives:" -ForegroundColor Yellow
$usbDrives | ForEach-Object { Write-Host "  $($_.Name): ($($_.Label))  $($_.Root)" }
Write-Host ""

if (-not $DriveLetter) {
    $DriveLetter = Read-Host "Enter the USB drive letter (e.g. E)"
}
$usbRoot = "${DriveLetter}:\claude-backup"

Write-Host ""
Write-Host "Backup destination: $usbRoot" -ForegroundColor Yellow
Write-Host ""

# Create backup folders
New-Item -ItemType Directory -Force "$usbRoot\workspace"             | Out-Null
New-Item -ItemType Directory -Force "$usbRoot\claude-settings\memory" | Out-Null
New-Item -ItemType Directory -Force "$usbRoot\claude-cli"            | Out-Null

# ── 1. Workspace ────────────────────────────────────────────────────────────
Write-Host "[1/4]  Copying workspace..." -ForegroundColor Green

$excludeDirs  = @('__pycache__', '.git', 'node_modules', 'dist', 'build', '.venv', 'venv')
$workspaceSrc = "$env:USERPROFILE\Desktop\workspace"

Get-ChildItem $workspaceSrc -Recurse -Force | Where-Object {
    $item = $_
    $skip = $false
    foreach ($ex in $excludeDirs) {
        if ($item.FullName -match [regex]::Escape("\$ex")) { $skip = $true; break }
    }
    -not $skip
} | ForEach-Object {
    $dest = $_.FullName.Replace($workspaceSrc, "$usbRoot\workspace")
    if ($_.PSIsContainer) {
        New-Item -ItemType Directory -Force $dest | Out-Null
    } else {
        Copy-Item $_.FullName $dest -Force
    }
}

Write-Host "       Done." -ForegroundColor Gray

# ── 2. Claude global settings ────────────────────────────────────────────────
Write-Host "[2/4]  Copying Claude settings..." -ForegroundColor Green

$claudeDir = "$env:USERPROFILE\.claude"
foreach ($f in @('settings.json', 'settings.local.json')) {
    if (Test-Path "$claudeDir\$f") {
        Copy-Item "$claudeDir\$f" "$usbRoot\claude-settings\" -Force
        Write-Host "       Copied: $f" -ForegroundColor Gray
    }
}

# ── 3. Memory ────────────────────────────────────────────────────────────────
Write-Host "[3/4]  Copying memory..." -ForegroundColor Green

# Derive memory key from current workspace path  (C:\Users\JW\Desktop\workspace -> C--Users-JW-Desktop-workspace)
$drive     = $workspaceSrc.Substring(0, 1)
$rest      = $workspaceSrc.Substring(2) -replace '\\', '-'
$memKey    = "$drive-$rest"
$memoryDir = "$claudeDir\projects\$memKey\memory"

if (Test-Path $memoryDir) {
    Copy-Item "$memoryDir\*" "$usbRoot\claude-settings\memory\" -Recurse -Force
    Write-Host "       Done." -ForegroundColor Gray
} else {
    Write-Host "       Memory folder not found, skipped." -ForegroundColor Yellow
}

# ── 4. Claude Code CLI binary ────────────────────────────────────────────────
Write-Host "[4/5]  Copying Claude Code CLI binary..." -ForegroundColor Green

$claudeCli = "$env:USERPROFILE\.local\bin\claude.exe"
if (Test-Path $claudeCli) {
    Copy-Item $claudeCli "$usbRoot\claude-cli\claude.exe" -Force
    Write-Host "       Copied: claude.exe" -ForegroundColor Gray
} else {
    Write-Host "       CLI binary not found at ~/.local/bin/claude.exe — skipped." -ForegroundColor Yellow
}

# ── 5. Skills check ──────────────────────────────────────────────────────────
Write-Host "[5/5]  Checking skills..." -ForegroundColor Green

$skillsLock = "$workspaceSrc\skills-lock.json"
$skillNames = @()

if (Test-Path $skillsLock) {
    $skillNames = (Get-Content $skillsLock -Raw | ConvertFrom-Json).skills.PSObject.Properties.Name
    Write-Host "       $($skillNames.Count) skill(s) included in backup:" -ForegroundColor Gray
    $skillNames | ForEach-Object { Write-Host "         - $_" -ForegroundColor Gray }
} else {
    Write-Host "       No skills-lock.json found." -ForegroundColor Yellow
}

# Copy restore scripts to USB
Copy-Item "$workspaceSrc\restore_from_usb.ps1" "$usbRoot\" -Force
if (Test-Path "$workspaceSrc\run_restore.bat") {
    Copy-Item "$workspaceSrc\run_restore.bat" "$usbRoot\" -Force
}

# ── Write README.txt ─────────────────────────────────────────────────────────
$skillList = if ($skillNames.Count -gt 0) { ($skillNames | ForEach-Object { "  - $_" }) -join "`r`n" } else { "  (none)" }

@"
=== Claude Code Backup ===
Created: $(Get-Date -Format 'yyyy-MM-dd HH:mm')

HOW TO RESTORE ON A NEW COMPUTER
----------------------------------
1. Insert this USB drive into the new computer.
2. Double-click  run_restore.bat
   (If Windows blocks it: right-click -> Run as administrator)
3. Follow the on-screen prompts.
   - You will be asked where to place the workspace folder.
   - Default is  Desktop\workspace  (press Enter to accept).
4. After the restore completes, open a terminal and run 'claude'
   to log in to your Anthropic account.
   (Login cannot be automated for security reasons.)

WHAT IS INCLUDED
-----------------
  workspace\           -> All project files, scripts, and skills
  claude-settings\     -> Claude settings files + conversation memory
  claude-cli\          -> Claude Code CLI binary (claude.exe)

SKILLS INCLUDED
-----------------
$skillList

NOTES
------
- Skills (.agents\skills\) are restored as part of the workspace.
- If any skill shows [MISSING] during restore, open a terminal
  in the workspace folder and run:  claude skills install
"@ | Out-File "$usbRoot\README.txt" -Encoding utf8

Write-Host ""
Write-Host "Backup complete!" -ForegroundColor Cyan
Write-Host "USB folder: $usbRoot"
Write-Host ""

} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host ""
}

Read-Host "Press Enter to close"
