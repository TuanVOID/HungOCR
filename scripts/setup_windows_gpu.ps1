# PowerShell script to set up Windows GPU environment with CUDA 12.8 and Python 3.11
$ErrorActionPreference = "Stop"

Write-Host "=== GIAI DOAN 1: Kiem tra phan cung va phan mem ===" -ForegroundColor Cyan
# 1. Kiem tra Python 3.11
$python311 = & py -0p | Out-String
if ($python311 -match "3.11-64") {
    Write-Host "Tim thay Python 3.11 64-bit." -ForegroundColor Green
} else {
    Write-Warning "Khong tim thay Python 3.11 64-bit trong danh sach cua 'py launcher'."
    Write-Host "Thu kiem tra truc tiep 'python' executable..." -ForegroundColor Yellow
}

# 2. Tao thu muc virtualenv moi .venv-gpu
Write-Host "=== GIAI DOAN 2: Tao virtualenv .venv-gpu ===" -ForegroundColor Cyan
if (Test-Path ".venv-gpu") {
    Write-Host "Thu muc .venv-gpu da ton tai. Xoa de tao moi..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force ".venv-gpu"
}

& py -3.11 -m venv .venv-gpu
if (-not $?) {
    Write-Error "Khong the tao virtualenv bang py -3.11. Vui long kiem tra lai phien ban Python."
}
Write-Host "Tao virtualenv .venv-gpu thanh cong." -ForegroundColor Green

# Cac duong dan den executable cua .venv-gpu
$venvPython = ".\.venv-gpu\Scripts\python.exe"
$venvPip = ".\.venv-gpu\Scripts\pip.exe"

# 3. Nang cap pip, setuptools, wheel
Write-Host "=== GIAI DOAN 3: Nang cap pip, setuptools, wheel ===" -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip setuptools wheel
if (-not $?) { Write-Error "Nang cap pip, setuptools, wheel that bai." }

# 4. Cai dat requirements-base
Write-Host "=== GIAI DOAN 4: Cai dat requirements chung (requirements-base.txt) ===" -ForegroundColor Cyan
& $venvPython -m pip install -r requirements-base.txt
if (-not $?) { Write-Error "Cai dat requirements-base.txt that bai." }

# 5. Cai dat PyTorch CUDA 12.8 tu official index
Write-Host "=== GIAI DOAN 5: Cai dat PyTorch cu128 ===" -ForegroundColor Cyan
& $venvPython -m pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu128
if (-not $?) { Write-Error "Cai dat torch va torchvision cu128 that bai." }

# 6. Cai dat onnxruntime-gpu
Write-Host "=== GIAI DOAN 6: Cai dat onnxruntime-gpu==1.22.0 ===" -ForegroundColor Cyan
& $venvPython -m pip install onnxruntime-gpu==1.22.0
if (-not $?) { Write-Error "Cai dat onnxruntime-gpu that bai." }

# 7. Cai dat VietOCR
Write-Host "=== GIAI DOAN 7: Cai dat vietocr==0.3.13 ===" -ForegroundColor Cyan
& $venvPython -m pip install vietocr==0.3.13
if (-not $?) { Write-Error "Cai dat vietocr that bai." }

# 8. Kiem tra pip check
Write-Host "=== GIAI DOAN 8: Kiem tra xung dot dependency (pip check) ===" -ForegroundColor Cyan
& $venvPython -m pip check
if (-not $?) { Write-Error "Phat hien xung dot dependency qua pip check." }
Write-Host "pip check OK. Khong co xung dot." -ForegroundColor Green

# 9. Smoke test ban dau (import va CUDA check)
Write-Host "=== GIAI DOAN 9: Smoke test moi truong GPU ===" -ForegroundColor Cyan
$smokeTestCmd = @"
import sys
import torch
import torchvision
import onnxruntime as ort

print('Python Version:', sys.version)
print('Torch Version:', torch.__version__)
print('Torch CUDA Available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('Torch CUDA Version:', torch.version.cuda)
    print('Torch GPU Name:', torch.cuda.get_device_name(0))
else:
    print('ERROR: Torch CUDA is not available!')
    sys.exit(1)

print('ONNX Runtime Version:', ort.__version__)
print('ONNX Runtime Available Providers:', ort.get_available_providers())
if 'CUDAExecutionProvider' in ort.get_available_providers():
    print('ONNX Runtime CUDA Provider is available.')
else:
    print('ERROR: ONNX Runtime CUDA Execution Provider is NOT available!')
    sys.exit(1)

sys.exit(0)
"@

& $venvPython -c $smokeTestCmd
if ($LASTEXITCODE -ne 0) {
    Write-Error "Smoke test moi truong GPU that bai! Mot hoac nhieu thanh phan khong chay tren CUDA."
}

# 10. Ghi nhan phien ban cuoi cung
Write-Host "=== GIAI DOAN 10: Hoan thanh va xuat pip freeze ===" -ForegroundColor Cyan
& $venvPython -m pip freeze > requirements-gpu-installed.lock
Write-Host "Thiet lap moi truong GPU hoan tat! Thong tin dependencies duoc ghi nhan vao requirements-gpu-installed.lock" -ForegroundColor Green
