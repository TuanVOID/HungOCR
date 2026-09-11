$ErrorActionPreference = 'Stop'
$bundleRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$manifest = Get-Content -LiteralPath (Join-Path $bundleRoot 'manifest.json') -Raw -Encoding utf8 | ConvertFrom-Json
foreach ($file in $manifest.files) {
  $target = [IO.Path]::GetFullPath((Join-Path $bundleRoot $file.path))
  if (-not $target.StartsWith($bundleRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid manifest path' }
  if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw "Missing file: $($file.path)" }
  $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($hash -ne $file.sha256) { throw "Checksum mismatch: $($file.path)" }
}
Write-Host "Verified $($manifest.files.Count) files. Image and model match the prepared package."
