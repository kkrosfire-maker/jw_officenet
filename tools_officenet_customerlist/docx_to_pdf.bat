@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0docx_to_pdf.ps1" %*
if errorlevel 1 pause
