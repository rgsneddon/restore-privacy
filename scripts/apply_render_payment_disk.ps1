# Apply durable payment-store config on Render service restore-privacy-status.
#
# Matches render.yaml intent:
#   RPT_PAYMENT_DATA_DIR=/var/data/rpt-payment
#   persistent disk name=rpt-payment-data mountPath=/var/data sizeGB=1
#   plan must support disks (starter+; free cannot attach)
#
# Requires:
#   $env:RENDER_API_KEY = 'rnd_...'   # https://dashboard.render.com/u/settings#api-keys
#
# Usage:
#   $env:RENDER_API_KEY = 'rnd_...'
#   .\scripts\apply_render_payment_disk.ps1
#   .\scripts\apply_render_payment_disk.ps1 -WhatIf   # dry-run: list service + env only
#
# Never commit API keys. Does not print secret values.

param(
  [string]$ServiceName = 'restore-privacy-status',
  [string]$PaymentDataDir = '/var/data/rpt-payment',
  [string]$DiskName = 'rpt-payment-data',
  [string]$DiskMountPath = '/var/data',
  [int]$DiskSizeGB = 1,
  [switch]$WhatIf,
  [switch]$SkipDeploy
)

$ErrorActionPreference = 'Stop'

function Write-Log([string]$msg) {
  Write-Host $msg
}

$apiKey = $env:RENDER_API_KEY
if (-not $apiKey) {
  Write-Log 'FAIL: RENDER_API_KEY not set.'
  Write-Log 'Create a key at https://dashboard.render.com/u/settings#api-keys'
  Write-Log "Then:  `$env:RENDER_API_KEY = 'rnd_...'"
  Write-Log '       .\scripts\apply_render_payment_disk.ps1'
  Write-Log 'Or apply the Blueprint in Dashboard (Blueprints sync) with render.yaml disk + env.'
  exit 2
}

$headers = @{
  Authorization = "Bearer $apiKey"
  Accept        = 'application/json'
}

Write-Log "Listing Render services for '$ServiceName'..."
$services = Invoke-RestMethod -Uri 'https://api.render.com/v1/services?limit=50' -Headers $headers
$svc = @($services | ForEach-Object { $_.service } | Where-Object {
  $_.name -match [regex]::Escape($ServiceName)
}) | Select-Object -First 1

if (-not $svc) {
  Write-Log 'Services on account:'
  $services | ForEach-Object { Write-Log (" - {0} {1}" -f $_.service.name, $_.service.id) }
  throw "No service matching $ServiceName"
}

$sid = $svc.id
$planHint = ''
try {
  if ($svc.serviceDetails -and $svc.serviceDetails.plan) {
    $planHint = [string]$svc.serviceDetails.plan
  } elseif ($svc.plan) {
    $planHint = [string]$svc.plan
  }
} catch {
  $planHint = ''
}
Write-Log ("Target: {0} ({1}) plan={2}" -f $svc.name, $sid, $planHint)

Write-Log 'GET env-vars (names only)...'
$envList = Invoke-RestMethod -Uri "https://api.render.com/v1/services/$sid/env-vars" -Headers $headers
$names = @()
foreach ($item in @($envList)) {
  $ev = if ($item.envVar) { $item.envVar } else { $item }
  if ($ev.key) { $names += [string]$ev.key }
}
Write-Log ("env keys: {0}" -f ($names -join ', '))

$hasPaymentDir = $names -contains 'RPT_PAYMENT_DATA_DIR'
Write-Log ("RPT_PAYMENT_DATA_DIR present before apply: {0}" -f $hasPaymentDir)

if ($WhatIf) {
  Write-Log "WhatIf: would PUT RPT_PAYMENT_DATA_DIR=$PaymentDataDir"
  Write-Log "WhatIf: would ensure disk name=$DiskName mount=$DiskMountPath sizeGB=$DiskSizeGB (if API allows)"
  Write-Log 'WhatIf: would POST deploy (unless -SkipDeploy)'
  exit 0
}

$putHeaders = $headers.Clone()
$putHeaders['Content-Type'] = 'application/json'
$encKey = [uri]::EscapeDataString('RPT_PAYMENT_DATA_DIR')
$body = @{ value = $PaymentDataDir } | ConvertTo-Json
Write-Log "PUT RPT_PAYMENT_DATA_DIR=$PaymentDataDir ..."
Invoke-RestMethod -Method Put `
  -Uri "https://api.render.com/v1/services/$sid/env-vars/$encKey" `
  -Headers $putHeaders -Body $body | Out-Null
Write-Log 'RPT_PAYMENT_DATA_DIR set.'

$diskApplied = $false
$diskError = ''
try {
  # Correct Render API: POST /v1/disks with serviceId in body (not /services/{id}/disks).
  # Fails with 400 if a deploy is still pending — wait or retry after live.
  $diskBody = @{
    name      = $DiskName
    mountPath = $DiskMountPath
    sizeGB    = $DiskSizeGB
    serviceId = $sid
  } | ConvertTo-Json
  Write-Log "POST /v1/disks $DiskName @ $DiskMountPath (${DiskSizeGB}GB) serviceId=$sid ..."
  Invoke-RestMethod -Method Post `
    -Uri 'https://api.render.com/v1/disks' `
    -Headers $putHeaders -Body $diskBody | Out-Null
  $diskApplied = $true
  Write-Log 'Disk create/attach accepted by API (redeploy required for mount).'
} catch {
  $diskError = $_.Exception.Message
  # Idempotent: disk already attached is success for our purposes
  try {
    $existing = Invoke-RestMethod -Uri "https://api.render.com/v1/disks?serviceId=$sid" -Headers $headers
    $found = $false
    foreach ($item in @($existing)) {
      $disk = if ($item.disk) { $item.disk } else { $item }
      if ($disk.mountPath -eq $DiskMountPath -or $disk.name -eq $DiskName) {
        $found = $true
        $diskApplied = $true
        Write-Log ("Disk already present: id={0} name={1} mount={2}" -f $disk.id, $disk.name, $disk.mountPath)
        break
      }
    }
    if (-not $found) {
      Write-Log "Disk API note (env still set): $diskError"
      Write-Log 'If disk missing: Dashboard -> service -> Disks -> Add disk mountPath=/var/data'
      Write-Log 'Or Blueprints -> Apply render.yaml (plan starter + disk block). Free plan cannot attach disks.'
      Write-Log 'Note: cannot add disk while deploys are pending — wait for live then re-run.'
    }
  } catch {
    Write-Log "Disk API note (env still set): $diskError"
    Write-Log 'If disk missing: Dashboard -> service -> Disks -> Add disk mountPath=/var/data'
  }
}

if (-not $SkipDeploy) {
  try {
    Write-Log 'POST deploy...'
    Invoke-RestMethod -Method Post `
      -Uri "https://api.render.com/v1/services/$sid/deploys" `
      -Headers $putHeaders `
      -Body '{}' | Out-Null
    Write-Log 'Deploy triggered. Wait for live, then check /health and /admin durable path.'
  } catch {
    Write-Log "Deploy trigger failed (env may still be set): $($_.Exception.Message)"
  }
}

$envList2 = Invoke-RestMethod -Uri "https://api.render.com/v1/services/$sid/env-vars" -Headers $headers
$names2 = @()
foreach ($item in @($envList2)) {
  $ev = if ($item.envVar) { $item.envVar } else { $item }
  if ($ev.key) { $names2 += [string]$ev.key }
}
$okEnv = $names2 -contains 'RPT_PAYMENT_DATA_DIR'
Write-Log ("RPT_PAYMENT_DATA_DIR present after apply: {0}" -f $okEnv)
Write-Log ("disk_api_applied={0}" -f $diskApplied)
if ($diskError) { Write-Log ("disk_api_error={0}" -f $diskError) }

if (-not $okEnv) {
  throw 'RPT_PAYMENT_DATA_DIR missing after PUT - apply failed'
}

Write-Log 'Done.'
exit 0
