param([switch]$SkipImageLoad)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath 'models/olmocr/config.json')) { throw 'Missing models/olmocr. Copy the complete portable directory.' }
& docker version --format '{{.Server.Version}}'
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop (Linux containers) first.' }
if (-not $SkipImageLoad) {
  & (Join-Path $PSScriptRoot 'verify.ps1')
  if (-not (Test-Path -LiteralPath 'olmocr-image.tar')) { throw 'Missing olmocr-image.tar' }
  & docker load -i olmocr-image.tar
  if ($LASTEXITCODE -ne 0) { throw 'Docker image import failed' }
}
if (-not (Test-Path -LiteralPath '.env')) {
  $bytes = New-Object byte[] 32
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  $key = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
  $settings = "OLMOCR_BIND_IP=127.0.0.1`nOLMOCR_PORT=8011`nOLMOCR_API_KEY=$key`nOLMOCR_GPU_MEMORY_UTILIZATION=0.86`n"
  [IO.File]::WriteAllText((Join-Path $PSScriptRoot '.env'), $settings, (New-Object Text.UTF8Encoding($false)))
}
& docker compose up -d --pull never
if ($LASTEXITCODE -ne 0) { throw 'Container startup failed. Check GPU support and port availability.' }
Write-Host 'Installed. Run manage.ps1 status. Copy OLMOCR_API_KEY from .env into the Chatbot private environment file; never put it in frontend config.'
