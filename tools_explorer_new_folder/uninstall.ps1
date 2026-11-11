Remove-Item -Path "HKCU:\Software\Classes\Directory\Background\shell\00_NewFolderTop" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "제거 완료"
