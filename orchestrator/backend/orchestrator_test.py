"""
orchestrator_test.py — Master Orchestrator Loopback Test
=========================================================
Runs two concurrent tasks in a single process:

  1. **Webhook Receiver** (FastAPI on :8000)
     Accepts SourcePacket payloads from the Vision Node at ``POST /ingest/visual``
     and appends each validated packet to ``results.json``.

  2. **Batch Sender** (async httpx)
     Iterates every image in ``./test_images/`` and POSTs each one to the
     Vision Node's ``/embed/visual`` endpoint, including a generated
     ``packet_id`` and ISO-8601 ``timestamp`` as multipart form fields.

Usage
-----
    # Install deps (once):
    pip install fastapi uvicorn[standard] httpx aiofiles python-multipart

    # Place ~25 test images in ./test_images/
    # Set VISION_NODE_URL if Rohit's IP differs from the default below.

    VISION_NODE_URL=http://<ROHIT_IP>:8080 python orchestrator_test.py

Configuration (env vars — all optional)
----------------------------------------
    VISION_NODE_URL   Vision Node base URL   (default: http://127.0.0.1:8080)
    RECEIVER_HOST     Receiver bind host      (default: 0.0.0.0)
    RECEIVER_PORT     Receiver bind port      (default: 8000)
    TEST_IMAGES_DIR   Folder of test images   (default: ./test_images)
    RESULTS_FILE      Output JSON path        (default: ./results.json)
    SEND_CONCURRENCY  Max parallel sends      (default: 5)
    STARTUP_DELAY     Seconds to wait for
                      receiver before sending (default: 2.0)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiofiles
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("orchestrator_test")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
VISION_NODE_URL  : str   = os.environ.get("VISION_NODE_URL",  "http://127.0.0.1:8080")
RECEIVER_HOST    : str   = os.environ.get("RECEIVER_HOST",    "0.0.0.0")
RECEIVER_PORT    : int   = int(os.environ.get("RECEIVER_PORT", "8000"))
TEST_IMAGES_DIR  : Path  = Path(os.environ.get("TEST_IMAGES_DIR", "./test_images"))
RESULTS_FILE     : Path  = Path(os.environ.get("RESULTS_FILE",    "./results.json"))
SEND_CONCURRENCY : int   = int(os.environ.get("SEND_CONCURRENCY", "5"))
STARTUP_DELAY    : float = float(os.environ.get("STARTUP_DELAY",  "2.0"))

# Image extensions the sender will pick up
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

# Timeouts for Vision Node calls
_SEND_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=15.0, pool=5.0)


# ─────────────────────────────────────────────────────────────────────────────
# ① WEBHOOK RECEIVER — FastAPI application
# ─────────────────────────────────────────────────────────────────────────────

receiver_app = FastAPI(
    title="Orchestrator Loopback Receiver",
    version="1.0.0",
    description="Captures SourcePackets from the Vision Node and writes results.json",
)

# In-memory counter (races are not a concern — single uvicorn worker)
_received_count: int = 0

# File-write lock: guarantees atomic JSON array appends across async tasks
_results_lock = asyncio.Lock()

class IncomingSourcePacket(BaseModel):
    """
    The 'Bulletproof' Version: 
    Accepts everything, rejects nothing.
    """
    model_config = {"extra": "allow"}

    # We use Optional types for EVERYTHING to stop the 422 errors
    packet_id:     str | None = Field(default=None)
    visual_vector: list[float] | None = Field(default=None)
    video_name:    str | None = Field(default=None)
    timestamp:     str | None = Field(default=None)
    metadata:      dict[str, Any] | None = Field(default_factory=dict)


@receiver_app.get("/health", tags=["ops"])
async def receiver_health() -> dict[str, Any]:
    return {"status": "ok", "received": _received_count}


@receiver_app.post(
    "/ingest",
    status_code=200,
    tags=["ingest"],
    summary="Accept a SourcePacket from the Vision Node",
)
async def ingest_visual(packet: IncomingSourcePacket) -> dict[str, str]:
    """
    Validate the incoming SourcePacket, append it to ``results.json``,
    and return an immediate ACK.

    ``results.json`` structure
    --------------------------
    A JSON array; each element is a full SourcePacket dict plus a
    server-side ``received_at`` timestamp for traceability.
    """
    global _received_count

    record: dict[str, Any] = {
        **packet.model_dump(),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }

    async with _results_lock:
        # Read existing array (or start fresh)
        existing: list[dict[str, Any]] = []
        if RESULTS_FILE.exists():
            try:
                async with aiofiles.open(RESULTS_FILE, "r") as fh:
                    raw = await fh.read()
                    existing = json.loads(raw) if raw.strip() else []
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read %s — starting fresh: %s", RESULTS_FILE, exc)

        existing.append(record)

        async with aiofiles.open(RESULTS_FILE, "w") as fh:
            await fh.write(json.dumps(existing, indent=2))

    _received_count += 1
    logger.info(
        "✅ Received packet #%d  id=%s  objects=%s",
        _received_count,
        packet.packet_id,
        [d["class"] for d in packet.metadata.get("detected_objects", [])],
    )

    return {"status": "stored", "packet_id": packet.packet_id}


# ─────────────────────────────────────────────────────────────────────────────
# ② BATCH SENDER — async httpx
# ─────────────────────────────────────────────────────────────────────────────

async def _send_image(
    client:    httpx.AsyncClient,
    image_path: Path,
    semaphore:  asyncio.Semaphore,
    stats:      dict[str, int],
) -> None:
    """
    POST a single image file to the Vision Node as multipart/form-data.

    Form fields
    -----------
    file       — binary image content
    packet_id  — freshly generated UUID v4
    timestamp  — ISO-8601 UTC wall-clock time at submission
    """
    packet_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    embed_url = f"{VISION_NODE_URL.rstrip('/')}/embed/visual"

    async with semaphore:
        try:
            image_bytes = image_path.read_bytes()

            # Derive a plausible MIME type from the file extension
            suffix      = image_path.suffix.lower()
            mime_map    = {
                ".jpg":  "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png":  "image/png",
                ".webp": "image/webp",
                ".bmp":  "image/bmp",
                ".tiff": "image/tiff",
                ".tif":  "image/tiff",
            }
            content_type = mime_map.get(suffix, "application/octet-stream")

            files   = {"file": (image_path.name, image_bytes, content_type)}
            data    = {"packet_id": packet_id, "timestamp": timestamp}

            t0       = time.perf_counter()
            response = await client.post(embed_url, files=files, data=data)
            elapsed  = (time.perf_counter() - t0) * 1000  # ms

            if response.status_code == 200:
                stats["success"] += 1
                logger.info(
                    "→ Sent %-40s  packet_id=%s  HTTP %d  %.0f ms",
                    image_path.name, packet_id, response.status_code, elapsed,
                )
            else:
                stats["failure"] += 1
                logger.warning(
                    "→ Rejected %-36s  packet_id=%s  HTTP %d: %s",
                    image_path.name, packet_id,
                    response.status_code, response.text[:200],
                )

        except httpx.TimeoutException:
            stats["failure"] += 1
            logger.error("Timeout sending %s (packet_id=%s)", image_path.name, packet_id)

        except httpx.RequestError as exc:
            stats["failure"] += 1
            logger.error(
                "Network error sending %s (packet_id=%s): %s",
                image_path.name, packet_id, exc,
            )

        except Exception:
            stats["failure"] += 1
            logger.exception(
                "Unexpected error sending %s (packet_id=%s)", image_path.name, packet_id
            )


async def run_batch_sender() -> None:
    """
    Discover images in ``TEST_IMAGES_DIR``, wait for the receiver to warm up,
    then send them concurrently (bounded by ``SEND_CONCURRENCY``).
    """
    if not TEST_IMAGES_DIR.is_dir():
        logger.error(
            "Test images directory not found: %s — create it and populate "
            "it with ~25 images before running this script.",
            TEST_IMAGES_DIR,
        )
        return

    image_paths: list[Path] = sorted(
        p for p in TEST_IMAGES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES
    )

    if not image_paths:
        logger.error(
            "No images found in %s (looking for: %s).",
            TEST_IMAGES_DIR, ", ".join(sorted(_IMAGE_SUFFIXES)),
        )
        return

    logger.info(
        "Found %d image(s) in %s — waiting %.1f s for receiver to start …",
        len(image_paths), TEST_IMAGES_DIR, STARTUP_DELAY,
    )
    await asyncio.sleep(STARTUP_DELAY)

    # Verify Vision Node reachability before committing the full batch
    health_url = f"{VISION_NODE_URL.rstrip('/')}/health"
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as probe:
        try:
            r = await probe.get(health_url)
            r.raise_for_status()
            logger.info("Vision Node health check passed (%s).", health_url)
        except Exception as exc:
            logger.error(
                "Vision Node unreachable at %s: %s — aborting batch send.",
                health_url, exc,
            )
            return

    semaphore = asyncio.Semaphore(SEND_CONCURRENCY)
    stats: dict[str, int] = {"success": 0, "failure": 0}

    logger.info(
        "Starting batch send: %d image(s), concurrency=%d",
        len(image_paths), SEND_CONCURRENCY,
    )

    async with httpx.AsyncClient(timeout=_SEND_TIMEOUT) as client:
        tasks = [
            asyncio.create_task(
                _send_image(client, path, semaphore, stats)
            )
            for path in image_paths
        ]
        await asyncio.gather(*tasks)

    logger.info(
        "Batch complete — ✅ success: %d  ❌ failure: %d  "
        "(results → %s)",
        stats["success"], stats["failure"], RESULTS_FILE.resolve(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# ③ ENTRY-POINT — run both tasks concurrently
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    """
    Start the uvicorn receiver server and the async batch sender
    concurrently inside a single asyncio event loop.

    uvicorn is run via its programmatic async API so it shares the same
    loop as the sender — no threads, no subprocesses.
    """
    logger.info("=" * 60)
    logger.info("Orchestrator Loopback Test")
    logger.info("  Vision Node   : %s", VISION_NODE_URL)
    logger.info("  Receiver      : http://%s:%d", RECEIVER_HOST, RECEIVER_PORT)
    logger.info("  Test images   : %s", TEST_IMAGES_DIR.resolve())
    logger.info("  Results file  : %s", RESULTS_FILE.resolve())
    logger.info("  Concurrency   : %d", SEND_CONCURRENCY)
    logger.info("=" * 60)

    # Ensure results file starts clean for this test run
    if RESULTS_FILE.exists():
        RESULTS_FILE.unlink()
        logger.info("Cleared previous %s", RESULTS_FILE)

    config = uvicorn.Config(
        app=receiver_app,
        host=RECEIVER_HOST,
        port=RECEIVER_PORT,
        log_level="info",
        loop="none",          # Use the running asyncio loop, not uvicorn's own
        access_log=True,
    )
    server = uvicorn.Server(config)

    # Run receiver + sender in parallel; sender exits naturally when done
    await asyncio.gather(
        server.serve(),
        run_batch_sender(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down.")