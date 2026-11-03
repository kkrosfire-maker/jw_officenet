# 관리자 권한으로 자동 재실행 후, 로그온 때마다 snap_right.ps1 -Watch 를 숨김 실행하는 작업 등록.
# (SS-Compare가 관리자 권한 프로그램이라 일반 권한 스크립트는 창을 움직일 수 없음)
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
  exit
}
# 이전 버전(왼쪽 배치) 작업과 실행 중인 감시 프로세스 정리
Stop-ScheduledTask -TaskName 'SSCompare_SnapLeft' -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'SSCompare_SnapLeft' -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -match 'snap_(left|right)\.ps1' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$script = Join-Path $PSScriptRoot 'snap_right.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`" -Watch"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $id.Name
$principal = New-ScheduledTaskPrincipal -UserId $id.Name -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'SSCompare_SnapRight' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName 'SSCompare_SnapRight'
Write-Host '등록 및 시작 완료'

