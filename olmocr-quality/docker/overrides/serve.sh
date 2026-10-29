#!/usr/bin/env bash
set -euo pipefail

FREE_QWEN_CONTAINER="attt-portable-llm-1"
DOCKER_SOCK="/var/run/docker.sock"
QWEN_PROPS_URL="${QWEN_PROPS_URL:-http://host.docker.internal:28473/props}"
# VRAM the Qwen container holds once its model is loaded (14.8 GB measured on the RTX 5090).
QWEN_VRAM_MIB="${QWEN_VRAM_MIB:-15360}"
qwen_stopped=0

coord_log() {
  echo "[$(date -Iseconds)] [GPU-Coord] $*" >> /data/vllm.log
}

start_qwen() {
  if [ "$qwen_stopped" = "1" ] && [ -S "$DOCKER_SOCK" ]; then
    qwen_stopped=0
    if [ -n "${VLLM_PID:-}" ] && kill -0 "$VLLM_PID" 2>/dev/null; then
      kill "$VLLM_PID" 2>/dev/null || true
      wait "$VLLM_PID" 2>/dev/null || true
      sleep 2
    fi
    coord_log "Starting $FREE_QWEN_CONTAINER..."
    curl -s --unix-socket "$DOCKER_SOCK" -X POST "http://localhost/containers/$FREE_QWEN_CONTAINER/start" >> /data/vllm.log 2>&1 || true
  fi
}

stop_qwen() {
  if [ -S "$DOCKER_SOCK" ]; then
    qwen_stopped=1
    coord_log "Stopping $FREE_QWEN_CONTAINER to free GPU VRAM..."
    curl -s --unix-socket "$DOCKER_SOCK" -X POST "http://localhost/containers/$FREE_QWEN_CONTAINER/stop?t=10" >> /data/vllm.log 2>&1 || true
    sleep 3
  fi
}

# Qwen keeps running unless olmOCR would not fit next to it. A sleeping or still
# loading Qwen takes its VRAM back on the next request, so that share stays reserved.
qwen_must_stop() {
  local gpu free total need container props
  gpu=$(nvidia-smi --query-gpu=memory.free,memory.total --format=csv,noheader,nounits | head -n 1) || return 0
  IFS=', ' read -r free total <<< "$gpu"
  need=$(awk -v t="$total" -v u="${OLMOCR_GPU_MEMORY_UTILIZATION:-0.85}" 'BEGIN { printf "%d", t * u }')
  container=$(curl -s --unix-socket "$DOCKER_SOCK" "http://localhost/containers/$FREE_QWEN_CONTAINER/json" || true)
  props=$(curl -s -m 3 "$QWEN_PROPS_URL" || true)
  if [[ "$container" == *'"Running":true'* && "$props" != *'"is_sleeping":false'* ]]; then
    need=$((need + QWEN_VRAM_MIB))
  fi
  coord_log "Free ${free} MiB, olmOCR needs ${need} MiB."
  [ "$free" -lt "$need" ]
}

trap start_qwen EXIT TERM INT

if qwen_must_stop; then
  stop_qwen
else
  coord_log "Running next to $FREE_QWEN_CONTAINER."
fi

runtime=/home/imdevil/olmocr-quality
if [ "${OLMOCR_CONTAINER:-0}" != "1" ]; then export PATH="$runtime/.venv/bin:$PATH"; fi
# WSL2 does not expose CUDA UVA, which vLLM's V2 runner requires.
export VLLM_USE_V2_MODEL_RUNNER=0

# This host shares its GPU with Qwen, meeting, embedding and reranking services.
# A single eager-mode sequence avoids CUDA graph reservation. An explicit
# 384 MiB KV cache (7,008 tokens) keeps the 7B FP8 model at about 11 GB
# while the app's other CUDA services remain online; the API serializes jobs.
# max_pixels matches the pipeline's 1288px render so pages are not downscaled;
# 6.5k context fits a square page's 2,116 image tokens plus 4,096 output tokens.
vllm serve "${OLMOCR_MODEL_PATH:-allenai/olmOCR-2-7B-1025-FP8}" \
  --host 127.0.0.1 --port 8000 \
  --served-model-name olmocr \
  --max-model-len 6656 \
  --gpu-memory-utilization "${OLMOCR_GPU_MEMORY_UTILIZATION:-0.85}" \
  --kv-cache-memory-bytes 384M \
  --max-num-seqs 1 \
  --enforce-eager \
  --tensor-parallel-size 1 \
  --mm-processor-kwargs '{"max_pixels":1658944}' \
  --limit-mm-per-prompt '{"image":1,"video":0}' &

VLLM_PID=$!
wait $VLLM_PID
