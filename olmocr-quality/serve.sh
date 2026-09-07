#!/usr/bin/env bash
set -euo pipefail
runtime=/home/imdevil/olmocr-quality
export PATH="$runtime/.venv/bin:$PATH"
# WSL2 does not expose CUDA UVA, which vLLM's V2 runner requires.
export VLLM_USE_V2_MODEL_RUNNER=0
exec vllm serve allenai/olmOCR-2-7B-1025-FP8 \
  --host 127.0.0.1 --port 8000 \
  --served-model-name olmocr \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.86 \
  --max-num-seqs 2 \
  --tensor-parallel-size 1 \
  --mm-processor-kwargs '{"max_pixels":589824}' \
  --limit-mm-per-prompt '{"image":1,"video":0}'
