$ErrorActionPreference = 'Stop'
& wsl.exe -d Ubuntu -u root -- systemctl stop olmocr-vllm.service
if ($LASTEXITCODE -ne 0) { throw 'Could not stop olmOCR server.' }
