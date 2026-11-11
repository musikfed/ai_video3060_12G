#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${STUDIO_PORT:-10720}"
HOST="${STUDIO_HOST:-0.0.0.0}"
if ss -ltnH "( sport = :$PORT )" | grep -q .; then
  echo "ERROR: port $PORT already occupied, refusing to start" >&2
  exit 1
fi
export STUDIO_PORT="$PORT"
export STUDIO_DATA="${STUDIO_DATA:-$(pwd)/data}"
mkdir -p "$STUDIO_DATA"
exec uv run --no-dev uvicorn app.main:app --host "$HOST" --port "$PORT"
