@echo off
REM Restore Privacy — allow residual Connect through Windows Defender Firewall
REM Scoped allows only (product node UDP + this install's .exe). No kill-switch.
setlocal EnableExtensions
cd /d "%~dp0"

set "QUIET=0"
if /I "%~1"=="/quiet" set "QUIET=1"

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator to add Windows Defender Firewall allows...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '/quiet' -Verb RunAs -Wait"
  exit /b %ERRORLEVEL%
)

set "NODE=82.221.101.241"
set "PORT=44044"
set "EXE="
if exist "%~dp0RestorePrivacy.exe" set "EXE=%~dp0RestorePrivacy.exe"

echo Adding scoped Windows Defender Firewall allows for Restore Privacy...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $pfx='RPT-FW'; $node='%NODE%'; $port=%PORT%; $exe='%EXE%';" ^
  "Get-NetFirewallRule -EA SilentlyContinue | Where-Object { $_.DisplayName -like ($pfx+'-*') } | Remove-NetFirewallRule -EA SilentlyContinue;" ^
  "New-NetFirewallRule -DisplayName ($pfx+'-allow-node-udp') -Direction Outbound -Action Allow -Protocol UDP -RemoteAddress $node -RemotePort $port -Enabled True -Profile Any | Out-Null;" ^
  "New-NetFirewallRule -DisplayName ($pfx+'-allow-node-any') -Direction Outbound -Action Allow -RemoteAddress $node -Enabled True -Profile Any -EA SilentlyContinue | Out-Null;" ^
  "if ($exe -and (Test-Path -LiteralPath $exe)) { New-NetFirewallRule -DisplayName ($pfx+'-allow-program') -Direction Outbound -Action Allow -Program $exe -Enabled True -Profile Any -EA SilentlyContinue | Out-Null; New-NetFirewallRule -DisplayName ($pfx+'-allow-program-in') -Direction Inbound -Action Allow -Program $exe -Enabled True -Profile Any -EA SilentlyContinue | Out-Null };" ^
  "if (-not (Get-NetFirewallRule -DisplayName ($pfx+'-allow-node-udp') -EA SilentlyContinue)) { throw 'missing RPT-FW-allow-node-udp' };" ^
  "Write-Output RPT_FW_ALLOW_OK"

if errorlevel 1 (
  echo Failed to add firewall allows.
  if "%QUIET%"=="0" pause
  exit /b 1
)

if "%QUIET%"=="1" exit /b 0
echo.
echo Windows Defender Firewall allows installed for residual Connect.
echo You can close this window and open Privacy Restored.
pause
exit /b 0
