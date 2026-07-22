# Set RPT_ADMIN_PASSWORD on Render service restore-privacy-status and deploy.
#
# Requires RENDER_API_KEY (https://dashboard.render.com/u/settings#api-keys).
# Password from:
#   $env:RPT_ADMIN_PASSWORD
#   or file ~/.restore_privacy/admin_password_pending.txt
#   or -Password argument (avoid shell history when possible)
#
# Usage:
#   $env:RENDER_API_KEY = 'rnd_...'
#   $env:RPT_ADMIN_PASSWORD = '...'   # or leave pending file from rotation
#   .\scripts\set_render_admin_password.ps1
#
# Never commit the password. This script does not print the password.

param(
  [string]$Password = '',
  [string]$ServiceName = 'restore-privacy-status'
)

$ErrorActionPreference = 'Stop'

$apiKey = $env:RENDER_API_KEY
if (-not $apiKey) {
  throw 'RENDER_API_KEY not set. Create one at https://dashboard.render.com/u/settings#api-keys'
}

$pw = $Password
if (-not $pw) { $pw = $env:RPT_ADMIN_PASSWORD }
if (-not $pw) {
  $pending = Join-Path $env:USERPROFILE '.restore_privacy\admin_password_pending.txt'
  if (Test-Path $pending) {
    $pw = (Get-Content -Path $pending -Raw -Encoding utf8).Trim()
  }
}
if (-not $pw -or $pw.Length -lt 24) {
  throw 'RPT_ADMIN_PASSWORD not set (or pending file missing / too short). Generate with secrets.token_urlsafe(32).'
}

$headers = @{
  Authorization = "Bearer $apiKey"
  Accept        = 'application/json'
}

Write-Host "Listing Render services for '$ServiceName'..."
$services = Invoke-RestMethod -Uri 'https://api.render.com/v1/services?limit=50' -Headers $headers
$svc = @($services | ForEach-Object { $_.service } | Where-Object {
  $_.name -match [regex]::Escape($ServiceName)
}) | Select-Object -First 1

if (-not $svc) {
  Write-Host 'Services on account:'
  $services | ForEach-Object { Write-Host ' -' $_.service.name $_.service.id }
  throw "No service matching $ServiceName"
}

Write-Host "Target: $($svc.name) ($($svc.id))"
$putHeaders = $headers + @{ 'Content-Type' = 'application/json' }
$encKey = [uri]::EscapeDataString('RPT_ADMIN_PASSWORD')
$body = @{ value = $pw } | ConvertTo-Json

Write-Host 'PUT RPT_ADMIN_PASSWORD (value redacted)...'
Invoke-RestMethod -Method Put `
  -Uri "https://api.render.com/v1/services/$($svc.id)/env-vars/$encKey" `
  -Headers $putHeaders -Body $body | Out-Null

# Also set a fresh session secret so old cookies invalidate after rotate
$session = -join ((1..48) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) })
$encSess = [uri]::EscapeDataString('RPT_ADMIN_SESSION_SECRET')
$bodySess = @{ value = $session } | ConvertTo-Json
Write-Host 'PUT RPT_ADMIN_SESSION_SECRET (value redacted)...'
Invoke-RestMethod -Method Put `
  -Uri "https://api.render.com/v1/services/$($svc.id)/env-vars/$encSess" `
  -Headers $putHeaders -Body $bodySess | Out-Null

try {
  Invoke-RestMethod -Method Post `
    -Uri "https://api.render.com/v1/services/$($svc.id)/deploys" `
    -Headers ($headers + @{ 'Content-Type' = 'application/json' }) `
    -Body '{}' | Out-Null
  Write-Host 'Deploy triggered. Wait for live, then sign in at https://restoreprivacy.online/admin'
} catch {
  Write-Host "Env set; trigger deploy manually if needed: $($_.Exception.Message)"
}

Write-Host 'Done (password not printed).'
