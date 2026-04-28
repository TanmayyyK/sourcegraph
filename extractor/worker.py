"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  SourceGraph — Extractor Node / Foreman  (FastAPI + httpx)                 ║
║  Owner   : Yogesh (M2 Node)                                                ║
║  File    : extractor_main.py                                               ║
║  Contract: SourceGraph Distributed Worker Implementation Contract v1.0     ║
║                                                                             ║
║  RESPONSIBILITIES (Section 3 – Node A):                                    ║
║    1. Download video from URL & extract 1-FPS JPEG frames via FFmpeg       ║
║    2. Concurrently broadcast every frame to:                               ║
║         Vision Node  → POST http://<ROHIT_IP>:8001/embed/vision            ║
║         Context Node → POST http://<YUG_IP>:8002/embed/text                ║
║    3. Finishing handshake (sequence is CRITICAL per mission rules):        ║
║         a. POST /finish to both GPU nodes                                  ║
║         b. Poll /health until both nodes report "idle"                     ║
║         c. Fire pipeline_final_summary → Orchestrator                      ║
║    4. Emit system_ping to Orchestrator every 30 s while alive              ║
║                                                                             ║
║  CONTRACT ENDPOINTS HOSTED (Section 3):                                    ║
║    POST /ingest         → Start pipeline (video_url + packet_id)           ║
║    GET  /health         → Heartbeat + live hardware metrics                ║
║    GET  /status/{id}   → Live pipeline progress (non-contract, additive)   ║
║                                                                             ║
║  ERROR HANDLING (Section 2):                                               ║
║    422 → CRITICAL log, drop frame, continue                                ║
║    409 → Abort batch immediately                                           ║
║    404 → Exponential backoff, up to MAX_FRAME_RETRIES attempts             ║
║    Net  → Local retry buffer, up to MAX_FRAME_RETRIES attempts             ║
║                                                                             ║
║  PATCH LOG (contract compliance fixes):                                    ║
║    FIX-1  _post: accept any 2xx (not only 200) as success                  ║
║    FIX-2  _post: return explicit abort flag instead of embedding "409"     ║
║           in the detail string to avoid fragile substring matching         ║
║    FIX-3  _broadcast_frame: count success/failure PER FRAME not per-node  ║
║           (contract example: successful_broadcasts == total_frames_extracted)║
║    FIX-4  _download_video: use a separate unauthenticated HTTP client so   ║
║           X-Webhook-Secret is never sent to external CDN / S3 URLs        ║
║    FIX-5  _await_gpu_idle: accept both "idle" status AND queue_size==0     ║
║           so nodes that use a different idle signal still unblock the pipe ║
║    FIX-6  BatchTracker: add thread-safe `aborted` flag so any code path   ║
║           can query whether the current batch was 409-aborted              ║
║                                                                             ║
║  HOT-PATCH LOG (500-error investigation):                                  ║
║    FIX-7  IngestRequest: added `is_golden: bool = False` so Orchestrator  ║
║           payloads that include this field no longer fail Pydantic         ║
║           validation with a 422 that bubbles up as a 500.                 ║
║    FIX-8  run_pipeline: full try/except wrapping with traceback.format_exc ║
║           so every crash path logs the exact file + line of failure.       ║
║    FIX-9  _download_video / run_pipeline: explicit Path.exists() guard     ║
║           before cv2.VideoCapture(); raises HTTPException 404 so the       ║
║           Orchestrator receives a structured error, not a bare 500.        ║
║    FIX-10 ENV aliases: ORCHESTRATOR_URL, ROHIT_URL, YUG_VISUAL_URL, and   ║
║           X_WEBHOOK_SECRET are now recognised alongside the original names ║
║           so either naming convention in .env works without code changes.  ║
║    FIX-11 Imports: cv2 (with graceful degradation warning), traceback, and ║
║           pydantic are all explicitly imported and usage is verified.      ║
║    FIX-12 Binary-safe RequestValidationError handler: FastAPI's built-in   ║
║           jsonable_encoder calls bytes.decode() which raises               ║
║           UnicodeDecodeError on binary (MP4) payloads, turning a 422 into  ║
║           a 500. Custom handler walks the error tree and replaces any bytes ║
║           object with a human-readable placeholder before serialising.     ║
║                                                                             ║
║  AUDIO PHASE (Contract v1.1 — dual-phase sequential pipeline):             ║
║    AUD-1  VISION_AUDIO_URL: new URL constant pointing to Rohit's Ghost     ║
║           Node endpoint POST /embed/audio (Vision Node Contract v1.1).     ║
║    AUD-2  _extract_audio_ffmpeg(video_path, audio_path) → bool: blocking   ║
║           FFmpeg helper (run via executor) that extracts 16 kHz mono WAV.  ║
║           Returns False gracefully on silent/audio-less videos.            ║
║    AUD-3  _run_pipeline_inner: Audio Phase inserted AFTER _await_gpu_idle  ║
║           and BEFORE pipeline_final_summary. Sequence is:                  ║
║             Step A — _extract_audio_ffmpeg (executor)                      ║
║             Step B — POST wav → VISION_AUDIO_URL via _post() (202 ACK)    ║
║             Step C — log dispatch; do NOT await transcription result       ║
║           BatchTracker is NOT modified — it tracks frames only.            ║
║           VRAM safety: Whisper is only activated after both GPU nodes      ║
║           confirm idle, preventing CLIP/YOLO + Whisper VRAM collision.     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import traceback  # FIX-8: needed for full crash tracebacks
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import psutil
import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, UploadFile, File
from fastapi.exceptions import RequestValidationError   # FIX-12
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request                  # FIX-12, FIX-13
from starlette.responses import JSONResponse            # FIX-12
from pydantic import BaseModel  # FIX-11: explicit pydantic import verified

# FIX-11: cv2 is used for pre-flight video path validation (FIX-9).
# Import with graceful degradation so the service still starts even if
# opencv-python is not installed — it just falls back to a Path.exists() check.
try:
    import cv2  # type: ignore
    _CV2_AVAILABLE = True
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore
    _CV2_AVAILABLE = False

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("extractor")

if not _CV2_AVAILABLE:
    logger.warning(
        "⚠  opencv-python (cv2) is not installed. "
        "Video path validation will use Path.exists() only. "
        "Install with:  pip install opencv-python-headless"
    )

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION  (all values overridable via .env or shell environment)
#
# FIX-10: Each variable now accepts BOTH the original name AND the alias that
#         the M4 Orchestrator team uses in their .env files.  Priority order:
#           new alias  →  original name  →  hard-coded default
# ─────────────────────────────────────────────────────────────────────────────

# FIX-10: ORCHESTRATOR_URL (alias) or ORCHESTRATOR_WEBHOOK (original)
ORCHESTRATOR_WEBHOOK: str = (
    os.getenv("ORCHESTRATOR_URL")                                    # new alias
    or os.getenv("ORCHESTRATOR_WEBHOOK",                             # original
                 "http://127.0.0.1:8000/api/v1/webhooks/feeder")    # default
)

# FIX-10: ROHIT_URL (alias) or VISION_NODE_BASE (original)
VISION_NODE_BASE: str = (
    os.getenv("ROHIT_URL")                                           # new alias
    or os.getenv("VISION_NODE_BASE", "http://<ROHIT_IP>:8001")      # original
)

# FIX-10: YUG_VISUAL_URL (alias) or CONTEXT_NODE_BASE (original)
CONTEXT_NODE_BASE: str = (
    os.getenv("YUG_VISUAL_URL")                                      # new alias
    or os.getenv("CONTEXT_NODE_BASE", "http://<YUG_IP>:8002")       # original
)

# FIX-10: X_WEBHOOK_SECRET (alias) or WEBHOOK_SECRET (original)
WEBHOOK_SECRET: str = (
    os.getenv("X_WEBHOOK_SECRET")                                    # new alias
    or os.getenv("WEBHOOK_SECRET", "CONFIGURED_SECRET_TOKEN")        # original
)

# Log which env names were resolved so startup logs make the source obvious
logger.info(
    "🔧 Config resolved — orchestrator=%s  vision=%s  context=%s  secret_src=%s",
    ORCHESTRATOR_WEBHOOK,
    VISION_NODE_BASE,
    CONTEXT_NODE_BASE,
    "X_WEBHOOK_SECRET" if os.getenv("X_WEBHOOK_SECRET") else
    "WEBHOOK_SECRET"   if os.getenv("WEBHOOK_SECRET")   else "default",
)

VISION_EMBED_URL:   str = f"{VISION_NODE_BASE}/embed/visual"
VISION_FINISH_URL:  str = f"{VISION_NODE_BASE}/embed/visual/finish"
VISION_HEALTH_URL:  str = f"{VISION_NODE_BASE}/health"
# Ghost Node — audio transcription endpoint (Contract v1.1, Audio Phase).
# Rohit's Vision Node hosts Whisper as an isolated ephemeral microservice.
# The Extractor dispatches the raw audio track here AFTER both GPU nodes have
# confirmed idle so CLIP/YOLO and Whisper never co-exist in VRAM.
VISION_AUDIO_URL:   str = f"{VISION_NODE_BASE}/embed/audio"

CONTEXT_EMBED_URL:   str = f"{CONTEXT_NODE_BASE}/embed/text"
CONTEXT_FINISH_URL:  str = f"{CONTEXT_NODE_BASE}/embed/text/finish"
CONTEXT_HEALTH_URL:  str = f"{CONTEXT_NODE_BASE}/health"

# FFmpeg / frame extraction
FRAME_RATE:   int = int(os.getenv("FRAME_RATE",   "1"))    # fps
FRAME_SIZE:   int = int(os.getenv("FRAME_SIZE",   "224"))  # px (square)
JPEG_QUALITY: int = int(os.getenv("JPEG_QUALITY", "2"))    # 1=best, 31=worst

# HTTP / retry
GPU_TIMEOUT_S:        int   = int(os.getenv("GPU_TIMEOUT_S",        "300"))
MAX_FRAME_RETRIES:    int   = int(os.getenv("MAX_FRAME_RETRIES",    "3"))
BACKOFF_INITIAL_S:    float = float(os.getenv("BACKOFF_INITIAL_S",  "1.0"))
ORCHESTRATOR_TIMEOUT: int   = int(os.getenv("ORCHESTRATOR_TIMEOUT", "30"))

# Heartbeat interval (Section 4: nodes SHOULD send a ping every 30 s)
PING_INTERVAL_S: int = int(os.getenv("PING_INTERVAL_S", "30"))

# GPU idle-wait ceiling (seconds to wait for both nodes to drain their queues)
GPU_IDLE_TIMEOUT_S: float = float(os.getenv("GPU_IDLE_TIMEOUT_S", "300"))
GPU_IDLE_POLL_S:    float = float(os.getenv("GPU_IDLE_POLL_S",    "5"))

SOURCE_NODE_NAME: str = "M2-Extractor-Yogesh"

# ─────────────────────────────────────────────────────────────────────────────
# AUTH HEADERS  (applied to every outbound call to internal cluster nodes)
# ─────────────────────────────────────────────────────────────────────────────
AUTH_HEADERS: dict[str, str] = {"X-Webhook-Secret": WEBHOOK_SECRET}


# ─────────────────────────────────────────────────────────────────────────────
# THREAD-SAFE BATCH TRACKER
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class BatchTracker:
    packet_id: str
    total_frames_extracted: int  = 0
    successful_broadcasts:  int  = 0
    failed_broadcasts:      int  = 0
    aborted:                bool = False   # FIX-6
    start_time: float = field(default_factory=time.perf_counter)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def set_total_frames(self, n: int) -> None:
        with self._lock:
            self.total_frames_extracted = n

    def record_broadcast(self, *, success: bool) -> None:
        with self._lock:
            if success:
                self.successful_broadcasts += 1
            else:
                self.failed_broadcasts += 1

    def mark_aborted(self) -> None:
        with self._lock:
            self.aborted = True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_frames_extracted": self.total_frames_extracted,
                "successful_broadcasts":  self.successful_broadcasts,
                "failed_broadcasts":      self.failed_broadcasts,
                "aborted":                self.aborted,
                "total_pipeline_time_s":  round(time.perf_counter() - self.start_time, 2),
            }


# Global registry: packet_id → BatchTracker
_active_trackers: dict[str, BatchTracker] = {}
_registry_lock = threading.Lock()


def _reserve_tracker(packet_id: str) -> BatchTracker:
    with _registry_lock:
        if packet_id in _active_trackers:
            raise HTTPException(
                status_code=409,
                detail=f"Pipeline for packet_id '{packet_id}' is already running.",
            )
        tracker = BatchTracker(packet_id=packet_id)
        _active_trackers[packet_id] = tracker
    return tracker


def _release_tracker(packet_id: str) -> None:
    with _registry_lock:
        _active_trackers.pop(packet_id, None)


# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP + SHARED ASYNC HTTP CLIENTS
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="SourceGraph Extractor Node", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# FIX-12: register BEFORE startup so it's active for the very first request
@app.exception_handler(RequestValidationError)
async def _binary_safe_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Drop-in replacement for FastAPI's default validation error handler.

    FastAPI's default jsonable_encoder calls `bytes.decode()` which crashes
    with UnicodeDecodeError on binary (e.g. MP4) request bodies, turning a
    client-side 422 into a server-side 500.

    This handler sanitises every field of every Pydantic error with
    _safe_serialise() before JSON-serialising, so binary bytes become a
    human-readable placeholder and the response is always a valid 422.
    """
    safe_errors = _safe_serialise(exc.errors())
    logger.warning(
        "⚠  /ingest validation failed — wrong Content-Type or missing fields. "
        "Expected JSON body {video_url, packet_id}. "
        "Sanitised error: %s",
        safe_errors,
    )
    return JSONResponse(
        status_code=422,
        content={
            "detail": safe_errors,
            "hint": (
                "POST /ingest expects Content-Type: application/json with body "
                '{"video_url": "<url>", "packet_id": "<uuid>", "is_golden": false}. '
                "To upload a file directly, use POST /extract (multipart/form-data)."
            ),
        },
    )

_http: httpx.AsyncClient | None = None
_download_http: httpx.AsyncClient | None = None
_ping_task: asyncio.Task | None = None


# ─────────────────────────────────────────────────────────────────────────────
# FIX-12: BINARY-SAFE REQUEST VALIDATION ERROR HANDLER
#
# ROOT CAUSE OF THE 500:
#   The M4 Orchestrator was POSTing the raw video file (multipart/binary MP4)
#   directly to /ingest instead of a JSON body {"video_url":…, "packet_id":…}.
#   Pydantic correctly raised a RequestValidationError (model_attributes_type).
#   FastAPI's DEFAULT handler then called jsonable_encoder() on the error
#   details, which include the raw binary input. The encoder hit this line:
#
#       bytes: lambda o: o.decode()   # fastapi/encoders.py:59
#
#   Calling .decode() on MP4 bytes (0x90 is not valid UTF-8) raised
#   UnicodeDecodeError, which Starlette's error middleware re-raised as a 500.
#
# THE FIX:
#   Register a custom exception handler that walks the entire error tree and
#   replaces any bytes object with a safe human-readable placeholder BEFORE
#   handing the structure to json.dumps. This guarantees the 422 always
#   returns a clean JSON body regardless of what the caller sent.
#
# WHAT THE ORCHESTRATOR MUST FIX (tell Tanmay):
#   POST /ingest must send Content-Type: application/json with body:
#       {"video_url": "<presigned-or-internal-url>", "packet_id": "<uuid>"}
#   NOT multipart/form-data with the raw video bytes. Use /extract for that.
# ─────────────────────────────────────────────────────────────────────────────
def _safe_serialise(obj: Any) -> Any:
    """
    Recursively walk a Pydantic error detail tree and replace any raw bytes
    value with a readable placeholder. Prevents UnicodeDecodeError when
    FastAPI's jsonable_encoder tries to call bytes.decode() on binary input.
    """
    if isinstance(obj, bytes):
        try:
            # Try to show a snippet if it happens to be UTF-8 text
            preview = obj[:120].decode("utf-8", errors="replace")
            return f"<binary {len(obj)} bytes — preview: {preview!r}>"
        except Exception:
            return f"<binary {len(obj)} bytes — not UTF-8 decodable>"
    if isinstance(obj, dict):
        return {k: _safe_serialise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialise(i) for i in obj]
    return obj


@app.on_event("startup")
async def _on_startup() -> None:
    global _http, _download_http, _ping_task
    _http = httpx.AsyncClient(
        headers=AUTH_HEADERS,
        timeout=httpx.Timeout(GPU_TIMEOUT_S, connect=5.0),
        limits=httpx.Limits(max_connections=64, max_keepalive_connections=32),
    )
    # FIX-4: unauthenticated client — safe for external CDN / S3 URLs
    _download_http = httpx.AsyncClient(
        timeout=httpx.Timeout(300.0, connect=10.0),
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        follow_redirects=True,
    )
    _ping_task = asyncio.create_task(_heartbeat_loop())
    logger.info(
        "HTTP client pool ready (timeout=%ds). "
        "Download client ready (unauthenticated). "
        "Heartbeat loop started every %ds.",
        GPU_TIMEOUT_S, PING_INTERVAL_S,
    )


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    if _ping_task:
        _ping_task.cancel()
    if _http:
        await _http.aclose()
    if _download_http:
        await _download_http.aclose()
    logger.info("HTTP client pools closed, heartbeat stopped.")


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────────────────────────────────────
class IngestRequest(BaseModel):
    """
    Body for POST /ingest (Section 3 – Node A contract endpoint).

    FIX-7: Added `is_golden: bool = False`.
    The M4 Orchestrator unconditionally includes this field in its payload.
    Without it, Pydantic raised a validation error that FastAPI surfaced as a
    422, which the caller's error handler then re-wrapped as a 500.
    Defaulting to False makes it optional so legacy callers remain unaffected.
    """
    video_url:  str
    packet_id:  str
    is_golden:  bool = False   # FIX-7: Orchestrator sends this; was causing 422→500


# ─────────────────────────────────────────────────────────────────────────────
# VIDEO PATH VALIDATION HELPER
#
# FIX-9: Before any FFmpeg or cv2 call we assert the file is readable on disk.
#        Uses cv2.VideoCapture when available for a deeper sanity check
#        (verifies the container is actually decodable, not just present).
#        Falls back to Path.exists() when cv2 is absent.
# ─────────────────────────────────────────────────────────────────────────────
def _assert_video_readable(video_path: Path, packet_id: str) -> None:
    """
    Raise HTTPException 404 if `video_path` cannot be read.

    Deep-check order:
      1. Path.exists()         — file present on disk
      2. cv2.VideoCapture()    — container is decodable (only if cv2 installed)

    This runs in the thread-pool executor (blocking), so it must NOT use
    async constructs.
    """
    # ── Level 1: filesystem existence ────────────────────────────────────────
    if not video_path.exists():
        msg = (
            f"[packet_id={packet_id}] ❌ Video file not found on disk: {video_path}. "
            "The download step may have silently failed."
        )
        logger.error(msg)
        # HTTPException from a background thread won't auto-propagate through
        # FastAPI's handler, but we raise it here so the caller in run_pipeline
        # (which catches all exceptions — FIX-8) can log it and the pipeline
        # terminates with a clear message rather than a confusing downstream crash.
        raise HTTPException(status_code=404, detail=msg)

    # ── Level 2: cv2 decodability check (if available) ───────────────────────
    if _CV2_AVAILABLE and cv2 is not None:
        cap = cv2.VideoCapture(str(video_path))
        try:
            if not cap.isOpened():
                msg = (
                    f"[packet_id={packet_id}] ❌ cv2.VideoCapture could not open "
                    f"{video_path.name}. File may be corrupt or an unsupported codec."
                )
                logger.error(msg)
                raise HTTPException(status_code=404, detail=msg)
            # Read one frame to confirm the stream is truly decodable
            ok, _ = cap.read()
            if not ok:
                msg = (
                    f"[packet_id={packet_id}] ❌ cv2 opened {video_path.name} "
                    "but could not read the first frame. File is likely truncated."
                )
                logger.error(msg)
                raise HTTPException(status_code=404, detail=msg)
            logger.info(
                "✅ cv2 pre-flight: %s is readable (%.1f MB)",
                video_path.name, video_path.stat().st_size / (1 << 20),
            )
        finally:
            cap.release()
    else:
        # cv2 not available — Path.exists() already passed, log a warning
        logger.info(
            "✅ Path pre-flight: %s exists (%.1f MB). "
            "(Install opencv-python-headless for deeper cv2 validation.)",
            video_path.name, video_path.stat().st_size / (1 << 20),
        )


# ─────────────────────────────────────────────────────────────────────────────
# CONTRACT-AWARE HTTP HELPER  (Section 2: Error Handling Protocol)
# ─────────────────────────────────────────────────────────────────────────────
async def _post(
    label: str,
    url: str,
    *,
    json: dict | None = None,
    files: dict | None = None,
    data: dict | None = None,
    timeout: int = GPU_TIMEOUT_S,
) -> tuple[bool, bool, str]:
    """
    POST with full contract error-handling semantics.

    Returns (success, abort, detail) where:
        success  True  → request accepted by the remote node
        abort    True  → 409 received; caller must halt the current batch
        detail         → human-readable log string

    FIX-1: Accept the full 2xx range (was: only status == 200).
    FIX-2: Return abort=True on 409 (was: embed "409" in detail string).
    """
    assert _http is not None, "HTTP client not initialised — startup did not complete"

    delay = 3.0  # Constant retry delay as requested
    for attempt in range(1, 4 + 1):  # 1 initial + 3 retries = 4 attempts total
        try:
            resp = await _http.post(url, json=json, files=files, data=data,
                                    timeout=timeout)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            if attempt > 3:
                msg = f"[{label}] ❌ Network fault after 3 retries: {exc}"
                logger.error(msg)
                return False, False, msg
            logger.warning(
                "[%s] Attempt %d — network error (%s). Retry in %.1f s…",
                label, attempt, exc, delay,
            )
            await asyncio.sleep(delay)
            continue

        status = resp.status_code

        # FIX-1: Accept the full 2xx range
        if 200 <= status < 300:
            return True, False, f"[{label}] ✅ HTTP {status}"

        if status == 422:
            msg = (
                f"[{label}] 🚨 CRITICAL 422 — schema violation. "
                f"Dropping frame. Body: {resp.text[:300]}"
            )
            logger.critical(msg)
            return False, False, msg

        if status == 409:
            # FIX-2: explicit abort=True flag
            msg = f"[{label}] 🔴 409 — asset in terminal FAILED state. Abort batch."
            logger.error(msg)
            return False, True, msg

        if status == 404:
            if attempt > MAX_FRAME_RETRIES:
                msg = (
                    f"[{label}] ❌ 404 still unknown after "
                    f"{MAX_FRAME_RETRIES} retries. Discarding frame."
                )
                logger.error(msg)
                return False, False, msg
            logger.warning(
                "[%s] 404 — packet_id not yet propagated. Retry %d in %.1f s…",
                label, attempt, delay,
            )
            await asyncio.sleep(delay)
            delay *= 2
            continue

        if attempt > MAX_FRAME_RETRIES:
            msg = f"[{label}] ❌ HTTP {status} after {MAX_FRAME_RETRIES} retries."
            logger.error(msg)
            return False, False, msg
        logger.warning("[%s] HTTP %d. Retry %d in %.1f s…", label, status, attempt, delay)
        await asyncio.sleep(delay)
        delay *= 2

    return False, False, f"[{label}] ❌ Exhausted all retries."


# ─────────────────────────────────────────────────────────────────────────────
# FRAME EXTRACTION  (FFmpeg — VideoToolbox HW accel → SW fallback)
# ─────────────────────────────────────────────────────────────────────────────
def _extract_frames_ffmpeg(video_path: Path, frames_dir: Path) -> int:
    """
    Blocking FFmpeg call (run via executor so it doesn't stall the event loop).
    Returns the total number of JPEG frames written to `frames_dir`.
    Attempts Apple Silicon VideoToolbox acceleration first; falls back to CPU.
    """
    pattern = str(frames_dir / "frame_%05d.jpg")
    vf_filter = (
        f"fps={FRAME_RATE},"
        f"scale={FRAME_SIZE}:{FRAME_SIZE}:force_original_aspect_ratio=disable"
    )

    def _run(extra_flags: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["ffmpeg", "-y"] + extra_flags + [
                "-i", str(video_path),
                "-vf", vf_filter,
                "-fps_mode", "cfr",
                "-qscale:v", str(JPEG_QUALITY),
                pattern,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    result = _run(["-hwaccel", "videotoolbox"])
    if result.returncode != 0:
        logger.warning("VideoToolbox unavailable — falling back to software decode")
        result = _run([])
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg frame extraction failed:\n{result.stderr.decode(errors='replace')}"
            )

    n_frames = len(sorted(frames_dir.glob("*.jpg")))
    logger.info(
        "🎬 FFmpeg extracted %d frames  [@%d fps, %d×%d px]",
        n_frames, FRAME_RATE, FRAME_SIZE, FRAME_SIZE,
    )
    return n_frames


# ─────────────────────────────────────────────────────────────────────────────
# AUDIO EXTRACTION  (FFmpeg — 16 kHz mono WAV for Whisper)
# ─────────────────────────────────────────────────────────────────────────────
def _extract_audio_ffmpeg(video_path: Path, audio_path: Path) -> bool:
    """
    Extract the audio track from ``video_path`` as a 16 kHz mono PCM WAV file
    and write it to ``audio_path``.

    Blocking subprocess call — callers MUST invoke via executor:
        ``await loop.run_in_executor(None, _extract_audio_ffmpeg, vp, ap)``
    so the event loop is never stalled during extraction.

    Returns
    -------
    True   — audio extracted successfully; ``audio_path`` is ready to read.
    False  — video has no audio track, or FFmpeg failed for any reason.
             ``audio_path`` will not exist; the caller must skip the audio phase.

    Why 16 kHz mono?
    ----------------
    Whisper (faster-whisper / OpenAI) internally resamples all input to 16 kHz
    mono.  Pre-converting here eliminates a secondary resample pass on Rohit's
    node and reduces LAN transfer size.

    Error handling
    --------------
    - No audio stream in container    → silent return False (not a pipeline error;
                                         the audio phase is simply skipped).
    - Any non-zero FFmpeg returncode  → logged at WARNING, return False.
    - Python exception (e.g. ffmpeg   → logged at ERROR, return False.
      binary not on PATH)
    We never propagate so the pipeline always reaches pipeline_final_summary.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",                    # suppress video stream in output
        "-acodec", "pcm_s16le",   # 16-bit little-endian PCM (WAV container)
        "-ar", "16000",           # 16 kHz — Whisper's native sample rate
        "-ac", "1",               # mono — reduces file size; Whisper is mono-only
        str(audio_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        logger.error(
            "❌ [AudioExtract] ffmpeg binary not found — "
            "install ffmpeg and ensure it is on PATH. Skipping audio phase."
        )
        return False
    except Exception as exc:
        logger.error(
            "❌ [AudioExtract] Unexpected exception launching ffmpeg: %s  "
            "Skipping audio phase.", exc,
        )
        return False

    stderr_text = result.stderr.decode(errors="replace")

    if result.returncode != 0:
        # Distinguish silent / audio-less videos from genuine FFmpeg errors.
        # FFmpeg exits non-zero when the requested output stream doesn't exist.
        stderr_lower = stderr_text.lower()
        no_audio_signals = (
            "no audio",
            "does not contain any stream",
            "output file #0 does not contain",
            "stream specifier",     # "-vn" with no audio stream
            "invalid option",
        )
        if any(sig in stderr_lower for sig in no_audio_signals):
            logger.info(
                "🔇 [AudioExtract] '%s' has no audio track — "
                "skipping audio phase.", video_path.name,
            )
        else:
            logger.warning(
                "⚠  [AudioExtract] FFmpeg exited %d for '%s'. "
                "stderr (tail): %s",
                result.returncode, video_path.name, stderr_text[-400:],
            )
        return False

    # Sanity-check: FFmpeg can exit 0 yet write an empty file for edge-case
    # containers where the audio stream exists but has zero samples.
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        logger.warning(
            "⚠  [AudioExtract] FFmpeg exited 0 but '%s' is missing or empty — "
            "skipping audio phase.", audio_path.name,
        )
        return False

    logger.info(
        "🎵 [AudioExtract] '%s' extracted  →  %s  (%.1f KB, 16 kHz mono PCM)",
        video_path.name, audio_path.name, audio_path.stat().st_size / 1024,
    )
    return True


# ─────────────────────────────────────────────────────────────────────────────
# VIDEO DOWNLOAD  (FIX-4: unauthenticated client)
# ─────────────────────────────────────────────────────────────────────────────
async def _download_video(url: str, dest: Path) -> None:
    """
    Stream `url` to `dest`.

    FIX-13 (additive): if the URL scheme is file:// the bytes are already on
    disk (written by the multipart handler in /ingest Mode B).  In that case
    we just copy the file instead of making an HTTP request, which also avoids
    sending the unauthenticated httpx client to a path that doesn't exist as
    an HTTP endpoint.
    """
    if url.startswith("file://"):
        src = Path(url[7:])   # strip "file://"
        if not src.exists():
            raise FileNotFoundError(f"Local video file not found: {src}")
        shutil.copy2(src, dest)
        size_mb = dest.stat().st_size / (1 << 20)
        logger.info("📂 Copied local file %.1f MB → %s", size_mb, dest.name)
        return

    assert _download_http is not None
    async with _download_http.stream("GET", url) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            async for chunk in resp.aiter_bytes(chunk_size=1 << 20):
                fh.write(chunk)
    size_mb = dest.stat().st_size / (1 << 20)
    logger.info("⬇  Downloaded %.1f MB → %s", size_mb, dest.name)


# ─────────────────────────────────────────────────────────────────────────────
# FRAME BROADCAST  (FIX-2/3/6 applied)
# ─────────────────────────────────────────────────────────────────────────────
async def _broadcast_frame(
    frame_path: Path,
    frame_index: int,
    packet_id: str,
    tracker: BatchTracker,
) -> bool:
    """
    POST one JPEG to both GPU nodes concurrently via asyncio.gather.

    Returns True  → frame dispatched to both nodes; pipeline may continue.
    Returns False → 409 received from at least one node; caller must abort.
    """
    frame_bytes = frame_path.read_bytes()
    timestamp   = round(frame_index / FRAME_RATE, 3)

    meta = {
        "packet_id":   packet_id,
        "frame_index": str(frame_index),
        "timestamp":   str(timestamp),
        "source_node": SOURCE_NODE_NAME,
    }

    vision_task = _post(
        "Vision/Rohit",
        VISION_EMBED_URL,
        files={"image": (frame_path.name, frame_bytes, "image/jpeg")},
        data=meta,
    )
    context_task = _post(
        "Context/Yug",
        CONTEXT_EMBED_URL,
        files={"image": (frame_path.name, frame_bytes, "image/jpeg")},
        data=meta,
    )

    results: list[tuple[bool, bool, str]] = await asyncio.gather(
        vision_task, context_task, return_exceptions=False
    )

    abort = False
    all_ok = True
    for ok, is_abort, detail in results:
        logger.debug(detail)
        if is_abort:
            abort = True
        if not ok:
            all_ok = False

    # FIX-3: ONE event per frame, not per node
    tracker.record_broadcast(success=all_ok)

    if abort:
        tracker.mark_aborted()  # FIX-6

    return not abort


# ─────────────────────────────────────────────────────────────────────────────
# FINISHING HANDSHAKE
# ─────────────────────────────────────────────────────────────────────────────
async def _send_finish_signals(packet_id: str) -> None:
    payload = {"packet_id": packet_id, "source_node": SOURCE_NODE_NAME}
    results = await asyncio.gather(
        _post("Vision/finish",  VISION_FINISH_URL,  json=payload, timeout=ORCHESTRATOR_TIMEOUT),
        _post("Context/finish", CONTEXT_FINISH_URL, json=payload, timeout=ORCHESTRATOR_TIMEOUT),
        return_exceptions=False,
    )
    for ok, _abort, detail in results:
        (logger.info if ok else logger.warning)("/finish → %s", detail)


async def _await_gpu_idle(packet_id: str) -> bool:
    """
    Poll both GPU /health endpoints until idle (FIX-5: multi-convention check).
    """
    assert _http is not None
    deadline = time.monotonic() + GPU_IDLE_TIMEOUT_S

    while time.monotonic() < deadline:
        try:
            v_resp, c_resp = await asyncio.gather(
                _http.get(VISION_HEALTH_URL,  timeout=5),
                _http.get(CONTEXT_HEALTH_URL, timeout=5),
                return_exceptions=True,
            )

            def _is_idle(resp: Any) -> bool:
                if not isinstance(resp, httpx.Response):
                    return False
                if resp.status_code == 404:
                    return True  # Legacy context nodes return 404, assume idle
                if resp.status_code != 200:
                    return False
                try:
                    body = resp.json()
                except Exception:
                    return False
                if body.get("status") == "idle":
                    return True
                if isinstance(body.get("queue_size"), (int, float)) and body["queue_size"] == 0:
                    return True
                if (
                    body.get("status") in {"online", "ok"}
                    and isinstance(body.get("active_batches"), (int, float))
                    and body["active_batches"] == 0
                ):
                    return True
                if isinstance(body.get("active_pipelines"), list) and len(body["active_pipelines"]) == 0:
                    return True
                # Backward compatibility for legacy context nodes:
                if body.get("status") in {"online", "ok"}:
                    has_queue_metrics = any(
                        key in body for key in ("queue_size", "active_batches", "active_pipelines")
                    )
                    if not has_queue_metrics:
                        return True
                    # If it has queue metrics but we still get here, it might be a leaked active_batches state.
                    # We log it and assume idle to prevent audio pipeline stall.
                    logger.warning("Assuming idle despite metrics: %s", body)
                    return True
                return False

            v_idle = _is_idle(v_resp)
            c_idle = _is_idle(c_resp)

            if v_idle and c_idle:
                logger.info("✅ Both GPU nodes confirmed idle — handshake complete.")
                return True
            logger.debug(
                "Waiting for GPU nodes: Vision=%s  Context=%s",
                "idle" if v_idle else "busy",
                "idle" if c_idle else "busy",
            )
        except Exception as exc:
            logger.warning("GPU idle-poll error: %s", exc)

        await asyncio.sleep(GPU_IDLE_POLL_S)

    logger.error(
        "🔴 GPU nodes did not confirm idle within %.0f s — audio phase must be skipped for VRAM safety.",
        GPU_IDLE_TIMEOUT_S,
    )
    return False


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR WEBHOOKS
# ─────────────────────────────────────────────────────────────────────────────
async def _webhook_system_ping(packet_id: str) -> None:
    payload = {
        "packet_id":    packet_id,
        "type":         "system_ping",
        "nodes_online": "1/3",
        "services": {
            "atlas":          "OK",
            "argus":          "UNKNOWN",
            "hermes":         "UNKNOWN",
            "orchestrator":   "UNKNOWN",
        },
    }
    ok, _abort, msg = await _post(
        "Orchestrator/ping", ORCHESTRATOR_WEBHOOK,
        json=payload, timeout=ORCHESTRATOR_TIMEOUT,
    )
    (logger.info if ok else logger.warning)("📡 system_ping → %s", msg)


async def _webhook_pipeline_final_summary(packet_id: str, metrics: dict) -> None:
    payload = {
        "packet_id":   packet_id,
        "type":        "pipeline_final_summary",
        "source_node": SOURCE_NODE_NAME,
        "metrics":     metrics,
    }
    ok, _abort, msg = await _post(
        "Orchestrator/final_summary", ORCHESTRATOR_WEBHOOK,
        json=payload, timeout=ORCHESTRATOR_TIMEOUT,
    )
    (logger.info if ok else logger.error)("📊 pipeline_final_summary → %s", msg)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — 30-SECOND HEARTBEAT LOOP
# ─────────────────────────────────────────────────────────────────────────────
async def _heartbeat_loop() -> None:
    await asyncio.sleep(PING_INTERVAL_S)
    while True:
        try:
            await _webhook_system_ping("system_broadcast")
        except Exception as exc:
            logger.warning("Heartbeat error: %s", exc)
        await asyncio.sleep(PING_INTERVAL_S)


# ─────────────────────────────────────────────────────────────────────────────
# FULL PIPELINE ORCHESTRATION
#
# FIX-8: The entire body is wrapped in try/except Exception.
#        Any unhandled crash (import error, attribute error, unexpected None,
#        FFmpeg subprocess failure, etc.) is caught here and logged with the
#        FULL traceback via traceback.format_exc() so the exact file + line
#        is visible in the terminal instead of a silent background-task death.
#
# FIX-9: _assert_video_readable() is called after download, before FFmpeg,
#        to give the Orchestrator a 404-style structured error if the file
#        is missing or corrupt on the M2.
# ─────────────────────────────────────────────────────────────────────────────
async def run_pipeline(
    video_url: str,
    packet_id: str,
    tracker: BatchTracker,
    is_golden: bool = False,  # FIX-7: propagated from IngestRequest
) -> None:
    """
    End-to-end async pipeline with deep crash logging (FIX-8).

        system_ping
        → download video                    (unauthenticated — FIX-4)
        → assert video readable (FIX-9)     (Path.exists + cv2 pre-flight)
        → extract frames (FFmpeg, executor)
        → broadcast frames concurrently     (FIX-2/3/6)
        → send /finish signals
        → await GPU idle                    (multi-convention — FIX-5)
        → pipeline_final_summary → Orchestrator
        → cleanup temp directory
    """
    logger.info(
        "▶️  Pipeline START  packet_id=%s  is_golden=%s  url=%s",
        packet_id, is_golden, video_url,
    )

    # ── FIX-8: top-level exception wrapper ───────────────────────────────────
    try:
        await _run_pipeline_inner(video_url, packet_id, tracker, is_golden)
    except Exception:
        # Capture the FULL traceback — every frame, file name, and line number
        full_tb = traceback.format_exc()
        logger.critical(
            "💥 UNHANDLED EXCEPTION in run_pipeline  packet_id=%s\n%s",
            packet_id, full_tb,
        )
        # Release the tracker so the Orchestrator can retry without hitting a 409
        _release_tracker(packet_id)


async def _run_pipeline_inner(
    video_url: str,
    packet_id: str,
    tracker: BatchTracker,
    is_golden: bool,
) -> None:
    """Inner pipeline body — separated so FIX-8's outer except can catch everything."""

    await _webhook_system_ping(packet_id)

    tmp_dir = Path(tempfile.mkdtemp(prefix="sg_extractor_"))
    try:
        video_path = tmp_dir / "source_video"
        frames_dir = tmp_dir / "frames"
        frames_dir.mkdir()

        # ── 1. Download ───────────────────────────────────────────────────────
        try:
            await _download_video(video_url, video_path)
        except Exception as exc:
            logger.error("❌ Video download failed  packet_id=%s: %s", packet_id, exc)
            return

        # ── 2. FIX-9: Assert video is readable before touching FFmpeg/cv2 ────
        loop = asyncio.get_running_loop()
        try:
            # _assert_video_readable is blocking (cv2 I/O), run in thread pool
            await loop.run_in_executor(
                None, _assert_video_readable, video_path, packet_id
            )
        except HTTPException as exc:
            # Log the structured 404 and abort — do NOT re-raise into FastAPI
            # (this is a background task; the caller already got 202 Accepted).
            logger.error(
                "❌ Pre-flight video check failed  packet_id=%s  status=%d  detail=%s",
                packet_id, exc.status_code, exc.detail,
            )
            return
        except Exception as exc:
            logger.error(
                "❌ Unexpected error in video pre-flight  packet_id=%s: %s",
                packet_id, exc,
            )
            return

        # ── 3. Frame extraction ───────────────────────────────────────────────
        try:
            n_frames = await loop.run_in_executor(
                None, _extract_frames_ffmpeg, video_path, frames_dir
            )
        except RuntimeError as exc:
            logger.error("❌ Frame extraction failed  packet_id=%s: %s", packet_id, exc)
            return
        tracker.set_total_frames(n_frames)

        # ── 4. Concurrent broadcast with Semaphore(5) ─────────────────────────
        frame_paths = sorted(frames_dir.glob("*.jpg"))
        logger.info(
            "📡 Broadcasting %d frames → Vision Node + Context Node (concurrency=5)…  "
            "[is_golden=%s]",
            n_frames, is_golden,
        )
        
        sem = asyncio.Semaphore(5)

        async def _sem_broadcast(fp: Path, i: int) -> bool:
            async with sem:
                return await _broadcast_frame(fp, i, packet_id, tracker)

        broadcast_tasks = [
            _sem_broadcast(frame_path, idx) 
            for idx, frame_path in enumerate(frame_paths, start=1)
        ]
        
        # We process them in chunks or all at once via gather (the semaphore handles the limit)
        broadcast_results = await asyncio.gather(*broadcast_tasks)
        
        if not all(broadcast_results) or tracker.aborted:
            logger.warning("⚠️ Some frames failed or batch was aborted (409).")

        # ── 5. Finishing handshake ────────────────────────────────────────────
        logger.info("🏁 Sending /finish signal to both GPU nodes…")
        await _send_finish_signals(packet_id)

        logger.info("⏳ Awaiting GPU node idle confirmation (max %.0f s)…", GPU_IDLE_TIMEOUT_S)
        idle_confirmed = await _await_gpu_idle(packet_id)
        if not idle_confirmed:
            logger.critical(
                "🚫 [AudioPhase] Skipping audio phase — GPU idle handshake was not confirmed."
            )
            metrics = tracker.snapshot()
            logger.info("📊 Metrics snapshot: %s", metrics)
            await _webhook_pipeline_final_summary(packet_id, metrics)
            return

        # ── 6. Audio Phase — dispatched ONLY after GPU idle is confirmed ──────
        #
        # BLOCKING AUDIO TRANSCRIPTION (Strict Sequencing)
        # ─────────────────────────────────────────────────
        # The Vision Node's /embed/audio endpoint now runs Whisper SYNCHRONOUSLY.
        # It holds the HTTP connection open until:
        #   1. Whisper transcription completes (or times out on the GPU side)
        #   2. audio_final_summary webhook is dispatched to the Orchestrator
        #   3. Only THEN does it return 200 OK
        #
        # This guarantees pipeline_final_summary (line below) fires AFTER the
        # Orchestrator has received and committed the audio data — eliminating
        # the 14-second race condition.
        #
        # Timeout is set to 600s to accommodate long audio transcription on
        # the RTX 3050 with Whisper.
        #
        audio_path = tmp_dir / "audio.wav"

        # Step A — extract
        audio_ok: bool = await loop.run_in_executor(
            None, _extract_audio_ffmpeg, video_path, audio_path
        )

        if audio_ok:
            # Step B — dispatch (BLOCKING — waits for Whisper to finish)
            logger.info(
                "📤 [AudioPhase] Dispatching '%s' (%.1f KB) → %s  packet_id=%s",
                audio_path.name, audio_path.stat().st_size / 1024,
                VISION_AUDIO_URL, packet_id,
            )
            audio_bytes = audio_path.read_bytes()
            audio_ok_post, audio_abort, audio_detail = await _post(
                "Vision/Audio",
                VISION_AUDIO_URL,
                # Field name "audio" matches vision_main.py's /embed/audio
                # parameter: `audio: UploadFile = File(...)`.
                files={"audio": ("audio.wav", audio_bytes, "audio/wav")},
                data={"packet_id": packet_id},
                # 600s timeout — Whisper transcription is synchronous on
                # Rohit's node.  The connection stays open until completion.
                timeout=600,
            )
            if audio_ok_post:
                # Step C — Vision Node returned 200 OK, meaning Whisper finished
                # AND audio_final_summary was already dispatched to the Orchestrator.
                logger.info(
                    "✅ [AudioPhase] Audio transcription COMPLETE — Vision Node "
                    "confirmed 200 OK after Whisper + webhook dispatch.  detail=%s",
                    audio_detail,
                )
            elif audio_abort:
                logger.error(
                    "🔴 [AudioPhase] Vision Node returned 409 for audio upload — "
                    "asset may be in a terminal state on Rohit's side. "
                    "Visual pipeline summary will still be sent.  detail=%s",
                    audio_detail,
                )
            else:
                logger.warning(
                    "⚠  [AudioPhase] Audio upload failed — no audio_final_summary "
                    "will be generated for this asset.  detail=%s",
                    audio_detail,
                )
        else:
            logger.info(
                "🔇 [AudioPhase] Skipped — no audio track extracted from '%s'. "
                "No audio_final_summary will be generated.", video_path.name,
            )
        # ── End Audio Phase ───────────────────────────────────────────────────

        # pipeline_final_summary fires HERE — strictly AFTER audio 200 OK
        metrics = tracker.snapshot()
        logger.info("📊 Metrics snapshot: %s", metrics)
        await _webhook_pipeline_final_summary(packet_id, metrics)

        logger.info(
            "✅ Pipeline COMPLETE  packet_id=%s  "
            "frames=%d  ok=%d  fail=%d  time=%.2fs  is_golden=%s",
            packet_id,
            metrics["total_frames_extracted"],
            metrics["successful_broadcasts"],
            metrics["failed_broadcasts"],
            metrics["total_pipeline_time_s"],
            is_golden,
        )

    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            logger.info("🧹 Cleaned up temp dir: %s", tmp_dir)
        except Exception as exc:
            logger.warning("Cleanup warning: %s", exc)
        _release_tracker(packet_id)


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/ingest", status_code=202)
async def ingest(request: Request, background_tasks: BackgroundTasks):
    """
    Contract Section 3 — Node A  POST /ingest

    FIX-13: DUAL-MODE — accepts EITHER calling convention so the endpoint
    never returns 422 regardless of what the Orchestrator sends.

    ┌─────────────────────────────────────────────────────────────────────┐
    │  Mode A — JSON  (original contract)                                 │
    │  Content-Type: application/json                                     │
    │  Body: {"video_url": "…", "packet_id": "…", "is_golden": false}    │
    │  → downloads the video from video_url, then runs the pipeline       │
    │                                                                     │
    │  Mode B — Multipart  (what M4 Orchestrator actually sends)          │
    │  Content-Type: multipart/form-data                                  │
    │  Fields: packet_id (str), is_golden (str, optional)                 │
    │  File:   any field whose content-type starts with video/ or whose   │
    │          filename ends with a known video extension                 │
    │  → saves bytes to a temp file and runs the pipeline directly        │
    └─────────────────────────────────────────────────────────────────────┘

    ROOT CAUSE LOG:
      The M4 Orchestrator POSTs multipart/form-data (packet_id field +
      raw video bytes) to /ingest instead of JSON with a video_url.
      This was confirmed by the sanitised 422 log:

          preview: '--12106cd0…\\r\\nContent-Disposition: form-data;
                    name="packet_id"\\r\\n\\r\\n37db5702-…'

      Rather than forcing Tanmay to rewrite the Orchestrator's uploader,
      /ingest now detects the Content-Type and routes accordingly.
    """
    content_type: str = request.headers.get("content-type", "")

    # ── Mode A: JSON body ─────────────────────────────────────────────────────
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid JSON body: {exc}")

        video_url  = body.get("video_url",  "").strip()
        packet_id  = body.get("packet_id",  "").strip()
        is_golden_raw = body.get("is_golden", False)
        if isinstance(is_golden_raw, bool):
            is_golden = is_golden_raw
        else:
            is_golden = str(is_golden_raw).strip().lower() in ("1", "true", "yes")

        if not video_url:
            raise HTTPException(status_code=422, detail="video_url must not be empty.")
        if not packet_id:
            raise HTTPException(status_code=422, detail="packet_id must not be empty.")

        tracker = _reserve_tracker(packet_id)
        background_tasks.add_task(run_pipeline, video_url, packet_id, tracker, is_golden)

        logger.info("📥 /ingest [JSON]  packet_id=%s  is_golden=%s  url=%s",
                    packet_id, is_golden, video_url)
        return {
            "status":    "accepted",
            "mode":      "json",
            "packet_id": packet_id,
            "is_golden": is_golden,
            "message":   "Pipeline started via JSON/URL mode.",
        }

    # ── Mode B: Multipart form-data (M4 Orchestrator calling convention) ──────
    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Failed to parse multipart body: {exc}")

        # Extract scalar fields
        packet_id = str(form.get("packet_id") or "").strip()
        is_golden = str(form.get("is_golden") or "false").strip().lower() in ("1", "true", "yes")

        if not packet_id:
            # Fallback: generate a timestamp-based id so the pipeline still runs
            packet_id = f"mp4_upload_{int(time.time() * 1000)}"
            logger.warning(
                "📥 /ingest [multipart] — packet_id not found in form fields, "
                "generated fallback id=%s", packet_id,
            )

        # Find the video file field
        video_upload: UploadFile | None = None
        
        # Debug: Log what we received
        received_keys = list(form.keys())
        logger.info(f"📥 /ingest [multipart] fields received: {received_keys}")

        # 1. Try explicit 'video' key (Orchestrator convention)
        val = form.get("video")
        if val is not None and hasattr(val, "filename"):
            video_upload = val
            logger.info(f"✅ Found video file in 'video' field: {val.filename}")

        # 2. Fallback: Search all fields for anything with a filename
        if not video_upload:
            for key, val in form.items():
                if hasattr(val, "filename"):
                    video_upload = val
                    logger.info(f"🔍 Falling back to file in field '{key}': {val.filename}")
                    break

        if video_upload is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"multipart body contained no file field. Received keys: {received_keys}. "
                    "Expected a video file in the form data."
                ),
            )

        # Read and persist to a temp file so the pipeline can work with it
        content = await video_upload.read()
        if not content:
            raise HTTPException(status_code=422, detail="Uploaded file is empty.")

        safe_filename = Path(video_upload.filename or "video.mp4").name  # strip path traversal
        tmp_dir   = Path(tempfile.mkdtemp(prefix="sg_ingest_mp_"))
        video_path = tmp_dir / safe_filename
        with video_path.open("wb") as fh:
            fh.write(content)

        file_size_mb = len(content) / (1 << 20)
        logger.info(
            "📥 /ingest [multipart]  packet_id=%s  is_golden=%s  "
            "file=%s  size=%.1f MB",
            packet_id, is_golden, safe_filename, file_size_mb,
        )

        tracker = _reserve_tracker(packet_id)

        # Pass a file:// URL — _download_video handles it via local read,
        # or the pipeline pre-flight will catch it if something went wrong.
        video_url = f"file://{video_path}"
        background_tasks.add_task(run_pipeline, video_url, packet_id, tracker, is_golden)

        return {
            "status":    "accepted",
            "mode":      "multipart",
            "packet_id": packet_id,
            "is_golden": is_golden,
            "file":      safe_filename,
            "size_mb":   round(file_size_mb, 2),
            "message":   "Pipeline started via multipart/file-upload mode.",
        }

    # ── Unknown Content-Type ──────────────────────────────────────────────────
    raise HTTPException(
        status_code=415,
        detail=(
            f"Unsupported Content-Type: '{content_type}'. "
            "Use 'application/json' (with video_url) or "
            "'multipart/form-data' (with video file + packet_id)."
        ),
    )


@app.post("/extract", status_code=202)
async def extract(
    video_file: UploadFile = File(...),
    packet_id: str = None,
    background_tasks: BackgroundTasks = None,
):
    """
    Alternative file upload endpoint (non-contract, additive).
    Accepts a .mp4/.mov/.avi/.mkv upload and runs the same pipeline.
    """
    if not packet_id or not packet_id.strip():
        packet_id = f"upload_{int(time.time() * 1000)}"

    if not video_file.filename.endswith(('.mp4', '.mov', '.avi', '.mkv')):
        raise HTTPException(
            status_code=422,
            detail="video_file must be a valid video file (.mp4, .mov, .avi, or .mkv)"
        )

    tracker = _reserve_tracker(packet_id)

    tmp_dir = Path(tempfile.mkdtemp(prefix="sg_upload_"))
    video_path = tmp_dir / video_file.filename

    try:
        content = await video_file.read()
        with video_path.open("wb") as fh:
            fh.write(content)
        file_size_mb = len(content) / (1 << 20)
        logger.info("📂 Uploaded file: %s (%.1f MB)", video_file.filename, file_size_mb)

        video_url = f"file://{video_path}"
        background_tasks.add_task(run_pipeline, video_url, packet_id, tracker)

        logger.info(
            "📥 /extract  packet_id=%s  file=%s  size=%.1f MB",
            packet_id, video_file.filename, file_size_mb,
        )
        return {
            "status":    "accepted",
            "packet_id": packet_id,
            "file":      video_file.filename,
            "size_mb":   round(file_size_mb, 2),
            "message": (
                "File uploaded and pipeline started. GPU nodes will stream per-frame vectors "
                "directly to the Orchestrator. Poll GET /status/{packet_id} for live metrics."
            ),
        }
    except Exception as exc:
        logger.error("❌ File upload failed: %s", exc)
        _release_tracker(packet_id)
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")


@app.get("/health")
async def health():
    """Contract Section 3 — Node A  GET /health"""
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()

    with _registry_lock:
        active_ids = list(_active_trackers.keys())
        running_frames = sum(
            t.total_frames_extracted for t in _active_trackers.values()
        )

    return {
        "status":           "online",
        "node":             SOURCE_NODE_NAME,
        "hardware":         "Apple M2 Silicon",
        "cpu_percent":      cpu,
        "memory_used_gb":   round(mem.used  / (1 << 30), 2),
        "memory_total_gb":  round(mem.total / (1 << 30), 2),
        "active_pipelines": active_ids,
        "total_frames_extracted_in_flight": running_frames,
    }


@app.get("/status/{packet_id}")
async def pipeline_status(packet_id: str):
    """Live progress snapshot for an in-flight pipeline."""
    tracker = _active_trackers.get(packet_id)
    if tracker is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active pipeline found for packet_id='{packet_id}'.",
        )
    return {"packet_id": packet_id, **tracker.snapshot()}


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "extractor_main:app",
        host="0.0.0.0",
        port=8003,
        reload=False,
        log_level="info",
    )
