$ErrorActionPreference = 'Stop'
$existing = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue
if (-not $existing) {
    Start-Process -FilePath 'node.exe' -ArgumentList ('"' + (Join-Path $PSScriptRoot 'ui\server.mjs') + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'ui.log') -RedirectStandardError (Join-Path $PSScriptRoot 'ui-error.log')
}
Write-Host 'olmOCR UI: http://localhost:8010'
