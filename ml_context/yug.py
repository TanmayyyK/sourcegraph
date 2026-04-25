"""
╔══════════════════════════════════════════════════════════════════════╗
║  SourceGraph — Context ML Node (FastAPI + Tailscale)                ║
║  Owner : Yug (RTX 2050)                                             ║
║  File  : main.py / yug.py                                           ║
║                                                                     ║
║  PURPOSE:                                                           ║
║    1. Receive 224×224 JPEG frames from Yogesh → OCR + embedding     ║
║    2. Receive 16 kHz WAV from Yogesh → transcription                ║
║    3. Forward all results to Tanmay's Orchestrator                  ║
║                                                                     ║
║  ENDPOINTS:                                                         ║
║    GET  /             → health check                                ║
║    POST /embed/text   → frame stream (OCR + MiniLM)                 ║
║    POST /embed/audio  → single WAV (transcription)                  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import requests
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from overwatch_logic import OverwatchNode

# ─────────────────────────────────────────────────────────────────────
# ENV — load before everything else
# ─────────────────────────────────────────────────────────────────────
load_dotenv()  # reads .env sitting next to main.py

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION — all values from .env with safe fallbacks
# ─────────────────────────────────────────────────────────────────────
# POINT DIRECTLY TO TANMAY'S V3 WEBHOOK ENDPOINT
TANMAY_URL = os.getenv("TANMAY_URL", "http://100.69.253.89:8000/api/v1/webhooks/vector")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8002"))

# ─────────────────────────────────────────────────────────────────────
# APP + MIDDLEWARE
# ─────────────────────────────────────────────────────────────────────
app = FastAPI(title="Context ML Node (Yug) - Overwatch")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global OverwatchNode — loaded once at startup
node = OverwatchNode()


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def _parse_metadata(raw: str) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        print(f"⚠️  [Yug Node] Could not parse metadata: {raw!r}")
        return {}

def _forward_to_orchestrator(payload: dict, label: str = "") -> None:
    try:
        # REQUIRED FOR V3 ORCHESTRATOR
        secret = os.getenv("WEBHOOK_SECRET", "change-me-in-production")
        headers = {"X-Webhook-Secret": secret}
        resp = requests.post(TANMAY_URL, json=payload, headers=headers, timeout=30)
        
        # Log if orchestrator rejects it (so Yug can debug easily without crashing)
        if resp.status_code not in (200, 202):
            print(f"⚠️ [Yug Node] Orchestrator ignored/rejected {label} ({resp.status_code}): {resp.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"🚨 [Yug Node] Orchestrator unreachable{' (' + label + ')' if label else ''}")
    except requests.exceptions.Timeout:
        print(f"⏳ [Yug Node] Orchestrator timed out{' (' + label + ')' if label else ''}")
    except Exception as exc:
        print(f"🚨 [Yug Node] Orchestrator forward error: {exc}")


# ─────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def health_check():
    return {
        "status":   "online",
        "node":     "ml_context",
        "protocol": "Anti-Gravity Context Managed",
        "task":     "Multimodal Overwatch",
    }


# ─────────────────────────────────────────────────────────────────────
# AUDIO ENDPOINT
# ─────────────────────────────────────────────────────────────────────

@app.post("/embed/audio")
async def process_audio(
    background_tasks: BackgroundTasks,
    audio:    UploadFile = File(...),
    metadata: str = Form("{}"),
):
    contents      = await audio.read()
    meta          = _parse_metadata(metadata)
    packet_id     = meta.get("packet_id", "unknown")
    video_name    = meta.get("video_name", "unknown")
    temp_wav_path = f"temp_audio_{packet_id}.wav"

    with open(temp_wav_path, "wb") as f:
        f.write(contents)

    print(f"🎙️  [Yug Node] Audio received: {audio.filename} (video: {video_name}) but explicitly dropping processing to preserve VRAM.")

    def _run_audio_pipeline(wav_path: str) -> None:
        # User requested to drop Audio Feature to maintain strict pipeline stability.
        # Clean up temp wave immediately.
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError as exc:
                print(f"⚠️  [Yug Node] Could not delete temp WAV: {exc}")

        # Still prime visual phase since audio is skipped!
        try:
            node.prepare_visual_phase()
        except Exception as exc:
            print(f"⚠️  [Yug Node] prepare_visual_phase error: {exc}")

    background_tasks.add_task(_run_audio_pipeline, temp_wav_path)
    return {
        "status":  "accepted_but_bypassed",
        "message": "Audio discarded gracefully. Proceeding directly to pure vision processing.",
    }


# ─────────────────────────────────────────────────────────────────────
# VISUAL / OCR ENDPOINT
# ─────────────────────────────────────────────────────────────────────

@app.post("/embed/text")
async def process_frame(
    image:    UploadFile = File(...),
    metadata: str = Form("{}"),
):
    # ── Parse metadata ────────────────────────────────────────────────
    meta        = _parse_metadata(metadata)
    packet_id   = meta.get("packet_id",         "unknown")
    video_name  = meta.get("video_name",        "unknown")
    frame_index = meta.get("frame_index",       -1)
    video_ts    = meta.get("video_timestamp_s", -1)

    # ── OCR + embedding ───────────────────────────────────────────────
    contents       = await image.read()
    visual_results = node.run_visual_phase(contents)

    if visual_results.get("ocr_text"):
        print(
            f"🔍 [Yug Node] OCR | frame {frame_index} | {video_name} | "
            f"{packet_id[:8]}… → {visual_results['ocr_text'][:120]}"
        )

    # Calculate float timestamp for Tanmay's strict Pydantic Model
    valid_timestamp = float(video_ts) if float(video_ts) >= 0 else float(frame_index)

    # ── STRICT TANMAY PAYLOAD ────────────────────────────────────────────
    source_packet = {
        "packet_id": packet_id,
        "timestamp": valid_timestamp,
        "text_vector": visual_results.get("vector"),
        "source_node": "ml_context"
    }

    # ── Forward to Orchestrator ───────────────────────────────────────
    _forward_to_orchestrator(source_packet, label=f"frame {frame_index}")

    return source_packet


# ─────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
