@echo off
REM =============================================================================
REM Restore Internet — failsafe residual restore + complete product removal (Windows)
REM Display name: "Restore Internet"
REM 1) Restore normal internet (dual /1, pin, RPT-KS, IPv6)
REM 2) Remove product firewall rules (RPT-FW / RPT-KS)
REM 3) Stop product process and delete install tree, shortcuts, product secrets
REM =============================================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "QUIET=0"
set "NODE=82.221.101.241"
set "APPNAME=RestorePrivacy"
set "DISPLAY=Privacy Restored"
if /I "%~1"=="/quiet" set "QUIET=1"
if /I "%~2"=="/quiet" set "QUIET=1"
if not "%~1"=="" if /I not "%~1"=="/quiet" set "NODE=%~1"

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator for Restore Internet (network + uninstall)...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '/quiet' -Verb RunAs -Wait"
  exit /b %ERRORLEVEL%
)

title Restore Internet — Restore Privacy failsafe
echo.
echo === Restore Internet ===
echo Restoring normal internet, then removing Restore Privacy from this PC...
echo.

REM ----- 1) Residual network restore -----
echo [1/4] Removing residual dual /1 routes and server pin...
route delete 0.0.0.0 mask 128.0.0.0 >nul 2>&1
route delete 128.0.0.0 mask 128.0.0.0 >nul 2>&1
route delete 0.0.0.0 mask 128.0.0.0 0.0.0.0 >nul 2>&1
route delete 128.0.0.0 mask 128.0.0.0 0.0.0.0 >nul 2>&1
route delete %NODE% mask 255.255.255.255 >nul 2>&1

echo [2/4] Clearing RPT kill-switch / profile Block and re-enabling IPv6...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Continue';" ^
  "Get-NetFirewallRule -EA SilentlyContinue | Where-Object { $_.DisplayName -like 'RPT-KS-*' -or $_.DisplayName -like 'RPT-FW-*' } | Remove-NetFirewallRule -EA SilentlyContinue;" ^
  "$sp=Join-Path $env:ProgramData 'RestorePrivacy\ks-outbound-state.json';" ^
  "if (Test-Path $sp) { try { $p=Get-Content $sp -Raw|ConvertFrom-Json; foreach($n in @('Domain','Private','Public')){ $v=$p.$n; if(-not $v){$v='Allow'}; Set-NetFirewallProfile -Name $n -DefaultOutboundAction $v -EA SilentlyContinue }; Remove-Item $sp -Force -EA SilentlyContinue } catch { foreach($n in @('Domain','Private','Public')){ Set-NetFirewallProfile -Name $n -DefaultOutboundAction Allow -EA SilentlyContinue } } } else { foreach($n in @('Domain','Private','Public')){ Set-NetFirewallProfile -Name $n -DefaultOutboundAction Allow -EA SilentlyContinue } };" ^
  "Get-NetAdapter -EA SilentlyContinue | ForEach-Object { Enable-NetAdapterBinding -Name $_.Name -ComponentID ms_tcpip6 -Confirm:$false -EA SilentlyContinue };" ^
  "netsh interface teredo set state default | Out-Null;" ^
  "Write-Output RPT_RESTORE_INTERNET_NET_OK"

echo [3/4] Stopping product process...
taskkill /F /IM RestorePrivacy.exe >nul 2>&1
taskkill /F /IM "Restore Privacy.exe" >nul 2>&1
timeout /t 1 /nobreak >nul 2>&1

echo [4/4] Removing install tree, shortcuts, and product secrets...
set "INSTALL=%LOCALAPPDATA%\Programs\%APPNAME%"
if exist "%INSTALL%" (
  rmdir /s /q "%INSTALL%" 2>nul
)
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\%APPNAME%" (
  rmdir /s /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\%APPNAME%" 2>nul
)
del /q "%USERPROFILE%\Desktop\%DISPLAY%.lnk" 2>nul
del /q "%USERPROFILE%\Desktop\%APPNAME%.lnk" 2>nul
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\%DISPLAY%.lnk" 2>nul
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Restore Internet*.lnk" 2>nul
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\%APPNAME%\*.lnk" 2>nul

REM Product secrets (complete removal)
if exist "%USERPROFILE%\.restore-privacy" (
  rmdir /s /q "%USERPROFILE%\.restore-privacy" 2>nul
)
if exist "%ProgramData%\RestorePrivacy" (
  rmdir /s /q "%ProgramData%\RestorePrivacy" 2>nul
)

REM If we are running from the install dir, schedule self-delete of remaining files
set "HERE=%~dp0"
echo %HERE% | find /I "%LOCALAPPDATA%\Programs\%APPNAME%" >nul 2>&1
if not errorlevel 1 (
  start "" cmd /c "timeout /t 2 /nobreak >nul & rmdir /s /q \"%INSTALL%\" 2>nul"
)

echo.
echo Restore Internet complete.
echo - Normal internet routing should work again.
echo - Restore Privacy has been removed from this PC (reinstall to use again).
echo.
if "%QUIET%"=="1" exit /b 0
pause
exit /b 0
