@echo off
REM Restore Privacy — emergency residual restore (Windows)
REM Undoes dual /1 blackhole routes, product server pin, RPT-KS kill-switch,
REM and re-enables IPv6 adapter bindings. Safe to run when already clean.
setlocal EnableExtensions
cd /d "%~dp0"

set "QUIET=0"
set "NODE=82.221.101.241"
if /I "%~1"=="/quiet" set "QUIET=1"
if /I "%~2"=="/quiet" set "QUIET=1"
if not "%~1"=="" if /I not "%~1"=="/quiet" set "NODE=%~1"

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator to restore internet routes...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '/quiet' -Verb RunAs -Wait"
  exit /b %ERRORLEVEL%
)

echo Restoring residual path (dual /1, pin, kill-switch, IPv6)...

REM Dual /1 catch-alls (blackhole if left after Wintun close)
route delete 0.0.0.0 mask 128.0.0.0 >nul 2>&1
route delete 128.0.0.0 mask 128.0.0.0 >nul 2>&1
route delete 0.0.0.0 mask 128.0.0.0 0.0.0.0 >nul 2>&1
route delete 128.0.0.0 mask 128.0.0.0 0.0.0.0 >nul 2>&1

REM Product node server pin
route delete %NODE% mask 255.255.255.255 >nul 2>&1

REM Kill-switch + IPv6 restore
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Continue'; Get-NetFirewallRule -EA SilentlyContinue | Where-Object { $_.DisplayName -like 'RPT-KS-*' } | Remove-NetFirewallRule -EA SilentlyContinue; $sp=Join-Path $env:ProgramData 'RestorePrivacy\ks-outbound-state.json'; if (Test-Path $sp) { try { $p=Get-Content $sp -Raw|ConvertFrom-Json; foreach($n in @('Domain','Private','Public')){ $v=$p.$n; if(-not $v){$v='Allow'}; Set-NetFirewallProfile -Name $n -DefaultOutboundAction $v -EA SilentlyContinue }; Remove-Item $sp -Force -EA SilentlyContinue } catch { foreach($n in @('Domain','Private','Public')){ Set-NetFirewallProfile -Name $n -DefaultOutboundAction Allow -EA SilentlyContinue } } } else { foreach($n in @('Domain','Private','Public')){ Set-NetFirewallProfile -Name $n -DefaultOutboundAction Allow -EA SilentlyContinue } }; Get-NetAdapter -EA SilentlyContinue | ForEach-Object { Enable-NetAdapterBinding -Name $_.Name -ComponentID ms_tcpip6 -Confirm:$false -EA SilentlyContinue }; netsh interface teredo set state default | Out-Null; Write-Output RPT_RESIDUAL_RESTORE_OK"

if "%QUIET%"=="1" exit /b 0
echo.
echo Internet residual path restored. You can close this window.
pause
exit /b 0
