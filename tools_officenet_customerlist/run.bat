@echo off
rem 도우미 서버(바탕화면 저장 + PDF 자동 변환)를 숨김 실행하고 Chrome으로 엽니다.
cd /d "%~dp0"
set PYEXE=
set PYARG=server.py
pyw -3 -c "import sys" >nul 2>nul && set PYEXE=pyw && set PYARG=-3 server.py
if not defined PYEXE pythonw -c "import sys" >nul 2>nul && set PYEXE=pythonw
if not defined PYEXE (
  echo Python을 찾지 못했어요. 설치.bat 을 먼저 실행하세요.
  pause
  exit /b 1
)
powershell -NoProfile -Command "try{(Invoke-WebRequest http://127.0.0.1:8771/api/ping -UseBasicParsing -TimeoutSec 1)|Out-Null}catch{Start-Process %PYEXE% -ArgumentList '%PYARG%' -WorkingDirectory '%~dp0' -WindowStyle Hidden; Start-Sleep -Seconds 1}"
start "" chrome "http://127.0.0.1:8771/index.html" 2>nul || start "" "http://127.0.0.1:8771/index.html"
