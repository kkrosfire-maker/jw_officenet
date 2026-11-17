@echo off
rem 도우미 서버(바탕화면 저장 + PDF 자동 변환)를 숨김 실행하고 Chrome으로 엽니다.
cd /d "%~dp0"
powershell -NoProfile -Command "try{(Invoke-WebRequest http://127.0.0.1:8771/api/ping -UseBasicParsing -TimeoutSec 1)|Out-Null}catch{Start-Process pythonw -ArgumentList 'server.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden; Start-Sleep -Seconds 1}"
start "" chrome "http://127.0.0.1:8771/index.html" 2>nul || start "" "http://127.0.0.1:8771/index.html"
