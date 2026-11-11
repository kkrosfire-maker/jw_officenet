param([string]$Dir)
# 우클릭한 폴더 안에 '새 폴더'를 만든다. 이미 있으면 '새 폴더 (2)', '새 폴더 (3)' ...
if (-not $Dir -or -not (Test-Path -LiteralPath $Dir)) { exit 1 }
$name = "새 폴더"
$path = Join-Path $Dir $name
$i = 2
while (Test-Path -LiteralPath $path) { $path = Join-Path $Dir "$name ($i)"; $i++ }
[void][IO.Directory]::CreateDirectory($path)
