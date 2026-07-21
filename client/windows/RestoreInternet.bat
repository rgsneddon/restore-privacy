@echo off
REM Compatibility alias → full failsafe "Restore Internet.bat"
setlocal
cd /d "%~dp0"
if exist "%~dp0Restore Internet.bat" (
  call "%~dp0Restore Internet.bat" %*
  exit /b %ERRORLEVEL%
)
REM Inline fallback if spaced name missing
call "%~dp0RestoreInternet_legacy_net_only.bat" %* 2>nul
if errorlevel 1 (
  echo Restore Internet failsafe missing. Reinstall the product package.
  if /I not "%~1"=="/quiet" pause
  exit /b 1
)
exit /b 0
