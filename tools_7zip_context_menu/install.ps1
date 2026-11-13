# 7-Zip 우클릭 메뉴 최상단 등록 (HKCU, 관리자 불필요). 제거: -Uninstall
param([switch]$Uninstall)
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$7z  = 'C:\Program Files\7-Zip\7zG.exe'
$exts = '.zip','.7z','.rar','.tar','.gz','.tgz','.bz2','.xz','.iso','.cab','.wim','.arj','.lzh','.z'
$C = 'HKCU:\Software\Classes'
$key = '0_7zipquick'
$paths = @("$C\Directory\shell\$key", "$C\*\shell\$key") + ($exts | % { "$C\SystemFileAssociations\$_\shell\$key" })
foreach($p in $paths){ Remove-Item -LiteralPath $p -Recurse -Force -ea 0 }
if($Uninstall){ 'removed'; return }
function Add-Verb($path,$label,$cmd,$applies){
  New-Item -Path $path -Force | Out-Null
  New-Item -Path "$path\command" -Force | Out-Null
  Set-ItemProperty -LiteralPath $path -Name '(default)' -Value $label
  Set-ItemProperty -LiteralPath $path -Name 'Icon' -Value $7z
  if($applies){ Set-ItemProperty -LiteralPath $path -Name 'AppliesTo' -Value $applies }
  Set-ItemProperty -LiteralPath "$path\command" -Name '(default)' -Value $cmd
}
$zipCmd = "`"$7z`" a -tzip `"%1.zip`" `"%1`""
$notArc = 'NOT (' + (($exts | % { "System.FileExtension:=`"$_`"" }) -join ' OR ') + ')'
$dirCmd = "`"$7z`" a -tzip `"%1.zip`" `"%1\*`""
Add-Verb "$C\Directory\shell\$key" 'ZIP으로 압축' $dirCmd $null
Add-Verb "$C\*\shell\$key" 'ZIP으로 압축' $zipCmd $notArc
$x = "wscript.exe `"$dir\extract_here.vbs`" `"%1`""
foreach($e in $exts){ Add-Verb "$C\SystemFileAssociations\$e\shell\$key" '현재 폴더에 압축풀기' $x $null }
'installed'
