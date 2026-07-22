# Check whether fulfilment SMTP env vars are set on Render restore-privacy-status.
# Values are NEVER printed — only present/empty booleans.
#
# Requires RENDER_API_KEY (https://dashboard.render.com/u/settings#api-keys).
#
# Usage:
#   $env:RENDER_API_KEY = 'rnd_...'
#   .\scripts\check_render_fulfilment_smtp.ps1
#   .\scripts\check_render_fulfilment_smtp.ps1 -OutFile smtp_check.json

param(
  [string]$ServiceName = 'restore-privacy-status',
  [string]$OutFile = ''
)

$ErrorActionPreference = 'Stop'

$keys = @(
  'RPT_FULFILMENT_SMTP_HOST',
  'RPT_FULFILMENT_SMTP_PORT',
  'RPT_FULFILMENT_SMTP_USER',
  'RPT_FULFILMENT_SMTP_PASSWORD',
  'RPT_FULFILMENT_FROM_EMAIL',
  'RPT_FULFILMENT_SMTP_TLS'
)

$result = [ordered]@{
  service = $ServiceName
  RENDER_API_KEY_present = [bool]$env:RENDER_API_KEY
  checked_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  keys = [ordered]@{}
  email_flow_enabled = $false
  status = 'unknown'
  detail = ''
}

if (-not $env:RENDER_API_KEY) {
  $result.status = 'skipped_no_RENDER_API_KEY'
  $result.detail = 'Set RENDER_API_KEY then re-run, or inspect Dashboard Environment for the six RPT_FULFILMENT_SMTP_* keys.'
  foreach ($k in $keys) { $result.keys[$k] = $null }
  $json = $result | ConvertTo-Json -Depth 6
  if ($OutFile) { $json | Set-Content -Path $OutFile -Encoding utf8 }
  Write-Output $json
  exit 2
}

$headers = @{
  Authorization = "Bearer $($env:RENDER_API_KEY)"
  Accept        = 'application/json'
}

$services = Invoke-RestMethod -Uri 'https://api.render.com/v1/services?limit=50' -Headers $headers
$svc = @($services | ForEach-Object { $_.service } | Where-Object {
  $_.name -match [regex]::Escape($ServiceName)
}) | Select-Object -First 1

if (-not $svc) {
  $result.status = 'service_not_found'
  $result.detail = "No service matching $ServiceName"
  $json = $result | ConvertTo-Json -Depth 6
  if ($OutFile) { $json | Set-Content -Path $OutFile -Encoding utf8 }
  Write-Output $json
  exit 3
}

$result.service_id = $svc.id
$result.service_name = $svc.name

# List all env vars (Render returns key + value; we only keep presence)
$envList = Invoke-RestMethod `
  -Uri "https://api.render.com/v1/services/$($svc.id)/env-vars" `
  -Headers $headers

$byKey = @{}
foreach ($item in @($envList)) {
  # API shape: array of { envVar: { key, value } } or flat { key, value }
  $ev = if ($item.envVar) { $item.envVar } else { $item }
  if ($null -eq $ev) { continue }
  $k = [string]$ev.key
  $v = [string]$ev.value
  $byKey[$k] = [bool]($v -and $v.Trim().Length -gt 0)
}

foreach ($k in $keys) {
  if ($byKey.ContainsKey($k)) {
    $result.keys[$k] = [bool]$byKey[$k]
  } else {
    $result.keys[$k] = $false
  }
}

$hostOk = [bool]$result.keys['RPT_FULFILMENT_SMTP_HOST']
$userOk = [bool]$result.keys['RPT_FULFILMENT_SMTP_USER']
$passOk = [bool]$result.keys['RPT_FULFILMENT_SMTP_PASSWORD']

# Port/TLS/from may use app defaults when unset on live
if (-not $byKey.ContainsKey('RPT_FULFILMENT_SMTP_PORT')) {
  $result.keys['RPT_FULFILMENT_SMTP_PORT'] = $false
  $result.port_uses_code_default = $true
}
if (-not $byKey.ContainsKey('RPT_FULFILMENT_SMTP_TLS')) {
  $result.keys['RPT_FULFILMENT_SMTP_TLS'] = $false
  $result.tls_uses_code_default = $true
}
if (-not $byKey.ContainsKey('RPT_FULFILMENT_FROM_EMAIL')) {
  $result.keys['RPT_FULFILMENT_FROM_EMAIL'] = $false
  $result.from_uses_code_default = $true
}

if (-not $hostOk) {
  $result.status = 'disabled'
  $result.email_flow_enabled = $false
  $result.detail = 'RPT_FULFILMENT_SMTP_HOST not set on service - email send skips'
} elseif ($hostOk -and (-not $userOk -or -not $passOk)) {
  $result.status = 'host_only_incomplete_auth'
  $result.email_flow_enabled = $false
  $result.detail = 'Host present but SMTP user and/or password missing'
} elseif ($hostOk -and $userOk -and $passOk) {
  $result.status = 'ready_to_attempt_send'
  $result.email_flow_enabled = $true
  $result.detail = 'Host + user + password present - fulfilment email can attempt SMTP'
} else {
  $result.status = 'partial'
  $result.email_flow_enabled = $false
  $result.detail = 'Incomplete SMTP env'
}

$json = $result | ConvertTo-Json -Depth 6
if ($OutFile) { $json | Set-Content -Path $OutFile -Encoding utf8 }
Write-Output $json
if ($result.email_flow_enabled) { exit 0 } else { exit 1 }
