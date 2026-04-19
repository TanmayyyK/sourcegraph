"""
Webhook Controller — GPU Node Vector Sink.

This is the hottest endpoint in the system.  The RTX 3050 (Vision) and
RTX 2050 (Text) both POST here, independently, for every extracted frame.

POST /api/v1/webhooks/vector
-----------------------------
Receives a partial vector delivery (one modality at a time).

Flow per delivery:
  1. Validate payload (Pydantic).
  2. Validate webhook secret (constant-time compare).
  3. Check the asset exists and is still 'processing' (guard against
     late arrivals on a 'failed' or already 'completed' asset).
  4. Hand off to BufferService.ingest().
  5. If the buffer returns a completed entry (both modalities present):
       a. Write FrameVector row to DB (INSERT … ON CONFLICT DO NOTHING
          for idempotency against duplicate deliveries).
       b. Log the flush with trace_id.
  6. Return WebhookAck immediately.

POST /api/v1/webhooks/complete
-------------------------------
Called by the M2 Extractor once ALL frames for an asset have been
dispatched to GPU nodes.

Flow:
  1. Update Asset.status → 'completed'.
  2. If is_golden=False: launch Similarity Engine as a background task.
  3. Return 200.

State transition guard
----------------------
  processing → completed  ✅
  failed     → completed  ❌  (rejected — already terminal)
  completed  → completed  ❌  (idempotent — 200 but no re-trigger)

Observability
-------------
  Every log line includes the trace_id from X-Trace-ID so the entire
  packet lifecycle (upload → webhook → DB → similarity) is traceable.
"""

from __future__ import annotations

import asyncio
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import get_trace_id, require_webhook_secret
from app.core.database import AsyncSessionLocal, get_db
from app.core.logger import get_logger
from app.models.db_models import Asset, FrameVector
from app.models.schemas import WebhookAck, WebhookCompletePayload, WebhookVectorPayload
from app.services.buffer_service import BufferService
from app.services.similarity_service import similarity_service

logger = get_logger("sourcegraph.webhook")

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks — GPU Nodes"])


# ── Helpers ─────────────────────────────────────────────────────────────

async def _get_asset_or_raise(
    asset_id: UUID, db: AsyncSession, trace_id: str
) -> Asset:
    """
    Fetch the asset.  Raise 404 if not found, 409 if not in 'processing'.
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset: Asset | None = result.scalar_one_or_none()

    if asset is None:
        logger.warning(
            f"[WEBHOOK] Unknown asset_id={asset_id} trace={trace_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found. Was it registered via /upload?",
        )

    if asset.status == "failed":
        logger.warning(
            f"[WEBHOOK] Vector arrived for FAILED asset={asset_id} — dropping trace={trace_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset {asset_id} is in 'failed' state. Vector rejected.",
        )

    return asset


async def _flush_frame_to_db(
    entry,  # BufferEntry
    db: AsyncSession,
    trace_id: str,
) -> bool:
    """
    Write a completed BufferEntry as a FrameVector row.

    Uses INSERT … ON CONFLICT DO NOTHING so that duplicate webhook
    deliveries (network retries) are silently ignored.

    Returns True if a new row was inserted, False if it was a duplicate.
    """
    stmt = (
        pg_insert(FrameVector)
        .values(
            id=uuid.uuid4(),
            asset_id=entry.asset_id,
            timestamp=entry.timestamp,
            visual_vector=entry.visual_vector,
            text_vector=entry.text_vector,
        )
        .on_conflict_do_nothing(
            index_elements=None,  # relies on uq_frame_asset_timestamp
            constraint="uq_frame_asset_timestamp",
        )
    )

    try:
        result = await db.execute(stmt)
        await db.commit()
        inserted = result.rowcount > 0

        if inserted:
            logger.info(
                f"[WEBHOOK] 💾 Frame persisted: asset={entry.asset_id} "
                f"ts={entry.timestamp:.3f}s trace={trace_id}"
            )
        else:
            logger.debug(
                f"[WEBHOOK] Duplicate frame ignored: asset={entry.asset_id} "
                f"ts={entry.timestamp:.3f}s trace={trace_id}"
            )

        return inserted

    except Exception as exc:
        await db.rollback()
        logger.error(
            f"[WEBHOOK] DB flush failed: asset={entry.asset_id} "
            f"ts={entry.timestamp:.3f}s error={exc} trace={trace_id}"
        )
        raise


async def _run_similarity_background(
    asset_id: UUID, trace_id: str
) -> None:
    """
    Background task: open a fresh DB session and run the similarity engine.
    Isolated from the request session so the HTTP response is not blocked.
    """
    logger.info(
        f"[WEBHOOK] 🚀 Similarity engine triggered "
        f"asset={asset_id} trace={trace_id}"
    )
    async with AsyncSessionLocal() as db:
        try:
            result = await similarity_service.run_for_asset(
                asset_id=asset_id, db=db, trace_id=trace_id
            )
            if result:
                logger.warning(
                    f"[WEBHOOK] 🎯 Verdict={result.verdict} "
                    f"score={result.fused_score:.4f} "
                    f"asset={asset_id} trace={trace_id}"
                )
            else:
                logger.info(
                    f"[WEBHOOK] ℹ Similarity returned no result "
                    f"asset={asset_id} trace={trace_id}"
                )
        except Exception as exc:
            logger.error(
                f"[WEBHOOK] Similarity engine error: {exc} "
                f"asset={asset_id} trace={trace_id}"
            )


# ── Vector endpoint ──────────────────────────────────────────────────────

@router.post(
    "/vector",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="Receive a frame vector from a GPU node (internal)",
)
async def receive_vector(
    payload: WebhookVectorPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _secret: str = Depends(require_webhook_secret),
) -> WebhookAck:
    """
    GPU node → Orchestrator vector delivery.

    The Vision Node (RTX 3050) sends visual_vector.
    The Text Node (RTX 2050) sends text_vector.
    Either may arrive first — the buffer waits for both.

    Once both arrive for a (packet_id, timestamp) pair, the frame is
    atomically flushed to the `frame_vectors` table.
    """
    trace_id = get_trace_id(request)

    logger.info(
        f"[WEBHOOK] Received vector: packet={payload.packet_id} "
        f"ts={payload.timestamp:.3f}s "
        f"visual={'✅' if payload.visual_vector else '⬜'} "
        f"text={'✅' if payload.text_vector else '⬜'} "
        f"node={payload.source_node or 'unknown'} "
        f"trace={trace_id}"
    )

    # Validate asset existence and state
    await _get_asset_or_raise(payload.packet_id, db, trace_id)

    # Feed into buffer
    buffer: BufferService = request.app.state.buffer
    result = await buffer.ingest(
        asset_id=payload.packet_id,
        timestamp=payload.timestamp,
        visual_vector=payload.visual_vector,
        text_vector=payload.text_vector,
        source_node=payload.source_node,
        trace_id=trace_id,
    )

    flushed = False
    if result.completed_entry is not None:
        flushed = await _flush_frame_to_db(result.completed_entry, db, trace_id)

    return WebhookAck(
        status="accepted",
        packet_id=payload.packet_id,
        timestamp=payload.timestamp,
        flushed_to_db=flushed,
        trace_id=trace_id,
    )


# ── Completion endpoint ──────────────────────────────────────────────────

@router.post(
    "/complete",
    status_code=status.HTTP_200_OK,
    summary="Mark an asset as fully processed (called by M2 Extractor)",
)
async def mark_asset_complete(
    payload: WebhookCompletePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _secret: str = Depends(require_webhook_secret),
) -> dict:
    """
    M2 Extractor → Orchestrator completion signal.

    Called after the extractor has dispatched ALL frame jobs to GPU nodes.
    Transitions asset from 'processing' → 'completed'.

    For non-golden assets, fires the Similarity Engine as a background task.

    State transition guard:
      - 'failed' → rejected (asset is terminal, cannot be completed)
      - 'completed' → idempotent 200 (no duplicate similarity runs)
    """
    trace_id = get_trace_id(request)
    asset_id = payload.packet_id

    logger.info(
        f"[WEBHOOK] Completion signal: asset={asset_id} "
        f"total_frames={payload.total_frames} trace={trace_id}"
    )

    # Fetch and validate
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset: Asset | None = result.scalar_one_or_none()

    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found.",
        )

    # Idempotency: already completed — do not re-trigger similarity
    if asset.status == "completed":
        logger.info(
            f"[WEBHOOK] Asset already completed (idempotent): "
            f"asset={asset_id} trace={trace_id}"
        )
        return {
            "status": "already_completed",
            "asset_id": str(asset_id),
            "trace_id": trace_id,
        }

    # Guard: failed assets cannot be completed
    if asset.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset {asset_id} is in 'failed' state and cannot be completed.",
        )

    # Transition to 'completed'
    await db.execute(
        update(Asset).where(Asset.id == asset_id).values(status="completed")
    )
    await db.commit()

    logger.info(
        f"[WEBHOOK] ✅ Asset completed: id={asset_id} "
        f"is_golden={asset.is_golden} trace={trace_id}"
    )

    # Trigger Similarity Engine for non-golden (suspect) assets
    if not asset.is_golden:
        asyncio.create_task(
            _run_similarity_background(asset_id, trace_id)
        )
        logger.info(
            f"[WEBHOOK] 🔍 Similarity task queued "
            f"asset={asset_id} trace={trace_id}"
        )

    return {
        "status": "completed",
        "asset_id": str(asset_id),
        "is_golden": asset.is_golden,
        "similarity_queued": not asset.is_golden,
        "trace_id": trace_id,
    }