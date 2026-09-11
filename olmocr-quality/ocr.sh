#!/usr/bin/env bash
set -euo pipefail
runtime=/home/imdevil/olmocr-quality
if [ "${OLMOCR_CONTAINER:-0}" != "1" ]; then export PATH="$runtime/.venv/bin:$PATH"; fi
if [ "$#" -lt 2 ]; then
  echo 'Usage: bash ocr.sh WORKSPACE PDF_OR_GLOB [PDF_OR_GLOB ...]' >&2
  exit 2
fi
workspace=$1
shift
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec python3 "$script_dir/legal_pipeline.py" "$workspace" \
  --server http://127.0.0.1:8000/v1 \
  --model olmocr \
  --markdown \
  --target_longest_image_dim 1288 \
  --workers 1 \
  --max_concurrent_requests 2 \
  --pdfs "$@"
