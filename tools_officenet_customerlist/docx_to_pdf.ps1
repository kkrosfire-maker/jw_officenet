# Word로 docx를 열어 PDF로 내보내기 (같은 폴더, 같은 이름). 사용: docx_to_pdf.bat 위로 docx 끌어다 놓기
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Files)
$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false; $word.DisplayAlerts = 0
try {
  foreach ($f in $Files) {
    $src = (Resolve-Path -LiteralPath $f).Path
    $pdf = [System.IO.Path]::ChangeExtension($src, ".pdf")
    $doc = $word.Documents.Open($src, $false, $true)   # 읽기 전용
    $doc.ExportAsFixedFormat($pdf, 17)                  # 17 = PDF
    $doc.Close($false)
    Write-Host "OK: $pdf"
  }
} finally { $word.Quit() }
