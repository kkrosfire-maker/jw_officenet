# Stops Antigravity IDE from forcing the Agent panel open on every startup.
# Antigravity hardcodes "show auxiliary bar + Agent" in its layout init, ignoring
# settings and saved state. This flips that one line to "hidden".
# Re-run after every Antigravity update (updates overwrite the file).
# Restart Antigravity after running.

$ErrorActionPreference = 'Stop'
$app  = Join-Path $env:LOCALAPPDATA 'Programs\Antigravity IDE\resources\app'
$js   = Join-Path $app 'out\vs\workbench\workbench.desktop.main.js'
$prod = Join-Path $app 'product.json'
$utf8 = New-Object System.Text.UTF8Encoding($false)

$text = [IO.File]::ReadAllText($js, $utf8)
$pattern = 'this\.stateModel\.setRuntimeValue\((\w+)\.AUXILIARYBAR_HIDDEN,!1\),this\.state\.initialization\.views\.containerToRestore\.auxiliaryBar=[\w$]+'
$m = [regex]::Matches($text, $pattern)

if ($m.Count -eq 0) {
    if ($text -match 'AUXILIARYBAR_HIDDEN,!0\)/\*hide-agent\*/') { Write-Host 'Already patched. Nothing to do.'; exit 0 }
    Write-Host 'Pattern not found. Antigravity code changed; patch needs updating.'; exit 1
}
if ($m.Count -gt 1) { Write-Host "Pattern found $($m.Count) times; refusing to patch."; exit 1 }

# Backup originals (once per day)
$stamp = Get-Date -Format 'yyMMdd'
$jsBak = $js -replace '\.js$', "_($stamp).js"
$prodBak = $prod -replace '\.json$', "_($stamp).json"
if (-not (Test-Path -LiteralPath $jsBak))   { Copy-Item -LiteralPath $js   $jsBak }
if (-not (Test-Path -LiteralPath $prodBak)) { Copy-Item -LiteralPath $prod $prodBak }

$alias = $m[0].Groups[1].Value
$text = $text.Remove($m[0].Index, $m[0].Length).Insert($m[0].Index, "this.stateModel.setRuntimeValue($alias.AUXILIARYBAR_HIDDEN,!0)/*hide-agent*/")
[IO.File]::WriteAllText($js, $text, $utf8)

# Update checksum so the IDE doesn't warn that the installation is corrupt
$bytes = [IO.File]::ReadAllBytes($js)
$hash = [Convert]::ToBase64String([Security.Cryptography.SHA256]::Create().ComputeHash($bytes)).TrimEnd('=')
$p = [IO.File]::ReadAllText($prod, $utf8)
$p = [regex]::Replace($p, '("vs/workbench/workbench\.desktop\.main\.js":\s*")[^"]*(")', "`${1}$hash`${2}")
[IO.File]::WriteAllText($prod, $p, $utf8)

Write-Host 'Patched. Restart Antigravity IDE.'
Write-Host "Backups: $jsBak"
Write-Host "         $prodBak"
