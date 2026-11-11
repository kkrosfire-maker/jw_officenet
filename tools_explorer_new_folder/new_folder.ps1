param([string]$Dir, [switch]$NoEdit)
# 우클릭한 폴더 안에 '새 폴더'를 만들고, 탐색기에서 바로 이름 바꾸기 상태로 만든다.
# 이미 있으면 '새 폴더 (2)', '새 폴더 (3)' ...
# 바탕화면이면 아이콘을 메뉴를 누른 마우스 위치로 옮긴다(탐색기 기본 '새로 만들기'처럼). -NoEdit 는 테스트용(이름 바꾸기 생략).
if (-not $Dir -or -not (Test-Path -LiteralPath $Dir)) { exit 1 }
Add-Type -AssemblyName System.Windows.Forms
$cursor = [Windows.Forms.Cursor]::Position   # 컴파일 등으로 마우스가 움직이기 전에 먼저 잡아둔다
$Dir = $Dir.TrimEnd([char]92)
$name = "새 폴더"
$path = Join-Path $Dir $name
$i = 2
while (Test-Path -LiteralPath $path) { $path = Join-Path $Dir "$name ($i)"; $i++ }
[void][IO.Directory]::CreateDirectory($path)
$leaf = Split-Path $path -Leaf

Add-Type -Namespace W -Name U -MemberDefinition @'
[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string t);
[DllImport("user32.dll")] public static extern IntPtr FindWindowEx(IntPtr p, IntPtr a, string c, string t);
[DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, int m, IntPtr w, IntPtr l);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
[DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr h, ref POINT p);
[DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(uint a, bool i, uint pid);
[DllImport("kernel32.dll")] public static extern IntPtr VirtualAllocEx(IntPtr p, IntPtr a, ulong s, uint t, uint pr);
[DllImport("kernel32.dll")] public static extern bool VirtualFreeEx(IntPtr p, IntPtr a, ulong s, uint t);
[DllImport("kernel32.dll")] public static extern bool WriteProcessMemory(IntPtr p, IntPtr a, byte[] b, ulong s, out ulong w);
[DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
[StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
'@

# 바탕화면 아이콘 목록(SysListView32)
function Get-DesktopList {
    $def = [IntPtr]::Zero
    $prog = [W.U]::FindWindow("Progman", [NullString]::Value)
    if ($prog -ne [IntPtr]::Zero) { $def = [W.U]::FindWindowEx($prog, [IntPtr]::Zero, "SHELLDLL_DefView", [NullString]::Value) }
    $wk = [IntPtr]::Zero
    while ($def -eq [IntPtr]::Zero) {
        $wk = [W.U]::FindWindowEx([IntPtr]::Zero, $wk, "WorkerW", [NullString]::Value)
        if ($wk -eq [IntPtr]::Zero) { return [IntPtr]::Zero }
        $def = [W.U]::FindWindowEx($wk, [IntPtr]::Zero, "SHELLDLL_DefView", [NullString]::Value)
    }
    return [W.U]::FindWindowEx($def, [IntPtr]::Zero, "SysListView32", [NullString]::Value)
}
# 이름이 같은 아이콘의 번호(없으면 -1). LVM_FINDITEMW, 탐색기 프로세스 안에 문자열을 잠깐 써 넣는다.
function Find-IconIndex([IntPtr]$list, [string]$text) {
    [uint32]$procId = 0
    [void][W.U]::GetWindowThreadProcessId($list, [ref]$procId)
    $h = [W.U]::OpenProcess(0x38, $false, $procId)
    if ($h -eq [IntPtr]::Zero) { return -1 }
    try {
        $mem = [W.U]::VirtualAllocEx($h, [IntPtr]::Zero, 4096, 0x3000, 4)
        $buf = New-Object byte[] 512
        [BitConverter]::GetBytes([int]2).CopyTo($buf, 0)                       # LVFI_STRING (정확히 일치)
        [BitConverter]::GetBytes([int64]($mem.ToInt64() + 64)).CopyTo($buf, 8)  # psz
        [Text.Encoding]::Unicode.GetBytes($text + "`0").CopyTo($buf, 64)
        [uint64]$wr = 0
        [void][W.U]::WriteProcessMemory($h, $mem, $buf, 512, [ref]$wr)
        $idx = [W.U]::SendMessage($list, 0x1053, [IntPtr](-1), $mem).ToInt32()  # LVM_FINDITEMW
        [void][W.U]::VirtualFreeEx($h, $mem, 0, 0x8000)
        return $idx
    } finally { [void][W.U]::CloseHandle($h) }
}

# 이 폴더를 보여주는 탐색기 창(여러 개면 맨 앞에 있는 것) 또는 바탕화면 찾기
$fg = [W.U]::GetForegroundWindow().ToInt64()
$shell = New-Object -ComObject Shell.Application
$view = $null; $hwnd = $null; $desktop = $false
foreach ($w in @($shell.Windows())) {
    try {
        if ($w.Document.Folder.Self.Path.TrimEnd([char]92) -eq $Dir) {
            if ($null -eq $view -or $w.HWND -eq $fg) { $view = $w.Document; $hwnd = $w.HWND }
        }
    } catch {}
}
if ($null -eq $view) {  # 바탕화면
    try {
        $hwnd = 0
        $disp = $shell.Windows().FindWindowSW([ref]0, [ref]"", 8, [ref]$hwnd, 1)
        if ($disp -and $disp.Document.Folder.Self.Path.TrimEnd([char]92) -eq $Dir) { $view = $disp.Document; $hwnd = $null; $desktop = $true }
    } catch {}
}
if ($null -eq $view) { exit 0 }

# 바탕화면: 새 아이콘이 목록에 나타나면 마우스 위치로 옮긴다 (LVM_SETITEMPOSITION)
if ($desktop) {
    try {
        $list = Get-DesktopList
        if ($list -ne [IntPtr]::Zero) {
            $pt = New-Object W.U+POINT
            $pt.X = $cursor.X; $pt.Y = $cursor.Y
            [void][W.U]::ScreenToClient($list, [ref]$pt)
            for ($n = 0; $n -lt 30; $n++) {
                $idx = Find-IconIndex $list $leaf
                if ($idx -ge 0) {
                    $x = $pt.X - 30; $y = $pt.Y - 30   # 왼쪽 모니터는 좌표가 음수다
                    [void][W.U]::SendMessage($list, 0x100F, [IntPtr]$idx, [IntPtr](($y -shl 16) -bor ($x -band 0xFFFF)))
                    break
                }
                Start-Sleep -Milliseconds 100
            }
        }
    } catch {}
}
if ($NoEdit) { exit 0 }

# 목록에 새 폴더가 나타날 때까지 잠깐 기다렸다가 선택 + 이름 바꾸기 (SVSI_EDIT|DESELECTOTHERS|ENSUREVISIBLE|FOCUSED = 0x1F)
for ($n = 0; $n -lt 30; $n++) {
    try {
        $item = $view.Folder.ParseName($leaf)
        if ($item) {
            if ($hwnd) { [void][W.U]::SetForegroundWindow([IntPtr]$hwnd) }  # 창이 활성이어야 이름 바꾸기 입력칸이 열린다
            Start-Sleep -Milliseconds 150
            $view.SelectItem($item, 0x1F); break
        }
    } catch {}
    Start-Sleep -Milliseconds 100
}
