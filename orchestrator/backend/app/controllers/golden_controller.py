"""
Golden Source Controller — Workflow A (PRODUCER).

POST /api/v1/golden/upload
---------------------------
Accepts a raw video file from a PRODUCER, creates an Asset record
(is_golden=True, status='processing'), and asynchronously forwards
the file to the M2 Extractor Node for FFmpeg frame extraction.

The endpoint returns the asset_id immediately — the caller does not
wait for extraction to complete.  Progress is tracked via:
  GET /api/v1/assets/{asset_id}/status

Retry Policy
------------
Uses tenacity with exponential backoff (3 attempts, 2-8 s delay) on
5xx responses from the Extractor.  If all retries are exhausted, the
asset status is updated to 'failed' and a 502 is returned.

Idempotency
-----------
Each upload always creates a new Asset row.  There is no filename
deduplication — the PRODUCER is responsible for not re-uploading.
If duplicate detection is required, add a SHA-256 column to `assets`
and check it here before inserting.
"""

from __future__ import annotations

import asyncio
import uuid
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
import logging

from app.config import settings
from app.core.auth import get_trace_id, require_producer
from app.core.database import get_db
from app.core.logger import get_logger
from app.models.db_models import Asset
from app.models.schemas import UploadResponse

logger = get_logger("sourcegraph.golden")

router = APIRouter(prefix="/api/v1/golden", tags=["Golden Source — PRODUCER"])


# ── Retry-decorated extractor forwarding ────────────────────────────────

async def _forward_to_extractor(
    asset_id: UUID,
    filename: str,
    file_bytes: bytes,
    trace_id: str,
) -> None:
    """
    POST the raw video bytes to the M2 Extractor.

    Tells the Extractor:
      - `packet_id`  — so it can embed this ID in every webhook it fires
      - `is_golden`  — so the Extractor knows this is a reference video
      - `callback_url` — Orchestrator webhook endpoint for vector delivery

    Retry: 3 attempts, exponential backoff 2→4→8 s.
    On permanent failure: caller updates asset status to 'failed'.
    """

    callback_url = f"http://{settings.tailscale_ip}:{8000}/api/v1/webhooks/vector"
    complete_url = f"http://{settings.tailscale_ip}:{8000}/api/v1/webhooks/complete"

    attempt = 0
    last_exc: Exception | None = None

    for attempt in range(1, settings.extractor_max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.extractor_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.extractor_url}/extract",
                    files={"video": (filename, file_bytes, "video/mp4")},
                    data={
                        "packet_id": str(asset_id),
                        "is_golden": "true",
                        "callback_url": callback_url,
                        "complete_url": complete_url,
                        "trace_id": trace_id,
                    },
                    headers={"X-Webhook-Secret": settings.webhook_secret},
                )
                response.raise_for_status()
                logger.info(
                    f"[GOLDEN] ✅ Forwarded to extractor "
                    f"asset={asset_id} attempt={attempt} trace={trace_id}"
                )
                return

        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_exc = exc
            wait = 2 ** attempt  # 2, 4, 8 s
            logger.warning(
                f"[GOLDEN] ⚠ Extractor attempt {attempt}/{settings.extractor_max_retries} "
                f"failed: {exc} — retrying in {wait}s  asset={asset_id} trace={trace_id}"
            )
            if attempt < settings.extractor_max_retries:
                await asyncio.sleep(wait)

    # All retries exhausted — raise so the caller can mark asset as failed
    raise RuntimeError(
        f"Extractor unreachable after {settings.extractor_max_retries} attempts: {last_exc}"
    )


async def _forward_and_update(
    asset_id: UUID,
    filename: str,
    file_bytes: bytes,
    trace_id: str,
) -> None:
    """
    Background task: forward file and handle persistent failure by
    updating asset.status → 'failed'.
    """
    from app.core.database import AsyncSessionLocal

    try:
        await _forward_to_extractor(asset_id, filename, file_bytes, trace_id)
    except Exception as exc:
        logger.error(
            f"[GOLDEN] ❌ Permanent extractor failure "
            f"asset={asset_id} error={exc} trace={trace_id}"
        )
        # Update asset status to 'failed' in a fresh session
        async with AsyncSessionLocal() as db:
            try:
                await db.execute(
                    update(Asset)
                    .where(Asset.id == asset_id)
                    .values(status="failed")
                )
                await db.commit()
            except Exception as db_exc:
                logger.error(
                    f"[GOLDEN] Failed to mark asset as failed: {db_exc} trace={trace_id}"
                )


# ── Route ────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register a protected Golden Source video (PRODUCER only)",
)
async def upload_golden_source(
    request: Request,
    file: UploadFile = File(..., description="Raw video file (.mp4, .mov, etc.)"),
    role: str = Depends(require_producer),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """
    Workflow A — PRODUCER

    1. Validate file presence.
    2. Create Asset(is_golden=True, status='processing') in PostgreSQL.
    3. Read file bytes and fire-and-forget to M2 Extractor.
    4. Return asset_id immediately — caller polls /status for progress.
    """
    trace_id = get_trace_id(request)

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )

    logger.info(
        f"[GOLDEN] 📥 Upload received: file={file.filename} "
        f"role={role} trace={trace_id}"
    )

    # ── Persist asset record ─────────────────────────────────────────────
    asset = Asset(
        filename=file.filename,
        is_golden=True,
        status="processing",
    )
    db.add(asset)

    try:
        await db.commit()
        await db.refresh(asset)
    except Exception as exc:
        await db.rollback()
        logger.error(
            f"[GOLDEN] DB insert failed: {exc} trace={trace_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register asset: {exc}",
        )

    asset_id = asset.id
    logger.info(
        f"[GOLDEN] ✅ Asset created: id={asset_id} "
        f"file={file.filename} trace={trace_id}"
    )

    # ── Read file bytes then fire-and-forget ─────────────────────────────
    file_bytes = await file.read()

    asyncio.create_task(
        _forward_and_update(asset_id, file.filename, file_bytes, trace_id)
    )

    return UploadResponse(
        asset_id=asset_id,
        filename=file.filename,
        is_golden=True,
        status="processing",
        message="Asset registered. Extraction job dispatched to M2 node.",
        trace_id=trace_id,
    )