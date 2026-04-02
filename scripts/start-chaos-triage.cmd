@echo off
setlocal
if /I "%~1"=="--no-browser" (
  powershell.exe -ExecutionPolicy Bypass -File "%~dp0start-chaos-triage.ps1" -NoBrowser
) else (
  powershell.exe -ExecutionPolicy Bypass -File "%~dp0start-chaos-triage.ps1"
)
