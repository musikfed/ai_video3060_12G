#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
 echo "Missing ffmpeg/ffprobe; install separately: sudo apt install ffmpeg" >&2
 exit 1
fi
uv sync --no-dev
mkdir -p data/media data/jobs
echo "Installed in isolated .venv. Run bash scripts/start.sh"
