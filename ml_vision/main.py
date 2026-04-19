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
import json
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

import torch
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, UploadFile, File
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
    return _state.engine


EngineDep = Annotated[VisionEngine, Depends(get_engine)]


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class SourcePacket(BaseModel):
    """
    Canonical payload forwarded to the Master Orchestrator (/api/v1/webhooks/vector).
    Strict payload matching Tanmay's WebhookVectorPayload.
    """
    packet_id:     str                = Field(..., description="Caller-supplied UUID (deduplication key)")
    timestamp:     float              = Field(..., description="video timestamp float")
    visual_vector: list[float]        = Field(..., description="512-D L2-normalised CLIP fp32 embedding")
    source_node:   str                = "Rohit-RTX3050"


class EmbedResponse(BaseModel):
    """Lightweight ACK returned immediately to the caller."""
    status:        str            = "queued"
    packet_id:     str
    visual_vector: list[float]


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"], summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/embed/visual",
    response_model=EmbedResponse,
    summary="Extract CLIP embedding + YOLO detections from an uploaded image",
    tags=["inference"],
)
async def embed_visual(
    background_tasks: BackgroundTasks,
    engine: EngineDep,
    image: UploadFile = File(...),         # MUST BE "image" TO MATCH YOGESH!
    metadata: str = Form("{}"),            # MUST BE "metadata" TO EXTRACT JSON STRING
) -> EmbedResponse:
    # ── 0. Parse Metadata from JSON String ─────────────────────────────────
    meta = {}
    if metadata != "{}":
        try:
            meta = json.loads(metadata)
        except Exception as exc:
            logger.warning("Failed to decode Yogesh metadata JSON: %s", exc)

    packet_id = meta.get("packet_id", str(uuid.uuid4()))
    video_name = meta.get("video_name", image.filename)
    frame_index = meta.get("frame_index", -1)
    video_ts = meta.get("video_timestamp_s", -1)

    # Cast to float for Tanmay's Pydantic verification
    valid_timestamp = float(video_ts) if float(video_ts) >= 0 else float(frame_index)

    # ── 1. Read & decode image ─────────────────────────────────────────────
    raw_bytes = await image.read()
    if not raw_bytes:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    try:
        img_obj = Image.open(io.BytesIO(raw_bytes))
        img_obj.verify()                          
        img_obj = Image.open(io.BytesIO(raw_bytes))  
    except (UnidentifiedImageError, Exception) as exc:
        logger.warning(
            "Rejected upload '%s' (packet_id=%s): %s",
            video_name, packet_id, exc,
        )
        raise HTTPException(status_code=422, detail=f"Could not decode image: {exc}") from exc

    # ── 2. Run inference ────────────────────────────────────────────────────
    visual_vector, inference_metadata = engine.embed_and_detect(img_obj)

    # ── 3. Build SourcePacket ───────────────────────────────────────────────
    packet = SourcePacket(
        packet_id     = packet_id,
        timestamp     = valid_timestamp,
        visual_vector = visual_vector,
        source_node   = "Rohit-RTX3050"
    )

    # ── 4. Fire-and-forget to Orchestrator ──────────────────────────────────
    background_tasks.add_task(post_source_packet, packet.model_dump())

    detected_classes = [d["class"] for d in inference_metadata.get("detected_objects", [])]
    logger.info(
        "Queued packet_id=%s  file=%s  objects=%s",
        packet_id, video_name, detected_classes,
    )

    # ── 5. Immediate ACK ────────────────────────────────────────────────────
    return EmbedResponse(
        status        = "queued",
        packet_id     = packet_id,
        visual_vector = visual_vector,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dev entry-point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    host    = os.environ.get("VISION_HOST", "0.0.0.0")
    port    = int(os.environ.get("VISION_PORT", "8001")) # Changed to 8001 to match Yogesh
    log_lvl = _LOG_LEVEL.lower()

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_lvl,
        workers=1,
    )