$ErrorActionPreference = 'Stop'
$processes = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'node.exe' -and $_.CommandLine -like ('*' + (Join-Path $PSScriptRoot 'ui\server.mjs') + '*')
}
if ($processes) {
    $state = Invoke-RestMethod -TimeoutSec 5 http://127.0.0.1:8010/api/health
    if ($state.active) { throw 'OCR is running. Wait until it finishes before stopping the UI.' }
    $processes | ForEach-Object { Stop-Process -Id $_.ProcessId }
}
Write-Host 'olmOCR UI stopped. The model server is managed separately by stop.ps1.'
