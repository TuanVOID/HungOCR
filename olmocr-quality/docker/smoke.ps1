param([Parameter(Mandatory=$true)][string]$InputPdf, [switch]$WaitIdle)
$ErrorActionPreference = 'Stop'
$settings = @{}
foreach ($line in Get-Content -LiteralPath (Join-Path $PSScriptRoot '.env') -Encoding utf8) {
  if ($line -match '^([A-Z_]+)=(.*)$') { $settings[$matches[1]] = $matches[2] }
}
$bind = $settings['OLMOCR_BIND_IP']
if (-not $bind -or $bind -eq '0.0.0.0') { $bind = '127.0.0.1' }
$port = $settings['OLMOCR_PORT']; if (-not $port) { $port = '8011' }
$base = "http://${bind}:$port"
$headers = @{ Authorization = "Bearer $($settings['OLMOCR_API_KEY'])"; 'X-File-Name' = [Uri]::EscapeDataString([IO.Path]::GetFileName($InputPdf)) }
$job = Invoke-RestMethod -Uri "$base/api/jobs" -Method Post -Headers $headers -ContentType 'application/pdf' -InFile $InputPdf -TimeoutSec 60
$deadline = (Get-Date).AddMinutes(20)
while ($job.status -eq 'running') {
  if ((Get-Date) -gt $deadline) { throw 'OCR exceeded the smoke-test deadline' }
  Start-Sleep -Seconds 5
  $job = Invoke-RestMethod -Uri "$base/api/jobs/$($job.id)" -Headers $headers -TimeoutSec 15
}
if ($job.status -ne 'done') { throw "OCR failed: $($job.error)" }
$raw = Invoke-WebRequest -UseBasicParsing -Uri "$base/api/jobs/$($job.id)/jsonl" -Headers $headers -TimeoutSec 15
$result = $raw.Content | ConvertFrom-Json
if ($result.metadata.'total-fallback-pages' -ne 0 -or [string]::IsNullOrWhiteSpace($result.text)) { throw 'Empty or fallback OCR result' }
Write-Host "OCR passed: $($result.metadata.'pdf-total-pages') pages, $($result.text.Length) characters."
if ($WaitIdle) {
  $deadline = (Get-Date).AddMinutes(7)
  do {
    Start-Sleep -Seconds 5
    $health = Invoke-RestMethod -Uri "$base/api/health" -TimeoutSec 15
    if ((Get-Date) -gt $deadline) { throw 'Idle unload was not observed; check for another active OCR request.' }
  } while ($health.model_state -ne 'unloaded')
  Write-Host 'Idle unload passed. Run this test again to verify automatic reload.'
}
