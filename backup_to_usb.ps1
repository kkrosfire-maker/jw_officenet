# Claude Code USB Backup Script
# Run this on the CURRENT computer

param(
    [string]$DriveLetter = ""
)

. "$PSScriptRoot\claude-env.ps1"

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

# Step counter
$step  = 0
$total = 5

# Create backup folders
New-Item -ItemType Directory -Force "$usbRoot\workspace"              | Out-Null
New-Item -ItemType Directory -Force "$usbRoot\claude-settings\memory" | Out-Null
New-Item -ItemType Directory -Force "$usbRoot\claude-cli"             | Out-Null

$workspaceSrc = "$env:USERPROFILE\Desktop\workspace"
$claudeDir    = "$env:USERPROFILE\.claude"
$memKey       = Get-MemoryKey $workspaceSrc

# Save meta.json so restore can warn on path mismatch
@{
    backupDate      = (Get-Date -Format 'yyyy-MM-dd HH:mm')
    sourceWorkspace = $workspaceSrc
    memoryKey       = $memKey
} | ConvertTo-Json | Out-File "$usbRoot\meta.json" -Encoding utf8

# ── 1. Workspace ─────────────────────────────────────────────────────────────
$step++; Write-Host "[$step/$total]  Copying workspace..." -ForegroundColor Green

$excludeDirs = @('__pycache__', '.git', 'node_modules', 'dist', 'build', '.venv', 'venv')

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

# ── 2. Claude global settings ─────────────────────────────────────────────────
$step++; Write-Host "[$step/$total]  Copying Claude settings..." -ForegroundColor Green

foreach ($f in @('settings.json', 'settings.local.json')) {
    if (Test-Path "$claudeDir\$f") {
        Copy-Item "$claudeDir\$f" "$usbRoot\claude-settings\" -Force
        Write-Host "       Copied: $f" -ForegroundColor Gray
    }
}

# ── 3. Memory ─────────────────────────────────────────────────────────────────
$step++; Write-Host "[$step/$total]  Copying memory..." -ForegroundColor Green

$memoryDir = "$claudeDir\projects\$memKey\memory"
if (Test-Path $memoryDir) {
    Copy-Item "$memoryDir\*" "$usbRoot\claude-settings\memory\" -Recurse -Force
    Write-Host "       Done." -ForegroundColor Gray
} else {
    Write-Host "       Memory folder not found, skipped." -ForegroundColor Yellow
}

# ── 4. Claude Code CLI binary ─────────────────────────────────────────────────
$step++; Write-Host "[$step/$total]  Copying Claude Code CLI binary..." -ForegroundColor Green

$claudeCli = "$env:USERPROFILE\.local\bin\claude.exe"
if (Test-Path $claudeCli) {
    Copy-Item $claudeCli "$usbRoot\claude-cli\claude.exe" -Force
    Write-Host "       Copied: claude.exe" -ForegroundColor Gray
} else {
    Write-Host "       CLI binary not found at ~/.local/bin/claude.exe — skipped." -ForegroundColor Yellow
}

# ── 5. Skills ─────────────────────────────────────────────────────────────────
$step++; Write-Host "[$step/$total]  Checking skills..." -ForegroundColor Green

$skillNames = Get-SkillNames $workspaceSrc
if ($skillNames.Count -gt 0) {
    Write-Host "       $($skillNames.Count) skill(s) included in backup:" -ForegroundColor Gray
    $skillNames | ForEach-Object { Write-Host "         - $_" -ForegroundColor Gray }
} else {
    Write-Host "       No skills-lock.json found." -ForegroundColor Yellow
}

# Copy restore scripts and shared module to USB
foreach ($f in @('restore_from_usb.ps1', 'run_restore.bat', 'claude-env.ps1')) {
    if (Test-Path "$workspaceSrc\$f") {
        Copy-Item "$workspaceSrc\$f" "$usbRoot\" -Force
    }
}

# ── Write README.txt ──────────────────────────────────────────────────────────
$skillList = if ($skillNames.Count -gt 0) {
    ($skillNames | ForEach-Object { "  - $_" }) -join "`r`n"
} else { "  (none)" }

@"
=== Claude Code Backup ===
Created: $(Get-Date -Format 'yyyy-MM-dd HH:mm')
Source:  $workspaceSrc

HOW TO RESTORE ON A NEW COMPUTER
----------------------------------
1. Insert this USB drive into the new computer.
2. Double-click  run_restore.bat
   (If Windows blocks it: right-click -> Run as administrator)
3. Follow the on-screen prompts.
   - You will be asked where to place the workspace folder.
   - Default is  Desktop\workspace  (press Enter to accept).
   - If you choose a different path, memory may not link correctly.
4. After the restore completes, open a NEW terminal and run 'claude'
   to log in to your Anthropic account.
   (Login cannot be automated for security reasons.)

WHAT IS INCLUDED
-----------------
  workspace\           -> All project files, scripts, and skills
  claude-settings\     -> Claude settings files + conversation memory
  claude-cli\          -> Claude Code CLI binary (claude.exe)
  meta.json            -> Backup metadata (source path, date)

SKILLS INCLUDED
-----------------
$skillList

NOTES
------
- Skills (.agents\skills\) are restored as part of the workspace.
- If any skill shows [MISSING] during restore, open a terminal
  in the workspace folder and run:  claude skills install
- Restoring to a different path than '$workspaceSrc'
  will disconnect conversation memory from the workspace.
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
