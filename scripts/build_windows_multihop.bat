@echo off
REM One-command Windows multihop residual rebuild for catalog 0.4.0
REM Run from repo root on Windows x64 (PowerShell or cmd).
REM See: client\windows\WINDOWS_HANDOFF_0.4.0.md
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv ...
  py -3 -m venv .venv 2>nul || python -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install -q --upgrade pip
python -m pip install -q pyinstaller cryptography

echo.
echo === Restore Privacy 0.4.0 Windows multihop rebuild ===
python scripts\build_windows_multihop.py %*
set ERR=%ERRORLEVEL%
if not %ERR%==0 (
  echo.
  echo BUILD FAILED exit=%ERR%
  exit /b %ERR%
)
echo.
echo BUILD OK
echo Output: releases\0.4.0\restore-privacy-client-0.4.0-windows-x64-setup.exe
endlocal
