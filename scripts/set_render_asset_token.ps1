# Set RPT_ASSET_FETCH_TOKEN (and RPT_VPS_ASSET_BASE) on Render service
# restore-privacy-status to match the Iceland VPS paid-asset unit.
#
# Requires RENDER_API_KEY (https://dashboard.render.com/u/settings#api-keys).
# Token value: from env RPT_ASSET_FETCH_TOKEN, or read from VPS unit over SSH.
#
# Usage:
#   $env:RENDER_API_KEY = 'rnd_...'
#   $env:RPT_ASSET_FETCH_TOKEN = 'rpt-paid-...'   # optional if SSH works
#   .\scripts\set_render_asset_token.ps1

$ErrorActionPreference = 'Stop'

$apiKey = $env:RENDER_API_KEY
if (-not $apiKey) {
  throw 'RENDER_API_KEY not set. Create one at https://dashboard.render.com/u/settings#api-keys'
}

$token = $env:RPT_ASSET_FETCH_TOKEN
if (-not $token) {
  $sshKey = Join-Path $env:USERPROFILE '.ssh\id_ed25519_restore_privacy_vps'
  if (-not (Test-Path $sshKey)) {
    throw 'RPT_ASSET_FETCH_TOKEN not set and VPS SSH key missing'
  }
  $line = ssh -i $sshKey -o BatchMode=yes -o ConnectTimeout=15 raskul@82.221.101.241 `
    "systemctl cat rpt-paid-assets.service | sed -n 's/.*Environment=RPT_ASSET_FETCH_TOKEN=//p' | head -1"
  $token = ($line | Out-String).Trim()
}
if (-not $token -or $token.Length -lt 8) {
  throw 'Could not resolve RPT_ASSET_FETCH_TOKEN'
}

$vpsBase = if ($env:RPT_VPS_ASSET_BASE) {
  $env:RPT_VPS_ASSET_BASE
} else {
  'http://82.221.101.241:8081/paid-assets'
}

$headers = @{
  Authorization = "Bearer $apiKey"
  Accept        = 'application/json'
}

Write-Host 'Listing Render services...'
$services = Invoke-RestMethod -Uri 'https://api.render.com/v1/services?limit=50' -Headers $headers
$svc = @($services | ForEach-Object { $_.service } | Where-Object {
  $_.name -match 'restore-privacy-status'
}) | Select-Object -First 1

if (-not $svc) {
  Write-Host 'Services on account:'
  $services | ForEach-Object { Write-Host ' -' $_.service.name $_.service.id }
  throw 'No service matching restore-privacy-status'
}

Write-Host "Target: $($svc.name) ($($svc.id))"

# Prefer single-key upsert (does not wipe other env vars)
$putHeaders = $headers + @{ 'Content-Type' = 'application/json' }
$bodyToken = @{ value = $token } | ConvertTo-Json
$bodyBase = @{ value = $vpsBase } | ConvertTo-Json

$encKey = [uri]::EscapeDataString('RPT_ASSET_FETCH_TOKEN')
$encBase = [uri]::EscapeDataString('RPT_VPS_ASSET_BASE')

Write-Host 'PUT RPT_ASSET_FETCH_TOKEN (value redacted)...'
Invoke-RestMethod -Method Put `
  -Uri "https://api.render.com/v1/services/$($svc.id)/env-vars/$encKey" `
  -Headers $putHeaders -Body $bodyToken | Out-Null

Write-Host "PUT RPT_VPS_ASSET_BASE=$vpsBase ..."
Invoke-RestMethod -Method Put `
  -Uri "https://api.render.com/v1/services/$($svc.id)/env-vars/$encBase" `
  -Headers $putHeaders -Body $bodyBase | Out-Null

# Trigger deploy so free-tier picks up durable env
try {
  Invoke-RestMethod -Method Post `
    -Uri "https://api.render.com/v1/services/$($svc.id)/deploys" `
    -Headers ($headers + @{ 'Content-Type' = 'application/json' }) `
    -Body '{}' | Out-Null
  Write-Host 'Deploy triggered. Wait for live, then:'
  Write-Host '  curl https://restore-privacy-status.onrender.com/health/fulfilment'
} catch {
  Write-Host "Env set; trigger deploy manually if needed: $($_.Exception.Message)"
}

Write-Host 'Done (token not printed).'
