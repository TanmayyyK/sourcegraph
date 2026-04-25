"""
╔══════════════════════════════════════════════════════════════════════════╗
║  SourceGraph — ML Context Node  (FastAPI)                                ║
║  Owner       : Yug  (NVIDIA RTX 2050)                                    ║
║  Contract    : SourceGraph Distributed Worker Implementation v1.0        ║
║                                                                          ║
║  ROLE  : OCR Extraction & Semantic Text Embedding (Node C / ml_context)  ║
║                                                                          ║
║  ENDPOINTS                                                               ║
║    GET  /health           → liveness heartbeat                           ║
║    POST /embed/text       → per-frame OCR + MiniLM → fires frame_text    ║
║    POST /embed/text/finish→ end-of-batch → fires text_final_summary      ║
║                                                                          ║
║  OUTBOUND WEBHOOKS  (→ Orchestrator /api/v1/webhooks/feeder)             ║
║    frame_text          – one per frame                                   ║
║    text_final_summary  – once per batch after /embed/text/finish         ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import os
# Must be set before any OpenMP-linked library (numpy, cv2, easyocr) is imported.
# Mirrors the fix in main.py — without this the process crashes on Windows/some
# Linux builds when both Intel and GNU OpenMP runtimes are loaded simultaneously.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import time
import threading
import logging
from typing import Annotated, Any

import numpy as np
import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from overwatch_logic import OverwatchNode, ConflictDetector

# ──────────────────────────────────────────────────────────────────────────────
# Bootstrap
# ──────────────────────────────────────────────────────────────────────────────

print("\n" + "="*50)
print("!!!!! YUG LOADED CONTRACT V2 !!!!!")
print("="*50 + "\n")

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("context_node")

# ──────────────────────────────────────────────────────────────────────────────
# Configuration  (all values from .env with safe fallbacks)
# ──────────────────────────────────────────────────────────────────────────────

ORCHESTRATOR_URL: str = os.getenv(
    "TANMAY_URL",
    "http://<orchestrator-host>:<port>/api/v1/webhooks/feeder",
)
WEBHOOK_SECRET: str   = os.getenv("WEBHOOK_SECRET", "change-me-in-production")
HOST: str             = os.getenv("HOST", "0.0.0.0")
PORT: int             = int(os.getenv("PORT", "8002"))
SOURCE_NODE: str      = "RTX-2050-Yug"

# Contract-mandated vector dimensionality for this node
TEXT_VECTOR_DIM: int  = 384

# ──────────────────────────────────────────────────────────────────────────────
# ML Engine  (OverwatchNode from overwatch_logic.py — core ML logic, UNTOUCHED)
# ──────────────────────────────────────────────────────────────────────────────
# OverwatchNode owns:
#   • EasyOCR   (lazy-loaded in prepare_visual_phase)
#   • MiniLM    (lazy-loaded in prepare_visual_phase)
#   • Anti-Gravity VRAM context managers
#   • OCR accumulator (node.ocr_list)
#   • ConflictDetector bridge (generate_master_packet)
#
# We call prepare_visual_phase() once at startup so the first frame request
# doesn't pay the model-load latency penalty mid-stream.

node = OverwatchNode()

log.info("⏳  Warming up OverwatchNode — loading EasyOCR + MiniLM via Anti-Gravity protocol …")
node.prepare_visual_phase()
log.info("✅  OverwatchNode visual phase ready.  VRAM governor active.")


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SourceGraph — ML Context Node",
    description="OCR extraction and 384-D semantic text embedding (Node C, ml_context).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────────────────
# Thread-Safe Batch Tracker
# ──────────────────────────────────────────────────────────────────────────────
# Schema per packet_id entry:
#   {
#       "ocr_chunks":      int,   # running total of text chunks detected
#       "bounding_boxes":  int,   # running total of OCR bounding boxes
#       "start_time":      float, # time.monotonic() of first frame in batch
#       "last_ocr_text":   str,   # most recent frame's OCR output (for generate_master_packet)
#   }

_tracker_lock = threading.Lock()
batch_tracker: dict[str, dict[str, Any]] = {}


def verify_webhook_secret(
    x_webhook_secret: Annotated[str | None, Header(alias="X-Webhook-Secret")] = None,
) -> None:
    if x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid X-Webhook-Secret")


class FinishRequest(BaseModel):
    packet_id: str
    source_node: str | None = None


def _get_or_init_batch(packet_id: str) -> dict[str, Any]:
    """
    Return the accumulator dict for *packet_id*.
    Creates a fresh entry (with start_time = now) if one does not exist.
    Caller MUST hold _tracker_lock.
    """
    if packet_id not in batch_tracker:
        batch_tracker[packet_id] = {
            "ocr_chunks":     0,
            "bounding_boxes": 0,
            "start_time":     time.monotonic(),
            "last_ocr_text":  "",
        }
    return batch_tracker[packet_id]


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator Webhook Sender
# ──────────────────────────────────────────────────────────────────────────────

def _fire_webhook(payload: dict[str, Any], label: str = "") -> None:
    """
    POST *payload* to the Orchestrator's polymorphic feeder endpoint.

    Resilience contract:
      • Always attaches X-Webhook-Secret header.
      • Logs non-2xx responses for observability.
      • Swallows connection/timeout errors so inference never stalls.
      • 422 → CRITICAL log (schema violation — dev must fix).
      • 409 → WARNING log (asset is in terminal FAILED state).
    """
    tag = f" [{label}]" if label else ""
    try:
        headers = {
            "Content-Type":    "application/json",
            "X-Webhook-Secret": WEBHOOK_SECRET,
        }
        resp = requests.post(
            ORCHESTRATOR_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if resp.status_code in (200, 202):
            log.debug("📤  Webhook OK%s  →  %d", tag, resp.status_code)

        elif resp.status_code == 422:
            log.critical(
                "🚫  Webhook REJECTED%s (422 — schema violation). "
                "Stopping current frame. Response: %s",
                tag, resp.text,
            )

        elif resp.status_code == 409:
            log.warning(
                "⛔  Webhook CONFLICT%s (409 — asset in terminal FAILED state). "
                "Aborting batch. Response: %s",
                tag, resp.text,
            )

        else:
            log.warning(
                "⚠️   Webhook non-2xx%s  →  %d: %s",
                tag, resp.status_code, resp.text,
            )

    except requests.exceptions.ConnectionError:
        log.error("🚨  Orchestrator unreachable%s — webhook dropped.", tag)
    except requests.exceptions.Timeout:
        log.error("⏳  Orchestrator timed-out%s — webhook dropped.", tag)
    except Exception as exc:                         # noqa: BLE001
        log.error("🚨  Webhook send error%s: %s", tag, exc)


# ──────────────────────────────────────────────────────────────────────────────
# ML Inference Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _run_inference(image_bytes: bytes) -> tuple[str, list[float], float, int, int]:
    """
    Delegate inference to ``OverwatchNode.run_visual_phase`` (overwatch_logic.py).

    OverwatchNode handles:
      • cv2 image decode
      • EasyOCR extraction with detail=1
      • MiniLM embedding ("Empty Context" fallback when no text found)
      • VRAM assertion via _assert_memory()
      • ocr_list accumulation for ConflictDetector

    chunk/box counts are derived from the delta of ``node.ocr_list`` before and
    after the call — this avoids duplicating readtext logic outside the node.
    Since run_visual_phase adds every detected region to ocr_list (no confidence
    filtering), chunks_extracted == boxes_mapped for this implementation.

    Returns
    -------
    ocr_text         : joined OCR string (may be empty)
    text_vector      : 384-D float list from MiniLM
    confidence       : mean OCR confidence (0.0 if no text)
    chunks_extracted : OCR regions detected this frame
    boxes_mapped     : bounding boxes drawn by EasyOCR (== chunks here)
    """
    pre_len  = len(node.ocr_list)
    result   = node.run_visual_phase(image_bytes)
    post_len = len(node.ocr_list)

    chunks_extracted = post_len - pre_len
    boxes_mapped     = chunks_extracted   # run_visual_phase maps 1 box → 1 chunk

    return (
        result["ocr_text"],
        result["vector"],
        result["confidence"],
        chunks_extracted,
        boxes_mapped,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "idle",
        "active_batches": 0,
        "queue_size": 0
    }


@app.post("/embed/text", tags=["Inference"], dependencies=[Depends(verify_webhook_secret)])
async def embed_text(
    image:         UploadFile = File(...,  description="224×224 JPEG frame bytes"),
    packet_id:     str        = Form(...,  description="UUID of the originating ingest job"),
    timestamp:     float      = Form(...,  description="Frame timestamp in seconds (float)"),
    frame_index:   int        = Form(-1,   description="Zero-based frame index (for logging)"),
    video_name:    str        = Form("",   description="Human-readable video filename (for logging)"),
) -> dict[str, Any]:
    """
    Per-frame inference endpoint.
    """
    raw_bytes = await image.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty image upload.")

    try:
        ocr_text, text_vector, confidence, chunks_extracted, boxes_mapped = (
            _run_inference(raw_bytes)
        )
    except AssertionError as exc:
        log.critical("🚨  VRAM ceiling hit: %s", exc)
        raise HTTPException(status_code=503, detail=f"VRAM: {exc}") from exc

    log.info(
        "🔍  frame %d | %s | packet=%s… | ocr=%r",
        frame_index, video_name or "?", packet_id[:8], ocr_text[:80],
    )

    with _tracker_lock:
        batch = _get_or_init_batch(packet_id)
        batch["ocr_chunks"]     += chunks_extracted
        batch["bounding_boxes"] += boxes_mapped
        batch["last_ocr_text"]   = ocr_text

    frame_payload: dict[str, Any] = {
        "packet_id":        packet_id,
        "type":             "frame_text",
        "timestamp":        float(timestamp),
        "source_node":      SOURCE_NODE,
        "chunks_extracted": chunks_extracted,
        "boxes_mapped":     boxes_mapped,
        "ocr_text":         ocr_text,
        "text_vector":      text_vector,
    }

    _fire_webhook(frame_payload, label=f"frame_text frame={frame_index}")
    return frame_payload


@app.post("/embed/text/finish", tags=["inference"])
async def finish_signal(packet_id: str = Form(...)):
    return {"status": "accepted", "packet_id": packet_id}


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
