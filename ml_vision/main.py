"""
vision_main.py — SourceGraph ML Vision Node (ml_vision)  |  Contract v1.0
==========================================================================
Node B of the SourceGraph Distributed Worker architecture.

Role    : Visual Embedding Generation
Hardware: NVIDIA RTX 3050 (Rohit)
Contract: SourceGraph Distributed Worker Implementation Contract v1.0

Hosted Endpoints
----------------
    POST /embed/visual         — Receive a raw frame, run CLIP inference,
                                 fire frame_vision webhook to Orchestrator.
    POST /embed/visual/finish  — Finalise a batch: fire vision_final_summary
                                 webhook, clear local state for that packet_id.
    GET  /health               — Liveness probe (returns node + GPU status).

Startup
-------
    uvicorn vision_main:app --host 0.0.0.0 --port 8081 --workers 1

    Single-worker is intentional: CUDA models are NOT fork-safe after
    initialisation. Scale horizontally via multiple containers instead.

Environment Variables (.env)
----------------------------
    ORCHESTRATOR_URL      — Full feeder URL, e.g.
                            http://127.0.0.1:8000/api/v1/webhooks/feeder
    WEBHOOK_SECRET        — Shared secret for X-Webhook-Secret header.
    LOG_LEVEL             — DEBUG / INFO / WARNING (default: INFO).
    VISION_HOST           — Bind address (default: 0.0.0.0).
    VISION_PORT           — Bind port   (default: 8081).

Webhook Contract (Outgoing)
----------------------------
Per-frame    → type: "frame_vision"          (sent on every /embed/visual call)
End-of-batch → type: "vision_final_summary"  (sent on /embed/visual/finish)

Transmission Change Log
-----------------------
v1.0.0
- Initial implementation against Contract v1.0.
- Payload field `visual_vector` (512-D CLIP fp32) matches the contract exactly.
- `source_node` locked to "RTX-3050-Rohit" per contract §3 Node B spec.
- Thread-safe `batch_tracker` dict keyed by packet_id for multi-batch safety.
- Retry logic: 3 attempts with exponential backoff (1 s → 2 s → 4 s).
- 422 and 409 responses treated as non-retryable per contract §2 error protocol.

v1.0.0 → v1.0.1  (gap-fixes — no ML logic changed)
- [FIX 1] engine.py zero-vector passthrough: engine._clip_embed() returns
  [0.0]*512 on CLIP failure (CUDA OOM, corrupt input, etc.). The previous
  len()-only guard passed this silently. Added all(v == 0.0) check; zero
  vectors are now logged as WARNING and skipped — NOT counted in batch_tracker
  and NOT forwarded to the Orchestrator.
- [FIX 2] Contract §4 heartbeat: Added _heartbeat_loop() — an asyncio
  background task started in lifespan that fires a system_ping webhook to
  the Orchestrator every HEARTBEAT_INTERVAL_S (30 s). Added SystemPingPacket
  Pydantic model and post_system_ping() transport function.
- [FIX 3] Empty WEBHOOK_SECRET warning: Added startup log.warning() when
  _WEBHOOK_SECRET is blank so misconfigured deployments are immediately visible
  in logs rather than silently sending unauthenticated requests.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Annotated, Any

import httpx
import torch
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from engine import VisionEngine  # !! ML LOGIC — DO NOT MODIFY !!
from audio_engine import AudioEngine

# ─────────────────────────────────────────────────────────────────────────────
# Environment & logging
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()

_LOG_LEVEL        = os.environ.get("LOG_LEVEL",        "INFO").upper()
_ORCHESTRATOR_URL = os.environ.get(
    "ORCHESTRATOR_URL",
    "http://127.0.0.1:8000/api/v1/webhooks/feeder",  # Contract §2 target URL
)
_WEBHOOK_SECRET   = os.environ.get("WEBHOOK_SECRET", "")

logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("vision.main")

# [FIX 3] Warn loudly at import time if WEBHOOK_SECRET is blank.
# All outgoing requests would be sent with an empty X-Webhook-Secret header,
# which the Orchestrator will reject or silently accept depending on its config.
# This makes the misconfiguration visible immediately in logs.
if not _WEBHOOK_SECRET:
    logger.warning(
        "WEBHOOK_SECRET is not set (or is empty). "
        "All outgoing requests will carry a blank X-Webhook-Secret header. "
        "Set WEBHOOK_SECRET in your .env file before deploying to staging/production."
    )

# ─────────────────────────────────────────────────────────────────────────────
# Constants — locked to Node B spec (Contract §3)
# ─────────────────────────────────────────────────────────────────────────────
SOURCE_NODE        = "RTX-3050-Rohit"
VECTOR_DIMENSION   = 512           # CLIP/Vision-Transformer standard (Contract §1)
DIMENSIONALITY_STR = "512-D mapped"
INDEX_STATUS_STR   = "synced"

# Retry parameters (Contract §2: at least 3 attempts before discarding)
MAX_RETRIES        = 3
RETRY_BASE_DELAY_S = 1.0           # doubles each attempt: 1 s → 2 s → 4 s

# Heartbeat interval (Contract §4: all nodes SHOULD ping every 30 s)
HEARTBEAT_INTERVAL_S = 30

# ─────────────────────────────────────────────────────────────────────────────
# Application state — singleton ML engine
# ─────────────────────────────────────────────────────────────────────────────

class _AppState:
    engine: VisionEngine


_state = _AppState()


# ─────────────────────────────────────────────────────────────────────────────
# Thread-safe Batch Tracker  (Contract §3 Node B: Required State Tracking)
# ─────────────────────────────────────────────────────────────────────────────
# Keyed by packet_id (str).  Each entry is a _BatchRecord.
# A threading.Lock guards all reads and writes so BackgroundTasks running in
# the asyncio thread pool cannot race with route handlers.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _BatchRecord:
    """Per-asset accumulator — created on the first frame for a packet_id."""
    processed_count: int   = field(default=0)
    start_time:      float = field(default_factory=time.monotonic)

    @property
    def elapsed_s(self) -> float:
        """Wall-clock seconds since this batch was first seen."""
        return round(time.monotonic() - self.start_time, 3)


# Public dict — always access through _Tracker methods, never directly.
batch_tracker: dict[str, _BatchRecord] = {}
_tracker_lock  = threading.Lock()


class _Tracker:
    """Thread-safe façade over batch_tracker."""

    @staticmethod
    def increment(packet_id: str) -> int:
        """Atomically create-or-increment processed_count; return the new value."""
        with _tracker_lock:
            record = batch_tracker.setdefault(packet_id, _BatchRecord())
            record.processed_count += 1
            return record.processed_count

    @staticmethod
    def snapshot_and_clear(packet_id: str) -> _BatchRecord | None:
        """
        Return the record then remove it from the tracker.
        Returns None if packet_id was never seen (zero-frame edge case).
        """
        with _tracker_lock:
            return batch_tracker.pop(packet_id, None)


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan — load/unload the ML engine exactly once
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ML Vision Node — loading CLIP model …")
    _state.engine = VisionEngine()
    logger.info(
        "ML Vision Node ready  |  source_node=%s  target=%s",
        SOURCE_NODE, _ORCHESTRATOR_URL,
    )
    # [FIX 2] Start the Contract §4 heartbeat background task
    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    yield
    # Cancel heartbeat gracefully on shutdown
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    # Graceful VRAM release on shutdown
    del _state.engine
    torch.cuda.empty_cache()
    logger.info("ML Vision Node shut down — VRAM released.")


app = FastAPI(
    title       = "SourceGraph ML Vision Node",
    version     = "1.0.0",
    description = (
        f"Node B — Visual Embedding Generation ({SOURCE_NODE}). "
        "CLIP fp16 512-D vectors + YOLOv8n detections. "
        "Implements SourceGraph Distributed Worker Contract v1.0."
    ),
    lifespan = lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency injection
# ─────────────────────────────────────────────────────────────────────────────

def get_engine() -> VisionEngine:
    return _state.engine


EngineDep = Annotated[VisionEngine, Depends(get_engine)]


def verify_webhook_secret(
    x_webhook_secret: Annotated[str | None, Header(alias="X-Webhook-Secret")] = None,
) -> None:
    """Reject requests that do not present the configured shared secret."""
    if x_webhook_secret != _WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid X-Webhook-Secret")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas — Inbound
# ─────────────────────────────────────────────────────────────────────────────

class FinishRequest(BaseModel):
    """Body for POST /embed/visual/finish."""
    packet_id: str = Field(..., description="Asset UUID — identifies the batch to finalise")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas — Outbound Webhooks  (Contract §3 Node B)
# ─────────────────────────────────────────────────────────────────────────────

class FrameVisionPacket(BaseModel):
    """
    Per-frame webhook payload (Contract §3 Node B — frame_vision).
    Fired to POST /api/v1/webhooks/feeder on every successful CLIP embedding.

        packet_id     — Caller-supplied UUID (DB deduplication / UPSERT key)
        type          — Polymorphic discriminator: always "frame_vision"
        timestamp     — Video frame timestamp in seconds
        source_node   — Always "RTX-3050-Rohit"  (Contract §3 Node B)
        visual_vector — 512-D L2-normalised CLIP fp32 list  (Contract §1)
    """
    packet_id:     str         = Field(...,           description="Asset UUID")
    type:          str         = Field("frame_vision", description="Polymorphic discriminator")
    timestamp:     float       = Field(...,           description="Frame timestamp in seconds")
    source_node:   str         = Field(SOURCE_NODE,   description="Originating node identifier")
    visual_vector: list[float] = Field(...,           description=f"{VECTOR_DIMENSION}-D CLIP fp32 embedding")


class VisionSummaryMetrics(BaseModel):
    """Nested metrics block for vision_final_summary (Contract §3 Node B)."""
    vector_embeddings: int   = Field(...,                description="Total frames successfully embedded")
    dimensionality:    str   = Field(DIMENSIONALITY_STR, description="Embedding space identifier")
    index_status:      str   = Field(INDEX_STATUS_STR,   description="Static status string for Orchestrator UI")
    node_time_s:       float = Field(...,                description="Total wall-clock time for this batch in seconds")


class VisionSummaryPacket(BaseModel):
    """
    End-of-batch webhook payload (Contract §3 Node B — vision_final_summary).
    Sent exactly once per batch via POST /embed/visual/finish.
    """
    packet_id:   str                  = Field(...,                    description="Asset UUID")
    type:        str                  = Field("vision_final_summary", description="Polymorphic discriminator")
    source_node: str                  = Field(SOURCE_NODE,            description="Originating node identifier")
    metrics:     VisionSummaryMetrics = Field(...,                    description="Aggregated batch metrics")


# [FIX 2] — Contract §4 Shared Heartbeat
# All nodes SHOULD send a system_ping every 30 seconds.
# Node B can only authoritatively report vision_engine status;
# the remaining service keys are filled from this node's perspective.
class SystemPingServices(BaseModel):
    """Service health sub-object for system_ping (Contract §4)."""
    ingest_api:     str = Field("UNKNOWN", description="Extractor node status — not observable from Node B")
    vision_engine:  str = Field("OK",      description="This node's CLIP+YOLO engine status")
    text_processor: str = Field("UNKNOWN", description="Context node status — not observable from Node B")
    orchestrator:   str = Field("UNKNOWN", description="Inferred from last successful webhook delivery")


class SystemPingPacket(BaseModel):
    """
    Heartbeat payload (Contract §4 — shared by all nodes).
    Fired every HEARTBEAT_INTERVAL_S seconds from _heartbeat_loop().
    """
    packet_id:   str                = Field("system_broadcast",   description="Static key per contract §4")
    type:        str                = Field("system_ping",         description="Polymorphic discriminator")
    nodes_online: str               = Field("1/3",                 description="Node B's self-report — only knows its own status")
    services:    SystemPingServices = Field(default_factory=SystemPingServices)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas — API Responses (returned immediately to the caller)
# ─────────────────────────────────────────────────────────────────────────────

class EmbedVisionResponse(BaseModel):
    """Immediate ACK returned to Yogesh's Extractor after /embed/visual."""
    status:          str   = "queued"
    packet_id:       str
    frame_timestamp: float
    processed_count: int   = Field(..., description="Running frame count for this packet_id in batch_tracker")


class FinishVisionResponse(BaseModel):
    """Immediate ACK returned after /embed/visual/finish."""
    status:            str   = "summary_queued"
    packet_id:         str
    vector_embeddings: int
    node_time_s:       float


class HealthResponse(BaseModel):
    """Liveness probe response."""
    status:         str
    source_node:    str
    active_batches: int  = Field(..., description="Number of in-flight packet_ids in batch_tracker")
    gpu_available:  bool
    cuda_device:    str


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Transmission Layer — Webhook Dispatch  (Contract §2)
# ─────────────────────────────────────────────────────────────────────────────
# All outbound HTTP lives here.  Routes call these via BackgroundTasks so the
# Orchestrator being offline NEVER blocks GPU frame processing.
#
# Contract §2 error handling matrix:
#   422  — Non-retryable: schema violation, log CRITICAL, stop.
#   409  — Non-retryable: asset in terminal FAILED state, abort batch.
#   404  — Retryable:     asset propagating, backoff and retry.
#   5xx / network — Retryable: backoff and retry up to MAX_RETRIES.
# ─────────────────────────────────────────────────────────────────────────────

def _build_headers() -> dict[str, str]:
    """Standard headers for every outgoing webhook (Contract §2 — Authentication)."""
    return {
        "Content-Type":     "application/json",
        "X-Webhook-Secret": _WEBHOOK_SECRET,
    }


async def _dispatch_webhook(payload: dict[str, Any], label: str) -> None:
    """
    Core async dispatcher with retry / backoff.

    Parameters
    ----------
    payload : dict  — Serialised webhook body (from model.model_dump()).
    label   : str   — Log label, e.g. "frame_vision" or "vision_final_summary".
    """
    headers   = _build_headers()
    packet_id = payload.get("packet_id", "unknown")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    _ORCHESTRATOR_URL,
                    json    = payload,
                    headers = headers,
                )

            # ── Non-retryable: schema violation ──────────────────────────────
            if response.status_code == 422:
                logger.critical(
                    "[%s] SCHEMA VIOLATION (422) — packet_id=%s. "
                    "Halting dispatch. Verify vector dimensions and field names. "
                    "Orchestrator response: %s",
                    label, packet_id, response.text,
                )
                return  # Retrying will produce the same failure

            # ── Non-retryable: asset in terminal failed state ─────────────────
            if response.status_code == 409:
                logger.critical(
                    "[%s] ASSET TERMINAL FAILURE (409) — packet_id=%s. "
                    "Orchestrator has marked this asset as FAILED. "
                    "Aborting dispatch for this batch.",
                    label, packet_id,
                )
                return  # Further frames for this asset are meaningless

            # ── Success ───────────────────────────────────────────────────────
            if response.status_code < 300:
                logger.info(
                    "[%s] Delivered  packet_id=%s  attempt=%d/%d  http=%d",
                    label, packet_id, attempt, MAX_RETRIES, response.status_code,
                )
                return

            # ── Retryable HTTP error (404, 5xx, etc.) ─────────────────────────
            logger.warning(
                "[%s] HTTP %d — packet_id=%s  attempt=%d/%d  body=%s",
                label, response.status_code, packet_id, attempt, MAX_RETRIES,
                response.text[:200],
            )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
            logger.warning(
                "[%s] Network error — packet_id=%s  attempt=%d/%d  error=%s",
                label, packet_id, attempt, MAX_RETRIES, exc,
            )

        # ── Exponential backoff before next retry ─────────────────────────────
        if attempt < MAX_RETRIES:
            delay = RETRY_BASE_DELAY_S * (2 ** (attempt - 1))  # 1 s → 2 s → 4 s
            logger.debug("[%s] Backing off %.1f s before attempt %d …", label, delay, attempt + 1)
            await asyncio.sleep(delay)

    logger.error(
        "[%s] DISCARDED after %d attempts — packet_id=%s",
        label, MAX_RETRIES, packet_id,
    )


async def post_frame_vision(payload: dict[str, Any]) -> None:
    """Fire a frame_vision webhook. Runs as a BackgroundTask — must never raise."""
    try:
        await _dispatch_webhook(payload, label="frame_vision")
    except Exception as exc:  # Absolute safety net: GPU must keep processing
        logger.exception("[frame_vision] Unexpected dispatch failure: %s", exc)


async def post_vision_summary(payload: dict[str, Any]) -> None:
    """Fire a vision_final_summary webhook. Runs as a BackgroundTask — must never raise."""
    try:
        await _dispatch_webhook(payload, label="vision_final_summary")
    except Exception as exc:
        logger.exception("[vision_final_summary] Unexpected dispatch failure: %s", exc)


async def _run_audio_transcription_job(packet_id: str, wav_path: str) -> None:
    """
    Background Whisper pipeline for /embed/audio.
    Guarantees best-effort cleanup: hard_unload + temp file deletion.
    """
    engine = AudioEngine()
    try:
        result = await asyncio.to_thread(engine.transcribe, wav_path)
        payload = {
            "packet_id": packet_id,
            "type": "audio_final_summary",
            "source_node": SOURCE_NODE,
            "transcript": result.get("transcript", []),
            "full_script": result.get("full_script", ""),
        }
        await _dispatch_webhook(payload, label="audio_final_summary")
    except Exception as exc:
        logger.exception("[audio_final_summary] Dispatch pipeline failed: %s", exc)
    finally:
        try:
            engine.hard_unload()
        except Exception:
            logger.exception("[audio_final_summary] hard_unload failed")
        try:
            os.remove(wav_path)
        except OSError:
            pass


# [FIX 2] — Contract §4 heartbeat transport
async def post_system_ping(payload: dict[str, Any]) -> None:
    """
    Fire a system_ping webhook.
    Called directly by _heartbeat_loop() (not via BackgroundTasks) — must never raise.
    Heartbeat failures are logged at DEBUG level to avoid flooding logs when the
    Orchestrator is temporarily unreachable.
    """
    try:
        headers   = _build_headers()
        packet_id = payload.get("packet_id", "system_broadcast")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(_ORCHESTRATOR_URL, json=payload, headers=headers)
        if response.status_code < 300:
            logger.debug("[system_ping] Delivered  http=%d", response.status_code)
        else:
            logger.debug("[system_ping] HTTP %d — Orchestrator may be busy", response.status_code)
    except Exception as exc:
        # Heartbeat failures are non-critical — GPU must keep processing frames
        logger.debug("[system_ping] Delivery failed (non-critical): %s", exc)


# [FIX 2] — Contract §4 heartbeat loop
async def _heartbeat_loop() -> None:
    """
    Background asyncio task — fires a system_ping to the Orchestrator every
    HEARTBEAT_INTERVAL_S seconds for the lifetime of the process.

    Design notes:
    - Started inside lifespan() so it shares the event loop with FastAPI.
    - Cancelled automatically when the lifespan context exits on shutdown.
    - vision_engine status reflects whether _state.engine is initialised.
    - Failures are swallowed at DEBUG level; this loop must NEVER crash the node.
    """
    logger.info(
        "Heartbeat loop started — pinging Orchestrator every %d s",
        HEARTBEAT_INTERVAL_S,
    )
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_S)
        engine_status = "OK" if hasattr(_state, "engine") and _state.engine is not None else "ERROR"
        ping = SystemPingPacket(
            services=SystemPingServices(vision_engine=engine_status)
        )
        await post_system_ping(ping.model_dump())


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["ops"])
@app.get(
    "/health",
    response_model = HealthResponse,
    tags           = ["ops"],
    summary        = "Liveness probe — GPU status and active batch count",
)
async def health() -> HealthResponse:
    gpu_available = torch.cuda.is_available()
    cuda_device   = torch.cuda.get_device_name(0) if gpu_available else "CPU fallback"
    with _tracker_lock:
        active = len(batch_tracker)
    return HealthResponse(
        status         = "ok",
        source_node    = SOURCE_NODE,
        active_batches = active,
        gpu_available  = gpu_available,
        cuda_device    = cuda_device,
    )


@app.post(
    "/embed/visual",
    response_model = EmbedVisionResponse,
    tags           = ["inference"],
    dependencies   = [Depends(verify_webhook_secret)],
    summary        = "Run CLIP inference on a raw frame and fire frame_vision webhook",
)
async def embed_vision(
    background_tasks: BackgroundTasks,
    engine:           EngineDep,
    image:       UploadFile = File(...),
    packet_id:   str        = Form(...),
    timestamp:   float      = Form(...),
    frame_index: int        = Form(-1),
    video_name:  str        = Form(""),
) -> EmbedVisionResponse:
    """
    Main inference endpoint — called once per frame by Yogesh's Extractor.
    """
    # ── 1. Read & validate image bytes ───────────────────────────────────────
    raw_bytes = await image.read()
    if not raw_bytes:
        raise HTTPException(status_code=422, detail="Uploaded frame is empty.")

    try:
        img_obj = Image.open(io.BytesIO(raw_bytes))
        img_obj.verify()                              # Detects truncated/corrupt files
        img_obj = Image.open(io.BytesIO(raw_bytes))   # Re-open: verify() exhausts the stream
    except (UnidentifiedImageError, Exception) as exc:
        logger.warning(
            "Rejected frame  packet_id=%s  file=%s  error=%s",
            packet_id, video_name, exc,
        )
        raise HTTPException(
            status_code = 422,
            detail      = f"Cannot decode frame image: {exc}",
        ) from exc

    # ── 2. ML Inference  (CLIP 512-D embedding + YOLO detections) ────────────
    # !! DO NOT MODIFY — core ML logic !!
    visual_vector, inference_metadata = engine.embed_and_detect(img_obj)

    # Guard: enforce dimensionality contract (Contract §1)
    if len(visual_vector) != VECTOR_DIMENSION:
        logger.critical(
            "DIMENSION CONTRACT VIOLATION — expected %d-D got %d-D  packet_id=%s",
            VECTOR_DIMENSION, len(visual_vector), packet_id,
        )
        raise HTTPException(
            status_code = 500,
            detail      = f"Engine returned {len(visual_vector)}-D vector; contract requires {VECTOR_DIMENSION}-D.",
        )

    # [FIX 1] Zero-vector passthrough guard.
    # engine._clip_embed() returns [0.0]*512 on CUDA OOM or any CLIP failure
    # (see engine.py lines under "Failure modes handled").  A zero-vector passes
    # the len() check above but is NOT a valid embedding — it carries no semantic
    # information and would corrupt Orchestrator similarity searches.
    # We detect it here (outside engine.py so ML logic stays untouched), log a
    # WARNING, and return 422 so the Extractor knows to retry or flag the frame.
    if all(v == 0.0 for v in visual_vector):
        logger.warning(
            "Zero-vector returned by engine — CLIP likely failed (OOM or corrupt input). "
            "Frame NOT counted or forwarded.  packet_id=%s  file=%s",
            packet_id, video_name,
        )
        raise HTTPException(
            status_code = 422,
            detail      = (
                "CLIP embedding failed for this frame (engine returned a zero-vector). "
                "Possible causes: CUDA OOM, corrupt/blank image, or model error. "
                "Check Vision Node logs for details."
            ),
        )

    # ── 3. Update batch_tracker (thread-safe) ────────────────────────────────
    processed_count = _Tracker.increment(packet_id)

    # ── 4. Build frame_vision webhook payload (Contract §3 Node B) ──────────
    packet = FrameVisionPacket(
        packet_id     = packet_id,
        type          = "frame_vision",       # Contract discriminator
        timestamp     = timestamp,
        source_node   = SOURCE_NODE,          # "RTX-3050-Rohit"
        visual_vector = visual_vector,        # 512-D CLIP fp32 — field name per contract
    )

    # ── 5. Fire-and-forget to Orchestrator ───────────────────────────────────
    background_tasks.add_task(post_frame_vision, packet.model_dump())

    detected = [d["class"] for d in inference_metadata.get("detected_objects", [])]
    logger.info(
        "Queued frame_vision  packet_id=%s  ts=%.3f  frame#=%d  objects=%s",
        packet_id, timestamp, processed_count, detected,
    )

    # ── 6. Immediate ACK to Extractor ────────────────────────────────────────
    return EmbedVisionResponse(
        status          = "queued",
        packet_id       = packet_id,
        frame_timestamp = timestamp,
        processed_count = processed_count,
    )


@app.post(
    "/embed/audio",
    status_code  = 202,
    tags         = ["inference"],
    dependencies = [Depends(verify_webhook_secret)],
    summary      = "Accept WAV and run Whisper in background; ACK immediately",
)
async def embed_audio(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    packet_id: str = Form(...),
) -> dict[str, Any]:
    raw_bytes = await audio.read()
    if not raw_bytes:
        raise HTTPException(status_code=422, detail="Uploaded audio file is empty.")

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".wav", prefix=f"{packet_id}_"
    ) as tmp:
        tmp.write(raw_bytes)
        wav_path = tmp.name

    background_tasks.add_task(_run_audio_transcription_job, packet_id, wav_path)
    return {"status": "accepted", "packet_id": packet_id}


@app.post(
    "/embed/visual/finish",
    response_model = FinishVisionResponse,
    tags           = ["inference"],
    dependencies   = [Depends(verify_webhook_secret)],
    summary        = "Finalise a batch — fire vision_final_summary and clear local state",
)
async def embed_vision_finish(
    background_tasks: BackgroundTasks,
    body:             FinishRequest,
) -> FinishVisionResponse:
    """
    Batch finalisation endpoint — called ONCE by Yogesh after all frames
    for an asset have been dispatched to /embed/visual.

    Pipeline:
      1. Atomically snapshot and remove _BatchRecord for this packet_id.
      2. Build VisionSummaryPacket with final metrics.
      3. Fire vision_final_summary webhook in background.
      4. Return immediate ACK.

    Edge case: if /embed/visual/finish is called before any frames arrived (zero-frame
    batch), a summary with vector_embeddings=0 is still dispatched so the
    Orchestrator receives a completion signal.
    """
    packet_id = body.packet_id

    # ── 1. Snapshot + clear (thread-safe, atomic) ─────────────────────────────
    record = _Tracker.snapshot_and_clear(packet_id)

    if record is None:
        # No frames were received for this packet_id before finish was called.
        logger.warning(
            "finish called for unknown packet_id=%s — no frames on record. "
            "Dispatching zero-count summary.",
            packet_id,
        )
        vector_embeddings = 0
        node_time_s = 0.0
    else:
        vector_embeddings = record.processed_count
        node_time_s = record.elapsed_s

    # ── 2. Build vision_final_summary payload (Contract §3 Node B) ──────────
    packet = VisionSummaryPacket(
        packet_id   = packet_id,
        type        = "vision_final_summary",   # Contract discriminator
        source_node = SOURCE_NODE,
        metrics     = VisionSummaryMetrics(
            vector_embeddings = vector_embeddings,
            dimensionality    = DIMENSIONALITY_STR,   # "512-D mapped"
            index_status      = INDEX_STATUS_STR,      # "synced"
            node_time_s       = node_time_s,
        ),
    )

    # ── 3. Fire-and-forget to Orchestrator ───────────────────────────────────
    background_tasks.add_task(post_vision_summary, packet.model_dump())

    logger.info(
        "Queued vision_final_summary  packet_id=%s  vectors=%d  node_time_s=%.3f",
        packet_id, vector_embeddings, node_time_s,
    )

    # ── 4. Immediate ACK to Extractor ────────────────────────────────────────
    return FinishVisionResponse(
        status            = "summary_queued",
        packet_id         = packet_id,
        vector_embeddings = vector_embeddings,
        node_time_s       = node_time_s,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dev entry-point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    _host    = os.environ.get("VISION_HOST", "0.0.0.0")
    _port    = int(os.environ.get("VISION_PORT", "8081"))
    _log_lvl = _LOG_LEVEL.lower()

    uvicorn.run(
        "main:app",
        host      = _host,
        port      = _port,
        log_level = _log_lvl,
        workers   = 1,   # Single-worker — CUDA is not fork-safe
    )