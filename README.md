# PEGINELAB AI Video Studio · CORE:10720

**Current status: working-code editing MVP (deployment and render tests on CORE pending). No AI video model is installed by this repository.** The [eleven-language showcase](docs/showcase/README.md) remains intact.

## Implemented in this branch
- Upload PNG/JPEG/WebP images, MP4/MOV/MKV/WebM video, MP3/WAV/M4A/FLAC/OGG audio.
- Arrange visual clips in a timeline with duration and trim-start options; move clips up/down.
- Export landscape 1280×720 or portrait 720×1280 MP4 using FFmpeg / H.264; 480p alternatives.
- Optional audio track loops to match the video, AAC encoding.
- Persistent job status file, HTTP job polling, output MP4 download and nvidia-smi monitoring.
- No automatic changes to other services, GPUs, Ollama or system drivers.

**Not implemented yet:** text-to-video or image-to-video using Wan/LTX/Hunyuan; TTS, subtitles, AI upscaling, original video-audio mixing, smooth transitions, persistent editable projects, generation resume after process restart, cancellation, multi-user security. Existing clip audio is deliberately discarded and replaced by the optional soundtrack. A job interrupted by server process restart will not resume. This is a first media editor only.

## Target hardware
192.168.0.100 · Ubuntu 24.04 · 2× Xeon 2650 · 48 GB RAM · RTX 3060 12GB. Disk target `/1tbdisk` with user-reported 846 GB available. **Port 10720 must be confirmed free on the actual host.**

## Deployment (use this branch until merged)
```bash
cd /1tbdisk
git clone https://github.com/musikfed/ai_video3060_12G.git
cd ai_video3060_12G
git switch feature/studio-10720-mvp
bash scripts/doctor.sh
# If ffmpeg is missing: sudo apt update && sudo apt install ffmpeg
bash scripts/install.sh
bash scripts/start.sh
```
Verify `curl -fsS http://127.0.0.1:10720/api/health`, then open `http://192.168.0.100:10720/` over LAN/VPN. Run in a terminal and stop with Ctrl+C. Do not open 10720 on a public IP: this MVP has **no authentication or upload rate limit**.

## Optional: free memory for future AI generation
Video editing here is CPU-encoded and does not need GPU VRAM. **Never blindly unload all GPU processes.** Inspect `nvidia-smi` and `ollama ps`; only unload explicitly identified Ollama models you own using `ollama stop MODEL_NAME`. Do not stop the service, kill other programs or delete downloaded models. Future AI-engine integration will implement a separate gated VRAM scheduler.

## Files and directories
`app/main.py` — FastAPI backend; `static/index.html` — local web interface; `scripts/doctor.sh` — read-only inspection; `scripts/install.sh` — isolated uv environment; `scripts/start.sh` — port collision check and startup. All user content is in gitignored `data/`. GitHub holds code only, not huge model weights or uploads.

## Smoke checks
```bash
bash scripts/doctor.sh
uv run --no-dev python -m compileall -q app
uv run --no-dev python -c "from app.main import app; print(app.title)"
bash scripts/start.sh
# In another terminal:
curl -fsS http://127.0.0.1:10720/api/health
curl -fsS http://127.0.0.1:10720/api/system
```
Test upload and export through the UI, inspect the resulting MP4 with `ffprobe`. Only after a successful smoke check should we install a service and connect model backends.
