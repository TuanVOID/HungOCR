param(
    [string]$InputPdf = 'F:\.VibeCoding\19.HungOCR\docling\docs\test_OCR.pdf',
    [string]$Workspace = (Join-Path $PSScriptRoot 'workspace')
)
$ErrorActionPreference = 'Stop'
function ConvertTo-WslPath([string]$WindowsPath) {
    $resolved = [System.IO.Path]::GetFullPath($WindowsPath).Replace('\', '/')
    return [regex]::Replace(
        $resolved,
        '^([A-Za-z]):',
        { param($match) '/mnt/' + $match.Groups[1].Value.ToLower() }
    )
}
$inputPath = ConvertTo-WslPath $InputPdf
$workspacePath = ConvertTo-WslPath $Workspace
& wsl.exe -d Ubuntu -- bash /mnt/f/.VibeCoding/19.HungOCR/olmocr-quality/ocr.sh $workspacePath $inputPath
if ($LASTEXITCODE -ne 0) { throw 'olmOCR processing failed. See output above.' }
Write-Host "Markdown and JSONL outputs: $Workspace"
