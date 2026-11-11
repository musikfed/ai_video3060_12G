"""Local PEGINELAB media editor; no AI generation is claimed."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.getenv("STUDIO_DATA", str(ROOT / "data"))).resolve()
MEDIA = DATA / "media"
JOBS = DATA / "jobs"
for path in (MEDIA, JOBS):
    path.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="PEGINELAB Video Studio", version="0.1.0")
LOCK = threading.Lock()
VALID = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".flac", ".ogg"}
IMAGE = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO = {".mp4", ".mov", ".mkv", ".webm"}
AUDIO = VALID - IMAGE - VIDEO
MAX_UPLOAD = int(os.getenv("STUDIO_UPLOAD_MAX_MB", "1024")) * 1024 * 1024


class Clip(BaseModel):
    media_id: str
    duration: float = Field(default=5, ge=0.2, le=600)
    start: float = Field(default=0, ge=0, le=36000)


class RenderRequest(BaseModel):
    clips: list[Clip] = Field(min_length=1, max_length=100)
    audio_id: str | None = None
    width: int = 1280
    height: int = 720
    fps: int = Field(default=24, ge=12, le=60)


def _safe_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(400, "Invalid media or job id") from exc


def _media_path(media_id: str) -> Path:
    uid = _safe_id(media_id)
    hits = list(MEDIA.glob(uid + ".*"))
    if len(hits) != 1:
        raise HTTPException(404, "Media not found")
    return hits[0]


def _job_file(job_id: str) -> Path:
    return JOBS / _safe_id(job_id) / "status.json"


def _store_status(job_id: str, **values):
    path = _job_file(job_id)
    with LOCK:
        state = json.loads(path.read_text()) if path.exists() else {}
        state.update(values)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False))
        temp.replace(path)


def probe(path: Path) -> dict:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(p.stdout)


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "port": int(os.getenv("STUDIO_PORT", "10720")),
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "ai_generation": False, "editor": True}


@app.get("/api/system")
def system():
    gpu = None
    if shutil.which("nvidia-smi"):
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,temperature.gpu,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=8, check=True)
            gpu = r.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            pass
    return {"gpu": gpu, "ai_generation": "not installed", "data": str(DATA)}


@app.post("/api/media")
async def upload(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in VALID:
        raise HTTPException(415, "Unsupported file type")
    media_id = str(uuid.uuid4())
    dest = MEDIA / (media_id + suffix)
    total = 0
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD:
                    raise HTTPException(413, "File too large")
                out.write(chunk)
        if total == 0:
            raise HTTPException(400, "Empty file")
        if suffix not in IMAGE:
            probe(dest)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    kind = "image" if suffix in IMAGE else "video" if suffix in VIDEO else "audio"
    return {"id": media_id, "name": Path(file.filename or "").name, "kind": kind, "bytes": total}


@app.get("/api/media/{media_id}")
def get_media(media_id: str):
    return FileResponse(_media_path(media_id))


def render_worker(job_id: str, request: RenderRequest):
    work = JOBS / job_id
    pieces = []
    try:
        _store_status(job_id, state="running", progress=0, message="Подготовка")
        for i, clip in enumerate(request.clips):
            source = _media_path(clip.media_id)
            if source.suffix.lower() not in IMAGE | VIDEO:
                raise ValueError("Audio cannot be a visual clip")
            target = work / f"clip-{i:03d}.mp4"
            vf = (f"scale={request.width}:{request.height}:force_original_aspect_ratio=decrease,"
                  f"pad={request.width}:{request.height}:(ow-iw)/2:(oh-ih)/2,"
                  "setsar=1,format=yuv420p")
            args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
            if source.suffix.lower() in IMAGE:
                args += ["-loop", "1", "-framerate", str(request.fps), "-i", str(source)]
            else:
                args += ["-ss", str(clip.start), "-i", str(source)]
            args += ["-t", str(clip.duration), "-an", "-vf", vf, "-r", str(request.fps),
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                     "-pix_fmt", "yuv420p", str(target)]
            subprocess.run(args, check=True, capture_output=True, text=True, timeout=3600)
            pieces.append(target)
            _store_status(job_id, progress=int(85 * (i + 1) / len(request.clips)),
                          message=f"Сцена {i+1}/{len(request.clips)}")
        manifest = work / "concat.txt"
        manifest.write_text("".join(f"file '{p.name}'\n" for p in pieces))
        joined = work / "joined.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                        "-f", "concat", "-safe", "1", "-i", str(manifest),
                        "-c", "copy", str(joined)], cwd=work, check=True,
                       capture_output=True, text=True, timeout=3600)
        output = work / "video.mp4"
        if request.audio_id:
            sound = _media_path(request.audio_id)
            if sound.suffix.lower() not in AUDIO | VIDEO:
                raise ValueError("Soundtrack must be audio or video")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                            "-i", str(joined), "-stream_loop", "-1", "-i", str(sound),
                            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                            "-c:a", "aac", "-b:a", "192k", "-shortest", str(output)],
                           check=True, capture_output=True, text=True, timeout=3600)
        else:
            joined.replace(output)
        _store_status(job_id, state="done", progress=100, message="Готово")
    except Exception as exc:
        detail = exc.stderr[-1200:] if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
        _store_status(job_id, state="error", message=detail[:1500])
    finally:
        for piece in pieces:
            piece.unlink(missing_ok=True)
        (work / "concat.txt").unlink(missing_ok=True)
        (work / "joined.mp4").unlink(missing_ok=True)


@app.post("/api/render")
def render(request: RenderRequest):
    if (request.width, request.height) not in {(1280, 720), (720, 1280), (854, 480), (480, 854)}:
        raise HTTPException(422, "Unsupported dimensions")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise HTTPException(503, "ffmpeg and ffprobe required")
    for clip in request.clips:
        path = _media_path(clip.media_id)
        if path.suffix.lower() not in IMAGE | VIDEO:
            raise HTTPException(422, "Timeline requires image/video")
    if request.audio_id:
        path = _media_path(request.audio_id)
        if path.suffix.lower() not in AUDIO | VIDEO:
            raise HTTPException(422, "Invalid soundtrack")
    job_id = str(uuid.uuid4())
    (JOBS / job_id).mkdir()
    _store_status(job_id, id=job_id, state="queued", progress=0, message="В очереди")
    threading.Thread(target=render_worker, args=(job_id, request), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    file = _job_file(job_id)
    if not file.exists():
        raise HTTPException(404, "Job not found")
    return json.loads(file.read_text())


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str):
    file = _job_file(job_id).parent / "video.mp4"
    if not file.exists():
        raise HTTPException(404, "Video not ready")
    return FileResponse(file, media_type="video/mp4", filename="peginelab-video.mp4")
