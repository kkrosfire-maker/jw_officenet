# 탐색기 빈 곳 우클릭 메뉴 맨 위에 '새 폴더' 추가 (현재 사용자 전용, 관리자 권한 불필요)
$script = Join-Path $PSScriptRoot "new_folder.ps1"
$key = "HKCU:\Software\Classes\Directory\Background\shell\00_NewFolderTop"
New-Item -Path "$key\command" -Force | Out-Null
Set-ItemProperty -Path $key -Name "(default)" -Value "새 폴더"
Set-ItemProperty -Path $key -Name "MUIVerb" -Value "새 폴더"
Set-ItemProperty -Path $key -Name "Position" -Value "Top"
Set-ItemProperty -Path $key -Name "Icon" -Value "imageres.dll,-5303"
Set-ItemProperty -Path "$key\command" -Name "(default)" -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`" `"%V`""
Write-Host "등록 완료"
