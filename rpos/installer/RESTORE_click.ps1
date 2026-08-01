$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Base = if (Test-Path (Join-Path $Here "rpos\installer")) { $Here }
  elseif (Test-Path (Join-Path $Here "..\rpos\installer")) { (Resolve-Path (Join-Path $Here "..")).Path }
  else { (Resolve-Path (Join-Path $Here "..\..")).Path }
$env:PYTHONPATH = $Base
Set-Location $Base
$Prefix = if ($env:RPOS_PREFIX) { $env:RPOS_PREFIX } else { Join-Path $env:USERPROFILE ".rpos\install" }
Write-Host "Launching Ned-aware RESTORE path (prefix=$Prefix)..."
python -m rpos.installer advisories
Write-Host ""
$Confirm = Read-Host "Type RESTORE to confirm absolute wipe intent"
python -m rpos.installer restore --yes-advisories --confirm $Confirm --prefix $Prefix
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ""
Write-Host "Ned: personal setup — timezone, language, rpMail email."
python -m rpos.installer oobe --prefix $Prefix
Write-Host ""
Write-Host "Ned: locked guide — Pens, then Tables, then Slides."
python -m rpos.installer apps-tour --prefix $Prefix
