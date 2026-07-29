param(
  [int]$Port = 5000,
  [ValidateSet("owned", "exclusive_lease")]
  [string]$Ownership = "exclusive_lease"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv_vl15\Scripts\python.exe"
$backend = Join-Path $root "app_backend.py"

foreach ($path in @($python, $backend)) {
  if (-not (Test-Path -LiteralPath $path)) {
    throw "Missing HungOCR TVPL service dependency: $path"
  }
}

$env:PORT = "$Port"
$env:OCR_DEVICE = "gpu"
$env:OCR_GPU_REQUIRED = "1"
$env:OCR_REQUIRE_EXPLICIT_LIFECYCLE = "1"
$env:OCR_LIFECYCLE_OWNERSHIP = $Ownership
$env:OCR_FORCE_PDF_IMAGE_OCR = "1"
$env:PYTHONIOENCODING = "utf-8"

& $python $backend
exit $LASTEXITCODE
