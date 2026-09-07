#!/usr/bin/env bash
set -euo pipefail
runtime=/home/imdevil/olmocr-quality
"$runtime/.venv/bin/python" - <<'PY'
import importlib.metadata as metadata
import importlib.util
from pathlib import Path
import torch
for name in ('vllm', 'olmocr', 'torch', 'transformers'):
    print(name, metadata.version(name))
print('CUDA', torch.version.cuda, 'GPU', torch.cuda.get_device_name(), 'capability', torch.cuda.get_device_capability())
spec = importlib.util.find_spec('olmocr.pipeline')
source = Path(spec.origin).read_text()
for number, line in enumerate(source.splitlines(), 1):
    if any(term in line for term in ('guided', 'max_concurrent', 'apply_filter', 'target_longest', 'build_olmocr', 'max_page_retries')):
        print(number, line)
PY
