import os, random, shutil, subprocess, tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

# ---------- FastAPI ----------
app = FastAPI(title="YouTube Shorts Generator")

origins = [
    "https://youtube-short-wiz.lovable.app",        # published Lovable domain
    "https://preview--youtube-short-wiz.lovable.app", # preview domain
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.options("/generate")
async def options_generate():
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "https://preview--youtube-short-wiz.lovable.app",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
    )

# ---------- Models ----------
class GenerateRequest(BaseModel):
    youtube_url: str = Field(..., examples=["https://www.youtube.com/watch?v=xxxx"])
    clip_length: int = Field(60, ge=10, le=60, description="Seconds (10–60)")
    response_mode: str = Field("stream", regex="^(stream|base64)$")

# ---------- Utils ----------
def _ensure_tool(name: str):
    if shutil.which(name) is None:
        raise RuntimeError(f"Required tool '{name}' not found in PATH")

def _validate_youtube_url(u: str):
    try:
        p = urlparse(u)
        if p.netloc not in ("www.youtube.com", "youtube.com", "youtu.be", "m.youtube.com"):
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

def _run(cmd: list[str], cwd: str | None = None):
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stdout.decode(errors='ignore')}")
    return p.stdout.decode(errors="ignore")

def _iterfile(path: str, chunk_size: int = 1024 * 1024):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk

# ---------- Routes ----------
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/ping")
def ping():
    return {"status": "ok", "message": "API is alive"}

@app.post("/generate")
def generate(req: GenerateRequest, bg: BackgroundTasks):
    _ensure_tool("ffmpeg")
    _ensure_tool("ffprobe")
    _ensure_tool("yt-dlp")
    _validate_youtube_url(req.youtube_url)

    return {"status": "ok", "message": "Validation passed"}

    tmpdir = tempfile.mkdtemp(prefix="ytshorts_")
    bg.add_task(shutil.rmtree, tmpdir, ignore_errors=True)

    try:
        # 1) Download best MP4 with yt-dlp (merged with ffmpeg if needed)
        outtmpl = str(Path(tmpdir) / "input.%(ext)s")
        ytdlp_fmt = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best"
        _run(["yt-dlp", "-f", ytdlp_fmt, "-o", outtmpl, "--no-playlist", req.youtube_url])

        # Resolve the downloaded mp4 path
        mp4s = list(Path(tmpdir).glob("input.*"))
        if not mp4s:
            raise RuntimeError("Download failed: no input file found")
        input_path = str(mp4s[0])

        # 2) Get duration (in seconds)
        dur_str = _run([
            "ffprobe","-v","error","-show_entries","format=duration",
            "-of","default=noprint_wrappers=1:nokey=1", input_path
        ]).strip()
        duration = int(float(dur_str)) if dur_str else 0
        if duration <= 0:
            raise RuntimeError("Failed to probe duration")
        clip_len = min(max(req.clip_length, 10), 60)
        if duration <= clip_len + 2:
            start = 0
            clip_len = max(5, duration - 1)
        else:
            start = random.randint(0, duration - clip_len - 1)

        # 3) Trim + make vertical 9:16 + re-encode H.264/AAC
        output_path = str(Path(tmpdir) / "short.mp4")
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        _run([
            "ffmpeg","-y",
            "-ss", str(start), "-t", str(clip_len),
            "-i", input_path,
            "-vf", vf, "-r", "30",
            "-c:v","libx264","-preset","veryfast","-crf","23",
            "-c:a","aac","-b:a","128k","-movflags","+faststart",
            output_path
        ])

        if req.response_mode == "base64":
            import base64
            with open(output_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            # Warning: large payloads; use only if your frontend needs it
            return JSONResponse({"filename": "short.mp4", "mime": "video/mp4", "base64": b64})

        headers = {
            "Content-Disposition": 'attachment; filename="short.mp4"',
            "Cache-Control": "no-store",
        }
        return StreamingResponse(_iterfile(output_path), media_type="video/mp4", headers=headers)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))