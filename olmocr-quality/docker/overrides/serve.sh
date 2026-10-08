#!/usr/bin/env bash
set -euo pipefail

FREE_QWEN_CONTAINER="attt-portable-llm-1"
DOCKER_SOCK="/var/run/docker.sock"
qwen_started=0

start_qwen() {
  if [ "$qwen_started" = "0" ] && [ -S "$DOCKER_SOCK" ]; then
    qwen_started=1
    if [ -n "${VLLM_PID:-}" ] && kill -0 "$VLLM_PID" 2>/dev/null; then
      kill "$VLLM_PID" 2>/dev/null || true
      wait "$VLLM_PID" 2>/dev/null || true
      sleep 2
    fi
    echo "[$(date -Iseconds)] [GPU-Coord] Starting $FREE_QWEN_CONTAINER..." >> /data/vllm.log
    curl -s --unix-socket "$DOCKER_SOCK" -X POST "http://localhost/containers/$FREE_QWEN_CONTAINER/start" >> /data/vllm.log 2>&1 || true
  fi
}

stop_qwen() {
  if [ -S "$DOCKER_SOCK" ]; then
    echo "[$(date -Iseconds)] [GPU-Coord] Stopping $FREE_QWEN_CONTAINER to free GPU VRAM..." >> /data/vllm.log
    curl -s --unix-socket "$DOCKER_SOCK" -X POST "http://localhost/containers/$FREE_QWEN_CONTAINER/stop?t=10" >> /data/vllm.log 2>&1 || true
    sleep 3
  fi
}

trap start_qwen EXIT TERM INT

stop_qwen

runtime=/home/imdevil/olmocr-quality
if [ "${OLMOCR_CONTAINER:-0}" != "1" ]; then export PATH="$runtime/.venv/bin:$PATH"; fi
# WSL2 does not expose CUDA UVA, which vLLM's V2 runner requires.
export VLLM_USE_V2_MODEL_RUNNER=0

# This host shares its 16 GiB GPU with meeting, embedding and reranking services.
# A single eager-mode sequence avoids CUDA graph reservation. An explicit
# 384 MiB KV cache and 6k context keep the 7B FP8 model inside this 16 GiB GPU
# while the app's other CUDA services remain online; the API serializes jobs.
vllm serve "${OLMOCR_MODEL_PATH:-allenai/olmOCR-2-7B-1025-FP8}" \
  --host 127.0.0.1 --port 8000 \
  --served-model-name olmocr \
  --max-model-len 6144 \
  --gpu-memory-utilization "${OLMOCR_GPU_MEMORY_UTILIZATION:-0.85}" \
  --kv-cache-memory-bytes 384M \
  --max-num-seqs 1 \
  --enforce-eager \
  --tensor-parallel-size 1 \
  --mm-processor-kwargs '{"max_pixels":589824}' \
  --limit-mm-per-prompt '{"image":1,"video":0}' &

VLLM_PID=$!
wait $VLLM_PID
