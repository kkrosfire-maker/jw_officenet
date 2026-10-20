# 바탕화면에 바로가기를 만들거나 갱신한다. build_exe.bat 이 빌드 끝에 호출한다.
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe  = Join-Path $root 'dist\네오벤타정산\네오벤타정산.exe'
$icon = Join-Path $root 'app.ico'

if (-not (Test-Path $exe)) {
    Write-Host "exe 를 찾지 못했습니다: $exe"
    exit 1
}

$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop '네오벤타 정산문서.lnk'

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($lnk)
$sc.TargetPath = $exe
$sc.WorkingDirectory = Split-Path $exe
$sc.Description = '네오벤타 정산문서'
if (Test-Path $icon) { $sc.IconLocation = "$icon,0" }
$sc.Save()

Write-Host "바로가기: $lnk"
