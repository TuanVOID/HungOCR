#!/usr/bin/env bash
set -euo pipefail

service_name="olmocr-vllm.service"

systemctl start "$service_name"
# Model shutdown is owned by stop.ps1 or the UI idle lifecycle manager.
# An old keeper exiting must not stop a model started by a newer request.

# Keeping this WSL invocation open prevents WSL from shutting down the distro
# while the system service is the only remaining Linux workload.
while systemctl is-active --quiet "$service_name"; do
  sleep 5
done

wait "$(jobs -p)" 2>/dev/null || true
