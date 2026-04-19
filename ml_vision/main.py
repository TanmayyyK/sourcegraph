"""
main.py — SourceGraph Vision Node  |  FastAPI Application Entry-Point
Wires together VisionEngine (engine.py) and the Orchestrator client (client.py).

Startup
-------
    uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1

    Single-worker is intentional: CUDA models are NOT fork-safe after
    initialisation.  Scale horizontally via multiple containers instead.
"""
from __future__ import annotations

import io
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Any

import torch
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from client import post_source_packet
from engine import VisionEngine

# ─────────────────────────────────────────────────────────────────────────────
# Environment & logging
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("vision.main")


# ─────────────────────────────────────────────────────────────────────────────
# Application state  (singleton engine lives here)
# ─────────────────────────────────────────────────────────────────────────────

class _AppState:
    engine: VisionEngine


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load heavyweight ML models once at startup; release VRAM on shutdown."""
    logger.info("Starting Vision Node — loading models …")
    _state.engine = VisionEngine()
    logger.info("Vision Node ready.")
    yield
    # Explicit VRAM cleanup on graceful shutdown
    del _state.engine
    torch.cuda.empty_cache()
    logger.info("Vision Node shut down — VRAM released.")


app = FastAPI(
    title="SourceGraph Vision Node",
    version="1.1.0",
    description=(
        "RTX 3050 VRAM-optimised visual inference engine (CLIP fp16 + YOLOv8n). "
        "Accepts raw image frames, returns 512-D CLIP vectors + YOLO metadata, "
        "and forwards a SourcePacket to the Master Orchestrator."
    ),
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency injection
# ─────────────────────────────────────────────────────────────────────────────

def get_engine() -> VisionEngine:
    """Inject the singleton VisionEngine into route handlers."""
    return _state.engine


EngineDep = Annotated[VisionEngine, Depends(get_engine)]


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class SourcePacket(BaseModel):
    """
    Canonical payload forwarded to the Master Orchestrator (/ingest/visual).
    Field names are intentionally stable — the Orchestrator schema mirrors this.
    """
    packet_id:     str                = Field(..., description="Caller-supplied UUID (deduplication key)")
    video_name:    str                = Field(..., description="Source identifier / original filename")
    timestamp:     str                = Field(..., description="ISO-8601 UTC timestamp supplied by caller")
    visual_vector: list[float]        = Field(..., description="512-D L2-normalised CLIP fp32 embedding")
    text_vector:   None               = Field(None, description="Reserved for future text branch")
    metadata:      dict[str, Any]     = Field(..., description="YOLO top-3 detected objects + confidence")


class EmbedResponse(BaseModel):
    """
    Lightweight ACK returned immediately to the caller.
    Heavy payload (visual_vector) is included for local debugging — omit or
    gate behind a query flag if bandwidth is a concern in production.
    """
    status:        str            = "queued"
    packet_id:     str
    visual_vector: list[float]
    metadata:      dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"], summary="Liveness probe")
async def health() -> dict[str, str]:
    """Returns ``{"status": "ok"}`` — no ML involved, suitable for L4 probes."""
    return {"status": "ok"}


@app.post(
    "/embed/visual",
    response_model=EmbedResponse,
    summary="Extract CLIP embedding + YOLO detections from an uploaded image",
    tags=["inference"],
)
async def embed_visual(
    file:             UploadFile,
    background_tasks: BackgroundTasks,
    engine:           EngineDep,
    # ── Caller-supplied identity fields (Form fields in multipart payload) ──
    packet_id: str = Form(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID identifying this packet (used for dedup + tracing). "
                    "Auto-generated if not supplied.",
    ),
    timestamp: str = Form(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp of frame capture. "
                    "Defaults to server receive-time if not supplied.",
    ),
) -> EmbedResponse:
    """
    ### Multipart form fields
    | Field       | Type   | Required | Description                        |
    |-------------|--------|----------|------------------------------------|
    | `file`      | binary | ✅        | Raw image (JPEG / PNG / WebP / …)  |
    | `packet_id` | string | ❌        | UUID — auto-generated if omitted   |
    | `timestamp` | string | ❌        | ISO-8601 UTC — defaults to now     |

    ### Processing flow
    1. Decode uploaded image with PIL (rejects non-images with **422**).
    2. Run CLIP ViT-B/32 fp16 → 512-D L2-normalised visual vector.
    3. Run YOLOv8n → top-3 object detections with confidence scores.
    4. Build a `SourcePacket` and **fire-and-forget** to the Orchestrator
       via `BackgroundTasks` — the HTTP response is **not** blocked.
    5. Return a lightweight ACK immediately.

    ### Fault tolerance
    - Corrupt/non-image uploads → **422 Unprocessable Entity**.
    - CUDA OOM in either model → zero-vector / empty-detections fallback.
    - Orchestrator delivery failure → logged + retried; never propagated.
    """
    # ── 1. Read & decode image ─────────────────────────────────────────────
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    try:
        image: Image.Image = Image.open(io.BytesIO(raw_bytes))
        image.verify()                          # Detect truncated / corrupt files early
        image = Image.open(io.BytesIO(raw_bytes))  # Re-open: verify() exhausts the fp
    except (UnidentifiedImageError, Exception) as exc:
        logger.warning(
            "Rejected upload '%s' (packet_id=%s): %s",
            file.filename, packet_id, exc,
        )
        raise HTTPException(
            status_code=422,
            detail=f"Could not decode image: {exc}",
        ) from exc

    # ── 2. Run inference ────────────────────────────────────────────────────
    visual_vector, metadata = engine.embed_and_detect(image)

    # ── 3. Build SourcePacket ───────────────────────────────────────────────
    video_name = file.filename or packet_id

    packet = SourcePacket(
        packet_id     = packet_id,
        video_name    = video_name,
        timestamp     = timestamp,
        visual_vector = visual_vector,
        text_vector   = None,
        metadata      = metadata,
    )

    # ── 4. Fire-and-forget to Orchestrator ──────────────────────────────────
    # BackgroundTask runs AFTER the HTTP response is sent — zero added latency.
    background_tasks.add_task(post_source_packet, packet.model_dump())

    detected_classes = [d["class"] for d in metadata.get("detected_objects", [])]
    logger.info(
        "Queued packet_id=%s  file=%s  objects=%s",
        packet_id, video_name, detected_classes,
    )

    # ── 5. Immediate ACK ────────────────────────────────────────────────────
    return EmbedResponse(
        status        = "queued",
        packet_id     = packet_id,
        visual_vector = visual_vector,
        metadata      = metadata,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dev entry-point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    host    = os.environ.get("VISION_HOST", "0.0.0.0")
    port    = int(os.environ.get("VISION_PORT", "8080"))
    log_lvl = _LOG_LEVEL.lower()

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_lvl,
        workers=1,   # MUST stay 1: CUDA models are not fork-safe post-init
    )