# PowerShell script to set up Windows CPU environment for rollback/dev
$ErrorActionPreference = "Stop"

Write-Host "=== GIAI DOAN 1: Tao virtualenv .venv-cpu ===" -ForegroundColor Cyan
if (Test-Path ".venv-cpu") {
    Write-Host "Thu muc .venv-cpu da ton tai. Xoa de tao moi..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force ".venv-cpu"
}

# Su dung Python 3.10 nhu moi truong goc de dam bao tuong thich 100%
$python310 = & py -0p | Out-String
if ($python310 -match "3.10-64") {
    & py -3.10 -m venv .venv-cpu
} else {
    Write-Warning "Khong tim thay Python 3.10 64-bit. Su dung phien ban Python mac dinh..."
    & python -m venv .venv-cpu
}

if (-not $?) {
    Write-Error "Khong the tao virtualenv .venv-cpu."
}
Write-Host "Tao virtualenv .venv-cpu thanh cong." -ForegroundColor Green

$venvPython = ".\.venv-cpu\Scripts\python.exe"

# 2. Nang cap pip, setuptools, wheel
Write-Host "=== GIAI DOAN 2: Nang cap pip, setuptools, wheel ===" -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip setuptools wheel
if (-not $?) { Write-Error "Nang cap pip, setuptools, wheel that bai." }

# 3. Cai dat requirements-base.txt
Write-Host "=== GIAI DOAN 3: Cai dat requirements-base.txt ===" -ForegroundColor Cyan
& $venvPython -m pip install -r requirements-base.txt
if (-not $?) { Write-Error "Cai dat requirements-base.txt that bai." }

# 4. Cai dat requirements-cpu.txt
Write-Host "=== GIAI DOAN 4: Cai dat requirements-cpu.txt ===" -ForegroundColor Cyan
& $venvPython -m pip install -r requirements-cpu.txt
if (-not $?) { Write-Error "Cai dat requirements-cpu.txt that bai." }

# 5. Kiem tra xung dot dependency (pip check)
Write-Host "=== GIAI DOAN 5: Kiem tra xung dot dependency (pip check) ===" -ForegroundColor Cyan
& $venvPython -m pip check
if (-not $?) { Write-Error "Phat hien xung dot dependency qua pip check." }
Write-Host "pip check OK. Khong co xung dot." -ForegroundColor Green

# 6. Smoke test
Write-Host "=== GIAI DOAN 6: Smoke test moi truong CPU ===" -ForegroundColor Cyan
$smokeTestCmd = @"
import sys
import torch
import paddle
print('Python Version:', sys.version)
print('Torch Version:', torch.__version__)
print('Paddle Version:', paddle.__version__)
print('Paddle CUDA compiling:', paddle.is_compiled_with_cuda())
"@

& $venvPython -c $smokeTestCmd
if ($LASTEXITCODE -ne 0) {
    Write-Error "Smoke test moi truong CPU that bai!"
}

Write-Host "Thiet lap moi truong CPU hoan tat thanh cong!" -ForegroundColor Green
