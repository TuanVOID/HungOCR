$ErrorActionPreference = 'Stop'
& wsl.exe -d Ubuntu -u root -- systemctl is-active --quiet olmocr-vllm.service
if ($LASTEXITCODE -eq 0) {
    Write-Host 'olmOCR server is already running. Health: http://localhost:8000/health'
    exit 0
}

$arguments = @(
    '-d', 'Ubuntu', '-u', 'root', '--',
    'bash', '/mnt/f/.VibeCoding/19.HungOCR/olmocr-quality/keep-alive.sh'
)
$process = Start-Process -FilePath 'wsl.exe' -ArgumentList $arguments -WindowStyle Hidden -PassThru
if ($process.HasExited) { throw 'Failed to start the WSL olmOCR launcher.' }
Write-Host 'Server is starting. Health: http://localhost:8000/health'
Write-Host 'Logs: wsl -d Ubuntu -- tail -f /home/imdevil/olmocr-quality/vllm.log'
