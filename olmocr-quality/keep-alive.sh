#!/usr/bin/env bash
set -euo pipefail

service_name="olmocr-vllm.service"

systemctl start "$service_name"
trap 'systemctl stop "$service_name" >/dev/null 2>&1 || true' EXIT INT TERM

# Keeping this WSL invocation open prevents WSL from shutting down the distro
# while the system service is the only remaining Linux workload.
while systemctl is-active --quiet "$service_name"; do
  sleep 5
done

wait "$(jobs -p)" 2>/dev/null || true
