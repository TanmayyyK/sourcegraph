"""
╔══════════════════════════════════════════════════════════════════════╗
║  SourceGraph — Extractor Worker (FastAPI + Tailscale)               ║
║  Owner : Yogesh (M2 Node)                                          ║
║  File  : worker.py                                                 ║
║                                                                    ║
║  PURPOSE:                                                          ║
║    1. Receive video uploads from Tanmay's Dashboard                ║
║    2. Demux → 1-fps JPEG frames + 16 kHz mono WAV (via FFmpeg)     ║
║    3. Normalize frames to 224×224 tensors                          ║
║    4. Receive packet_id from Orchestrator                          ║
║    5. Parallel broadcast to Rohit (visual) & Yug (OCR)             ║
║    6. Clean up local cache after broadcast                         ║
║                                                                    ║
║  ENDPOINTS:                                                        ║
║    GET  /            → health check                                ║
║    POST /extract     → receive video, kick off background pipeline ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
import os
import json
import uuid
import shutil
import subprocess
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env if present

app = FastAPI(title="Extractor Node (Yogesh)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────

# Team Endpoints (Tailscale IPs)
ROHIT_URL      = os.getenv("ROHIT_URL", "http://100.119.250.125:8001/embed/visual")
YUG_VISUAL_URL = os.getenv("YUG_VISUAL_URL", "http://100.115.89.72:8002/embed/text")
YUG_AUDIO_URL  = os.getenv("YUG_AUDIO_URL", "http://100.115.89.72:8002/embed/audio")

# Paths
SCRIPT_DIR   = Path(__file__).resolve().parent
OUTPUT_DIR   = SCRIPT_DIR / "_pipeline_output"
FRAMES_DIR   = OUTPUT_DIR / "frames"
AUDIO_PATH   = OUTPUT_DIR / "audio_16k_mono.wav"

# FFmpeg tuning
FRAME_RATE      = int(os.getenv("FRAME_RATE", "1"))
AUDIO_SAMPLE_HZ = int(os.getenv("AUDIO_SAMPLE_HZ", "16000"))
JPEG_QUALITY    = int(os.getenv("JPEG_QUALITY", "2"))
FRAME_SIZE      = int(os.getenv("FRAME_SIZE", "224"))

# Request timeout for GPU nodes (seconds)
GPU_TIMEOUT = int(os.getenv("GPU_TIMEOUT", "30"))

# Thread pool for parallel GPU broadcasting
GPU_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gpu_broadcast")

# ─────────────────────────────────────────────────────────────────────
# JOB STATUS STORE — in-memory log of all pipeline activity
# ─────────────────────────────────────────────────────────────────────
job_logs: dict[str, list[str]] = defaultdict(list)

def log(job_id: str, msg: str):
    """Append a timestamped message to this job's log."""
    entry = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    job_logs[job_id].append(entry)
    print(entry)   # still prints to terminal too

# ─────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def health_check():
    return {"status": "online", "node": "Yogesh-M2", "hardware": "Apple Silicon"}

@app.get("/status/{job_id}")
async def job_status(job_id: str):
    """Return full log of a specific job for Claude Haiku to read."""
    logs = job_logs.get(job_id, [])
    return {
        "job_id": job_id,
        "total_events": len(logs),
        "log": logs,
        "status": "complete" if any("Pipeline complete" in l for l in logs)
                  else "failed" if any("Demux failed" in l for l in logs)
                  else "running" if logs
                  else "not_found"
    }

@app.get("/status")
async def all_jobs():
    """Return summary of all jobs — so Claude Haiku knows what's running."""
    summary = {}
    for jid, logs in job_logs.items():
        summary[jid] = {
            "total_events": len(logs),
            "last_event": logs[-1] if logs else None,
            "status": "complete" if any("Pipeline complete" in l for l in logs)
                      else "failed" if any("Demux failed" in l for l in logs)
                      else "running"
        }
    return {"jobs": summary}

# ─────────────────────────────────────────────────────────────────────
# DEMUXER — FFmpeg frame + audio extraction
# ─────────────────────────────────────────────────────────────────────

def demux_video(video_path: Path, job_id: str) -> tuple[Path, Path]:
    job_output_dir = SCRIPT_DIR / "_pipeline_output" / job_id
    job_frames_dir = job_output_dir / "frames"
    job_audio_path = job_output_dir / "audio_16k_mono.wav"
    job_frames_dir.mkdir(parents=True, exist_ok=True)

    print(f"🎬 [M2] Demuxing: {video_path.name}")
    t0 = time.perf_counter()

    # extract frames
    frame_pattern = str(job_frames_dir / "frame_%05d.jpg")
    frame_cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "videotoolbox",
        "-i", str(video_path),
        "-vf", f"fps={FRAME_RATE},scale={FRAME_SIZE}:{FRAME_SIZE}:force_original_aspect_ratio=disable",
        "-fps_mode", "cfr",
        "-qscale:v", str(JPEG_QUALITY),
        frame_pattern,
    ]

    result = subprocess.run(frame_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print("⚠️  VideoToolbox unavailable — falling back to software decode")
        frame_cmd_sw = [c for c in frame_cmd if c not in ("-hwaccel", "videotoolbox")]
        result = subprocess.run(frame_cmd_sw, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg frame extraction failed:\n{result.stderr.decode()}")

    n_frames = len(list(job_frames_dir.glob("*.jpg")))

    # extract audio
    audio_cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(AUDIO_SAMPLE_HZ),
        "-ac", "1",
        str(job_audio_path),
    ]

    result = subprocess.run(audio_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed:\n{result.stderr.decode()}")

    elapsed = time.perf_counter() - t0
    print(f"✅ [M2] Demux done in {elapsed:.2f}s → {n_frames} frames ({FRAME_SIZE}×{FRAME_SIZE}), WAV @ {AUDIO_SAMPLE_HZ} Hz")
    return job_frames_dir, job_audio_path

# ─────────────────────────────────────────────────────────────────────
# PACKET BUILDER — Using Tanmay's packet_id
# ─────────────────────────────────────────────────────────────────────

def build_frame_packet(video_name: str, frame_index: int, packet_id: str) -> dict:
    """
    Generate the metadata skeleton for a single frame.
    Now correctly injects the packet_id sent by Orchestrator!
    """
    return {
        "packet_id":        packet_id,
        "video_name":       video_name,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "frame_index":      frame_index,
        "video_timestamp_s": frame_index / FRAME_RATE,
    }

# ─────────────────────────────────────────────────────────────────────
# GPU BROADCAST — Parallel dual-pipe to Rohit + Yug
# ─────────────────────────────────────────────────────────────────────

def _send_to_node(label: str, url: str, frame_name: str,
                  frame_bytes: bytes, metadata: dict) -> str:
    """
    POST a single frame + metadata JSON to one GPU node.
    """
    try:
        files = {"image": (frame_name, frame_bytes, "image/jpeg")}
        # Yug expects a Form field literally called "metadata" containing a JSON string!
        data  = {"metadata": json.dumps(metadata)}
        resp  = requests.post(url, files=files, data=data, timeout=GPU_TIMEOUT)
        return f"📤 → {label}: {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return f"❌ → {label}: Connection refused (server down?)"
    except requests.exceptions.Timeout:
        return f"⏳ → {label}: Timed out after {GPU_TIMEOUT}s"
    except Exception as e:
        return f"🚨 → {label}: {e}"

def broadcast_frame(frame_path: Path, frame_name: str, metadata: dict, job_id: str):
    """Parallel dual-pipe"""
    frame_bytes = frame_path.read_bytes()
    metadata["frame_sha256"] = hashlib.sha256(frame_bytes).hexdigest()

    targets = [
        ("Rohit/Vision (3050)", ROHIT_URL),
        ("Yug/OCR (2050)",      YUG_VISUAL_URL),
    ]

    futures = {
        GPU_POOL.submit(_send_to_node, label, url, frame_name, frame_bytes, metadata.copy()): label
        for label, url in targets
    }

    for future in as_completed(futures):
        log(job_id, future.result())

def broadcast_audio(audio_bytes: bytes, audio_filename: str, video_name: str, packet_id: str, job_id: str):
    """
    POST the WAV file to Yug (OCR/transcription) only.
    Now correctly passes Tanmay's packet_id to Yug!
    """
    try:
        # Field must be 'audio' to match Yug's process_audio signature
        files = {"audio": (audio_filename, audio_bytes, "audio/wav")}
        
        # Send metadata as JSON string just like frames do
        meta_json = json.dumps({"video_name": video_name, "packet_id": packet_id})
        data = {"metadata": meta_json}

        resp  = requests.post(YUG_AUDIO_URL, files=files, data=data, timeout=GPU_TIMEOUT)
        log(job_id, f"📤 → Yug/Audio: {resp.status_code}")
    except requests.exceptions.ConnectionError:
        log(job_id, "❌ → Yug/Audio: Connection refused")
    except requests.exceptions.Timeout:
        log(job_id, f"⏳ → Yug/Audio: Timed out after {GPU_TIMEOUT}s")
    except Exception as e:
        log(job_id, f"🚨 → Yug/Audio: {e}")

# ─────────────────────────────────────────────────────────────────────
# PIPELINE — Demux → Packet → Broadcast → Cleanup
# ─────────────────────────────────────────────────────────────────────

def process_media_pipeline(file_path: str, video_name: str, job_id: str, packet_id: str):
    """
    Full background pipeline...
    """
    log(job_id, f"🎬 START pipeline for: {video_name}")

    video_path = Path(file_path)
    if not video_path.exists():
        log(job_id, f"❌ File not found: {file_path}")
        return

    try:
        frames_dir, audio_path = demux_video(video_path, job_id)
        log(job_id, "✅ Demux complete")
    except RuntimeError as e:
        log(job_id, f"❌ Demux failed: {e}")
        return

    audio_bytes = audio_path.read_bytes()
    log(job_id, f"🎵 Audio loaded into memory ({len(audio_bytes)} bytes)")

    # Pass the actual Orchestrator packet_id down to the audio broadcast
    audio_future = GPU_POOL.submit(broadcast_audio, audio_bytes, audio_path.name, video_name, packet_id, job_id)
    log(job_id, "📡 Audio submitted to thread pool → Yug")

    frames = sorted(frames_dir.glob("*.jpg"))
    total = len(frames)
    log(job_id, f"🚀 Broadcasting {total} frames to Rohit + Yug")

    for i, frame in enumerate(frames):
        frame_index = i + 1
        # Use Tanmay's packet_id!
        metadata = build_frame_packet(video_name, frame_index, packet_id)
        log(job_id, f"📸 Frame {frame_index}/{total}: {frame.name}")
        broadcast_frame(frame, frame.name, metadata, job_id)

    try:
        audio_result = audio_future.result(timeout=60)
        log(job_id, "✅ Audio broadcast confirmed")
    except Exception as e:
        log(job_id, f"⚠️  Audio broadcast error: {e}")

    try:
        shutil.rmtree(SCRIPT_DIR / "_pipeline_output" / job_id)
        os.remove(file_path)
        log(job_id, "🧹 Cleanup complete")
    except Exception as e:
        log(job_id, f"⚠️  Cleanup warning: {e}")

    log(job_id, f"✅ Pipeline complete. Frames sent: {total}, Resolution: {FRAME_SIZE}×{FRAME_SIZE}")

# ─────────────────────────────────────────────────────────────────────
# API ENDPOINT — Receive video from Tanmay's Dashboard
# ─────────────────────────────────────────────────────────────────────

@app.post("/extract")
async def start_extraction(
    background_tasks: BackgroundTasks, 
    video: UploadFile = File(...),
    packet_id: str = Form(...)      # ← WE NOW ACCEPT TANMAY'S PACKET ID!
):
    """
    Receives a video file, saves it locally, and kicks off
    the demux + GPU broadcast pipeline in the background.
    """
    job_id = str(uuid.uuid4())
    
    local_filename = f"received_{job_id}_{video.filename}"
    local_path = str(SCRIPT_DIR / local_filename)

    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)

    file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
    print(f"📥 [M2] Received: {local_filename} ({file_size_mb:.1f} MB)")

    # Pass packet_id down to the pipeline so frames + audio get it
    background_tasks.add_task(process_media_pipeline, local_path, video.filename, job_id, packet_id)

    return {
        "status": "file_received",
        "job_id": job_id,
        "saved_as": local_filename,
        "size_mb": round(file_size_mb, 2),
        "message": f"Pipeline started. Poll /status/{job_id} for live updates.",
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)