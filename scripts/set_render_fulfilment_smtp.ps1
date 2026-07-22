# Set fulfilment SMTP env vars on Render service restore-privacy-status and deploy.
#
# Requires RENDER_API_KEY (https://dashboard.render.com/u/settings#api-keys).
# SMTP secrets must be provided via env (never committed):
#   RPT_FULFILMENT_SMTP_HOST
#   RPT_FULFILMENT_SMTP_USER
#   RPT_FULFILMENT_SMTP_PASSWORD
# Optional:
#   RPT_FULFILMENT_SMTP_PORT (default 587)
#   RPT_FULFILMENT_FROM_EMAIL (default noreply@restoreprivacy.online)
#   RPT_FULFILMENT_SMTP_TLS (default 1)
#   RENDER_SERVICE_NAME (default restore-privacy-status)
#
# Usage:
#   $env:RENDER_API_KEY = 'rnd_...'
#   $env:RPT_FULFILMENT_SMTP_HOST = 'smtp.example.com'
#   $env:RPT_FULFILMENT_SMTP_USER = 'user'
#   $env:RPT_FULFILMENT_SMTP_PASSWORD = 'secret'
#   .\scripts\set_render_fulfilment_smtp.ps1

$ErrorActionPreference = 'Stop'

$apiKey = $env:RENDER_API_KEY
if (-not $apiKey) {
  throw 'RENDER_API_KEY not set. Create one at https://dashboard.render.com/u/settings#api-keys'
}

$hostName = $env:RPT_FULFILMENT_SMTP_HOST
if (-not $hostName) {
  throw 'RPT_FULFILMENT_SMTP_HOST not set (SMTP server hostname)'
}

$port = if ($env:RPT_FULFILMENT_SMTP_PORT) { $env:RPT_FULFILMENT_SMTP_PORT } else { '587' }
$user = $env:RPT_FULFILMENT_SMTP_USER
$pass = $env:RPT_FULFILMENT_SMTP_PASSWORD
$from = if ($env:RPT_FULFILMENT_FROM_EMAIL) {
  $env:RPT_FULFILMENT_FROM_EMAIL
} else {
  'noreply@restoreprivacy.online'
}
$tls = if ($env:RPT_FULFILMENT_SMTP_TLS) { $env:RPT_FULFILMENT_SMTP_TLS } else { '1' }
$svcName = if ($env:RENDER_SERVICE_NAME) { $env:RENDER_SERVICE_NAME } else { 'restore-privacy-status' }

$headers = @{
  Authorization = "Bearer $apiKey"
  Accept        = 'application/json'
}

Write-Host "Listing Render services for '$svcName'..."
$services = Invoke-RestMethod -Uri 'https://api.render.com/v1/services?limit=50' -Headers $headers
$svc = @($services | ForEach-Object { $_.service } | Where-Object {
  $_.name -match [regex]::Escape($svcName)
}) | Select-Object -First 1

if (-not $svc) {
  Write-Host 'Services on account:'
  $services | ForEach-Object { Write-Host ' -' $_.service.name $_.service.id }
  throw "No service matching $svcName"
}

Write-Host "Target: $($svc.name) ($($svc.id))"

$putHeaders = $headers + @{ 'Content-Type' = 'application/json' }

function Set-RenderEnv([string]$Key, [string]$Value, [switch]$Redact) {
  $enc = [uri]::EscapeDataString($Key)
  $body = @{ value = $Value } | ConvertTo-Json
  if ($Redact) {
    Write-Host "PUT $Key (value redacted)..."
  } else {
    Write-Host "PUT $Key=$Value ..."
  }
  Invoke-RestMethod -Method Put `
    -Uri "https://api.render.com/v1/services/$($svc.id)/env-vars/$enc" `
    -Headers $putHeaders -Body $body | Out-Null
}

Set-RenderEnv 'RPT_FULFILMENT_SMTP_HOST' $hostName
Set-RenderEnv 'RPT_FULFILMENT_SMTP_PORT' $port
if ($user) { Set-RenderEnv 'RPT_FULFILMENT_SMTP_USER' $user -Redact }
if ($pass) { Set-RenderEnv 'RPT_FULFILMENT_SMTP_PASSWORD' $pass -Redact }
Set-RenderEnv 'RPT_FULFILMENT_FROM_EMAIL' $from
Set-RenderEnv 'RPT_FULFILMENT_SMTP_TLS' $tls

try {
  Invoke-RestMethod -Method Post `
    -Uri "https://api.render.com/v1/services/$($svc.id)/deploys" `
    -Headers ($headers + @{ 'Content-Type' = 'application/json' }) `
    -Body '{}' | Out-Null
  Write-Host 'Deploy triggered. Wait for live, then:'
  Write-Host '  curl https://restoreprivacy.online/health'
  Write-Host '  curl https://restoreprivacy.online/health/fulfilment'
} catch {
  Write-Host "Env set; trigger deploy manually if needed: $($_.Exception.Message)"
}

Write-Host 'Done (SMTP password not printed).'
