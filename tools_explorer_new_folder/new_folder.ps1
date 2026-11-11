param([string]$Dir)
# 우클릭한 폴더 안에 '새 폴더'를 만들고, 탐색기에서 바로 이름 바꾸기 상태로 만든다.
# 이미 있으면 '새 폴더 (2)', '새 폴더 (3)' ...
if (-not $Dir -or -not (Test-Path -LiteralPath $Dir)) { exit 1 }
$Dir = $Dir.TrimEnd('')
$name = "새 폴더"
$path = Join-Path $Dir $name
$i = 2
while (Test-Path -LiteralPath $path) { $path = Join-Path $Dir "$name ($i)"; $i++ }
[void][IO.Directory]::CreateDirectory($path)
$leaf = Split-Path $path -Leaf

# 이 폴더를 보여주는 탐색기 창(여러 개면 맨 앞에 있는 것) 또는 바탕화면 찾기
Add-Type -Namespace W -Name U -MemberDefinition '[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();'
$fg = [W.U]::GetForegroundWindow().ToInt64()
$shell = New-Object -ComObject Shell.Application
$view = $null
foreach ($w in @($shell.Windows())) {
    try {
        if ($w.Document.Folder.Self.Path.TrimEnd('') -eq $Dir) {
            if ($null -eq $view -or $w.HWND -eq $fg) { $view = $w.Document }
        }
    } catch {}
}
if ($null -eq $view) {  # 바탕화면
    try {
        $hwnd = 0
        $disp = $shell.Windows().FindWindowSW([ref]0, [ref]"", 8, [ref]$hwnd, 1)
        if ($disp -and $disp.Document.Folder.Self.Path.TrimEnd('') -eq $Dir) { $view = $disp.Document }
    } catch {}
}
if ($null -eq $view) { exit 0 }

# 목록에 새 폴더가 나타날 때까지 잠깐 기다렸다가 선택 + 이름 바꾸기 (SVSI_EDIT|DESELECTOTHERS|ENSUREVISIBLE|FOCUSED = 0x1F)
for ($n = 0; $n -lt 30; $n++) {
    try {
        $item = $view.Folder.ParseName($leaf)
        if ($item) { $view.SelectItem($item, 0x1F); break }
    } catch {}
    Start-Sleep -Milliseconds 100
}
