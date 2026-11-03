# SS-Compare 창을 화면 왼쪽 절반(작업표시줄 제외, 위아래 꽉 참)에 배치한다.
# 사용: snap_left.ps1          -> 지금 떠 있는 창 1회 배치
#       snap_left.ps1 -Watch   -> 계속 대기하며 새로 뜨는 창마다 배치
param([switch]$Watch)

Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class W32 {
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int ht, bool r);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
'@
[void][W32]::SetProcessDPIAware()

function Snap-Right($p) {
  # 보조 모니터(기본 모니터가 아닌 화면)의 오른쪽 절반. 보조 모니터가 없으면 기본 모니터.
  $scr = [System.Windows.Forms.Screen]::AllScreens | Where-Object { -not $_.Primary } | Select-Object -First 1
  if (-not $scr) { $scr = [System.Windows.Forms.Screen]::PrimaryScreen }
  $wa = $scr.WorkingArea
  [void][W32]::ShowWindow($p.MainWindowHandle, 9)   # SW_RESTORE (최대화 해제)
  # 보이지 않는 윈도우 테두리(좌우·아래 약 7px) 보정
  $b = 7
  $half = [int]($wa.Width / 2)
  [void][W32]::MoveWindow($p.MainWindowHandle, $wa.X + $half - $b, $wa.Y, $half + 2 * $b, $wa.Height + $b, $true)
}

# 로그인 창 등은 건드리지 않고, 메인 창(제목에 [화면이름]이 붙는 창)만 한 번 배치한다.
$done = @{}
do {
  Get-Process -Name 'SS-Compare' -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -match 'Partner-\s*\S+' -and -not $done.ContainsKey($_.Id) } |
    ForEach-Object { Start-Sleep -Milliseconds 800; $_.Refresh(); Snap-Right $_; $done[$_.Id] = 1 }
  if ($Watch) { Start-Sleep -Seconds 2 }
} while ($Watch)
