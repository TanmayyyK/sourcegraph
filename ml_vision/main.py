"""
main.py — SourceGraph Vision Node  |  FastAPI Application Entry-Point
Wires together VisionEngine (engine.py) and the Orchestrator client (client.py).
"""
from __future__ import annotations

import io
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, UploadFile
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError

from client import post_source_packet
from engine import VisionEngine

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
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
    """Load heavyweight ML models once at startup, release on shutdown."""
    logger.info("Starting Vision Node — loading models …")
    _state.engine = VisionEngine()
    logger.info("Vision Node ready.")
    yield
    # Explicit VRAM cleanup on graceful shutdown
    import torch
    del _state.engine
    torch.cuda.empty_cache()
    logger.info("Vision Node shut down — VRAM released.")


app = FastAPI(
    title="SourceGraph Vision Node",
    version="1.0.0",
    description="RTX 3050 VRAM-optimised visual inference engine "
                "(CLIP fp16 + YOLOv8n).",
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
    Canonical payload schema sent to the Master Orchestrator.
    Matches the /ingest contract exactly.
    """
    video_name:    str                   = Field(...,  description="Source identifier / filename")
    timestamp:     str                   = Field(...,  description="ISO-8601 UTC timestamp of processing")
    visual_vector: list[float]           = Field(...,  description="512-D L2-normalised CLIP embedding")
    text_vector:   None                  = Field(None, description="Reserved for text branch (always null here)")
    metadata:      dict[str, Any]        = Field(...,  description="YOLO top-3 detected objects + confidence")


class EmbedResponse(BaseModel):
    """Lightweight ACK returned to the caller — heavy data goes to Orchestrator."""
    status:        str  = "queued"
    packet_id:     str
    visual_vector: list[float]
    metadata:      dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Simple liveness probe — no ML involved."""
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
) -> EmbedResponse:
    """
    ### Flow
    1. Accept a raw image upload (`multipart/form-data`).
    2. Decode with PIL.
    3. Run CLIP (fp16, CUDA) → 512-D visual vector.
    4. Run YOLOv8n (CUDA) → top-3 object detections.
    5. Build a `SourcePacket` and **fire-and-forget** it to the Orchestrator
       via `BackgroundTasks` — the HTTP response is NOT blocked.
    6. Return a lightweight ACK to the caller immediately.

    ### Fault tolerance
    - Corrupt / non-image uploads → `422 Unprocessable Entity`.
    - Model-level errors → zero-vector fallback (see `engine.py`).
    - Orchestrator delivery failures → logged, never propagated to caller.
    """
    # ── 1. Read & validate image ───────────────────────────────────────────
    raw_bytes = await file.read()
    try:
        image: Image.Image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    except (UnidentifiedImageError, Exception) as exc:
        logger.warning("Rejected upload '%s': %s", file.filename, exc)
        raise HTTPException(
            status_code=422,
            detail=f"Could not decode image: {exc}",
        ) from exc

    # ── 2. Run inference ───────────────────────────────────────────────────
    visual_vector, metadata = engine.embed_and_detect(image)

    # ── 3. Construct SourcePacket ──────────────────────────────────────────
    packet_id  = str(uuid.uuid4())
    video_name = file.filename or packet_id
    timestamp  = datetime.now(timezone.utc).isoformat()

    packet = SourcePacket(
        video_name    = video_name,
        timestamp     = timestamp,
        visual_vector = visual_vector,
        text_vector   = None,
        metadata      = metadata,
    )

    # ── 4. Fire-and-forget to Orchestrator ─────────────────────────────────
    # BackgroundTask runs AFTER the response is sent — zero latency impact.
    background_tasks.add_task(
        post_source_packet,
        packet.model_dump(),
    )

    logger.info(
        "Packet %s queued for dispatch  |  file=%s  |  objects=%s",
        packet_id,
        video_name,
        [d["class"] for d in metadata.get("detected_objects", [])],
    )

    # ── 5. Immediate ACK ───────────────────────────────────────────────────
    return EmbedResponse(
        status        = "queued",
        packet_id     = packet_id,
        visual_vector = visual_vector,
        metadata      = metadata,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dev entry-point  (production: uvicorn main:app --host 0.0.0.0 --port 8080)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        # Single worker: models are NOT fork-safe after CUDA init.
        # Scale horizontally via multiple containers instead.
        workers=1,
    )