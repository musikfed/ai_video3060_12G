#!/usr/bin/env bash
set -uo pipefail
echo "=== PEGINELAB STUDIO READ-ONLY PRECHECK ==="
echo "Host: $(hostname)"; python3 --version; uv --version || true
echo "=== Mount ==="; df -h /1tbdisk || true
echo "=== Port 10720 ==="
if ss -ltnH "( sport = :10720 )" | grep -q .; then
  echo "BUSY: port 10720 is already listening; do not start"; ss -ltnp "( sport = :10720 )"
else echo "FREE: no listener on 10720 at check time"; fi
echo "=== GPU ==="; nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,temperature.gpu,power.draw --format=csv || true
echo "=== GPU processes ==="; nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv || true
echo "=== Ollama active models ==="; ollama ps || true
echo "=== Video tools ==="; command -v ffmpeg || true; command -v ffprobe || true
echo "=== Runtime ==="; free -h
