# Single-click RESTORE entry (Windows)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Base = if (Test-Path (Join-Path $Here "rpos\installer")) { $Here }
  elseif (Test-Path (Join-Path $Here "..\rpos\installer")) { (Resolve-Path (Join-Path $Here "..")).Path }
  else { (Resolve-Path (Join-Path $Here "..\..")).Path }
$env:PYTHONPATH = $Base
Set-Location $Base
Write-Host "Launching Ned-aware RESTORE path..."
python -m rpos.installer advisories
Write-Host ""
$Confirm = Read-Host "Type RESTORE to confirm absolute wipe intent + install"
python -m rpos.installer restore --yes-advisories --confirm $Confirm
Write-Host ""
Write-Host "Ned will guide first setup (timezone, language, rpMail email)."
python -m rpos.installer oobe --smoke
