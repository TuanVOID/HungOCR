param([ValidateSet('start','stop','status','logs')][string]$Action = 'status')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
switch ($Action) {
  'start' { & docker compose up -d --pull never }
  'stop' { & docker compose stop }
  'status' {
    & docker compose ps
    & docker compose exec -T olmocr node -e "fetch('http://127.0.0.1:8010/api/health').then(r=>r.json()).then(console.log)"
  }
  'logs' { & docker compose logs --tail 100 }
}
if ($LASTEXITCODE -ne 0) { throw 'Docker command failed' }
