"""
Webhook Controller — GPU Node Vector Sink  (v2, Polymorphic Feeder Edition)
===========================================================================

Endpoints
─────────
  POST /api/v1/webhooks/vector          Legacy GPU-node vector delivery
                                         (ARGUS Vision / HERMES Text)
  POST /api/v1/webhooks/complete        Legacy ATLAS completion signal
  POST /api/v1/webhooks/feeder          NEW — polymorphic event stream from
                                         simulate_ml_stream.py

/feeder  Payload routing
─────────────────────────
  system_ping            → log node health map; no DB write
  frame_vision           → INSERT into frame_embeddings (ARGUS / RTX 3050)
  frame_text             → INSERT into frame_vision_metadata (HERMES / RTX 2050)
  vision_final_summary   → log GPU-node completion metrics for Vision node (ARGUS)
  text_final_summary     → log GPU-node completion metrics for Text node (HERMES)
  pipeline_final_summary → authoritative "all frames dispatched" signal (ATLAS);
                           transitions Asset → 'completed' and optionally
                           fires the Similarity Engine

Async frame handling
─────────────────────
  frame_vision and frame_text arrive concurrently for the same
  (packet_id, timestamp).  Each is dispatched as an independent asyncio
  background task (_handle_frame_vision / _handle_frame_text) so
  the HTTP response is never blocked by DB I/O.  Both tasks open their own
  AsyncSessionLocal sessions, giving correct isolation without
  connection-pool contention.

packet_id → UUID resolution
─────────────────────────────
  The feeder simulator sends opaque hex tokens (e.g. "ingest_a1b2c3d4")
  as packet_id.  The two staging tables (frame_vision_metadata,
  frame_embeddings) store the raw string in packet_id and populate
  asset_id only when the token is a valid UUID.  The unique constraint is
  on (packet_id, timestamp, source_node) so idempotency is always
  guaranteed regardless of resolution outcome.

  pipeline_final_summary requires a real UUID for the asset state
  transition — it returns 422 with a clear message if the token is not
  a UUID so operators know exactly what to fix.

State-transition guard  (asset.status)
────────────────────────────────────────
  processing  → completed  ✅  (normal path)
  completed   → completed  ✅  (idempotent — 200, no re-trigger)
  failed      → completed  ❌  (409 — terminal state, rejected)

Observability
─────────────
  Every log line carries trace_id sourced from X-Trace-ID so the full
  lifecycle (upload → webhook → DB → similarity) is traceable end-to-end.
"""

from __future__ import annotations

import asyncio
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_trace_id, require_webhook_secret
from app.core.database import AsyncSessionLocal, get_db
from app.core.logger import get_logger
from app.models.db_models import (
    Asset,
    AudioSegment,
    FrameEmbedding,
    FrameVector,
    FrameVisionMetadata,
)
from app.models.schemas import (
    # Legacy schemas
    WebhookAck,
    WebhookCompletePayload,
    WebhookVectorPayload,
    # New polymorphic schemas
    FeederPayload,
    FrameTextPayload,
    FrameVisionPayload,
    PipelineFinalSummaryPayload,
    SystemPingPayload,
    TextFinalSummaryPayload,
    VisionFinalSummaryPayload,
    AudioSummaryPacket,
)
from app.services.auditor_client import process_asset_with_auditor
from app.controllers.feed_controller import NODE_LAST_SEEN
import time

logger = get_logger("sourcegraph.webhook")

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks — GPU Nodes"])


# ══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════════════════════════════════════

async def _get_asset_or_raise(
    asset_id: UUID,
    db: AsyncSession,
    trace_id: str,
) -> Asset:
    """
    Fetch an Asset row by PK.

    Raises
    ──────
    404  asset not found
    409  asset.status == 'failed'  (terminal — cannot accept new events)
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
            f"[WEBHOOK] Event rejected — asset is in terminal FAILED state: "
            f"asset={asset_id} trace={trace_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Asset {asset_id} is in 'failed' state. "
                "No further events will be accepted."
            ),
        )

    return asset


async def _flush_frame_to_db(
    entry,          # BufferEntry — typed loosely to avoid circular import
    db: AsyncSession,
    trace_id: str,
) -> bool:
    """
    Persist a fully-paired BufferEntry as a FrameVector row.

    Uses INSERT … ON CONFLICT DO NOTHING keyed on (asset_id, timestamp)
    so duplicate deliveries from network retries are silently swallowed.

    Returns True on a fresh insert, False on a duplicate.
    """
    asset = await _get_asset_or_raise(entry.asset_id, db, trace_id)
    is_temporary = not asset.is_golden

    stmt = (
        pg_insert(FrameVector)
        .values(
            id=uuid.uuid4(),
            asset_id=entry.asset_id,
            timestamp=entry.timestamp,
            visual_vector=entry.visual_vector,
            text_vector=entry.text_vector,
            is_temporary=is_temporary,
        )
        .on_conflict_do_nothing(index_elements=["asset_id", "timestamp"])
    )

    try:
        result = await db.execute(stmt)
        await db.commit()
        inserted: bool = result.rowcount > 0

        if inserted:
            logger.info(
                f"[WEBHOOK] 💾 Frame persisted: asset={entry.asset_id} "
                f"ts={entry.timestamp:.3f}s temporary={is_temporary} trace={trace_id}"
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
            f"ts={entry.timestamp:.3f}s error={exc!r} trace={trace_id}"
        )
        raise


async def _run_auditor_background(asset_id: UUID, is_golden: bool, trace_id: str) -> None:
    """
    Background task: open a *fresh* DB session isolated from the request
    session, then run the ML auditor engine.
    """
    logger.info(
        f"[WEBHOOK] 🚀 Auditor engine triggered "
        f"asset={asset_id} is_golden={is_golden} trace={trace_id}"
    )
    async with AsyncSessionLocal() as db:
        try:
            success = await process_asset_with_auditor(
                asset_id=asset_id, is_golden=is_golden, db=db, trace_id=trace_id
            )
            if success:
                logger.info(
                    f"[WEBHOOK] ✅ Auditor engine processed successfully "
                    f"asset={asset_id} trace={trace_id}"
                )
            else:
                logger.warning(
                    f"[WEBHOOK] ⚠ Auditor engine reported failure or no vectors "
                    f"asset={asset_id} trace={trace_id}"
                )
        except Exception as exc:
            logger.error(
                f"[WEBHOOK] Auditor engine error: {exc!r} "
                f"asset={asset_id} trace={trace_id}"
            )


async def _maybe_dispatch_auditor(
    asset_id: UUID,
    db: AsyncSession,
    trace_id: str,
) -> bool:
    """
    Atomically dispatch the Auditor exactly once, and only after both
    lifecycle barriers are closed for this asset.

    The UPDATE predicate is the lock: if either summary is missing or another
    request already dispatched the Auditor, rowcount is zero and no task starts.
    """
    stmt = (
        update(Asset)
        .where(
            Asset.id == asset_id,
            Asset.audio_summary_completed.is_(True),
            Asset.pipeline_summary_completed.is_(True),
            Asset.auditor_dispatched.is_(False),
        )
        .values(status="completed", auditor_dispatched=True)
        .returning(Asset.is_golden)
    )
    result = await db.execute(stmt)
    row = result.first()
    await db.commit()

    if row is None:
        logger.info(
            f"[WEBHOOK] Auditor dispatch blocked until both summaries complete "
            f"or already dispatched: asset={asset_id} trace={trace_id}"
        )
        return False

    is_golden = bool(row[0])
    asyncio.create_task(
        _run_auditor_background(asset_id, is_golden, trace_id),
        name=f"auditor:{asset_id}",
    )
    logger.info(
        f"[WEBHOOK] 🔍 Auditor task queued after lifecycle lock "
        f"asset={asset_id} is_golden={is_golden} trace={trace_id}"
    )
    return True


# ══════════════════════════════════════════════════════════════════════════════
# Feeder background tasks
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_asset_id(packet_id: str, trace_id: str, context: str) -> UUID | None:
    """
    Attempt to coerce the feeder's opaque packet_id string to a UUID.

    Returns the UUID on success, or None when the token is a simulator
    hex token (e.g. "ingest_a1b2c3d4").  The None case is valid —
    asset_id will be NULL in the staging row and can be back-filled
    once the simulator is updated to send real UUIDs.
    """
    try:
        return UUID(packet_id)
    except ValueError:
        logger.debug(
            f"[FEEDER] {context}: packet_id='{packet_id}' is not a UUID — "
            f"asset_id will be NULL in staging row. "
            f"Update simulator to send real UUIDs. trace={trace_id}"
        )
        return None


async def _handle_frame_vision(
    payload: FrameVisionPayload,
    trace_id: str,
) -> None:
    """
    Background task — persist vision-frame embeddings from ARGUS (RTX 3050)
    into the `frame_embeddings` staging table.

    Idempotency: (packet_id, timestamp, source_node) UNIQUE constraint
    ensures duplicate deliveries are silently discarded.

    asset_id is populated only when payload.packet_id is a valid UUID.
    """
    asset_id_val: UUID | None = _resolve_asset_id(
        payload.packet_id, trace_id, "frame_vision"
    )

    async with AsyncSessionLocal() as db:
        try:
            asset_is_golden: bool | None = None
            if asset_id_val is not None:
                asset_is_golden = await db.scalar(
                    select(Asset.is_golden).where(Asset.id == asset_id_val)
                )
                if asset_is_golden is None:
                    logger.warning(
                        f"[{payload.source_node}] frame_vision ignored for frame_vectors — "
                        f"Asset {asset_id_val} not found. trace={trace_id}"
                    )
                    asset_id_val = None

            # ── Dual-vector ingestion into frame_vectors (UPSERT merge) ──
            # Requires asset_id_val (frame_vectors.asset_id is NOT NULL).
            if asset_id_val is not None:
                # Task 1: Explicitly transition status to 'analyzing' on first frame
                await db.execute(
                    update(Asset)
                    .where(Asset.id == asset_id_val, Asset.status == "processing")
                    .values(status="analyzing")
                )
                
                is_temporary = not bool(asset_is_golden)
                insert_stmt = (
                    pg_insert(FrameVector)
                    .values(
                        id=uuid.uuid4(),
                        asset_id=asset_id_val,
                        timestamp=payload.timestamp,
                        visual_vector=payload.visual_vector,
                        is_temporary=is_temporary,
                    )
                )
                upsert_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=["asset_id", "timestamp"],
                    set_={
                        "visual_vector": insert_stmt.excluded.visual_vector,
                        "is_temporary": insert_stmt.excluded.is_temporary,
                    },
                )
                await db.execute(upsert_stmt)

            stmt = (
                pg_insert(FrameEmbedding)
                .values(
                    id=uuid.uuid4(),
                    packet_id=payload.packet_id,
                    asset_id=asset_id_val,
                    timestamp=payload.timestamp,
                    source_node=payload.source_node,
                    vector=payload.visual_vector,
                )
                .on_conflict_do_nothing(
                    index_elements=["packet_id", "timestamp", "source_node"]
                )
            )
            res = await db.execute(stmt)
            await db.commit()
            
            if res.rowcount > 0:
                 logger.debug(f"[{payload.source_node}] 💾 Staging embedding persisted: ts={payload.timestamp:.3f}s")
        except Exception as exc:
            await db.rollback()
            logger.error(
                f"[{payload.source_node}] frame_vision persist error: "
                f"packet={payload.packet_id} ts={payload.timestamp} "
                f"error={exc!r} trace={trace_id}"
            )


async def _handle_frame_text(
    payload: FrameTextPayload,
    trace_id: str,
) -> None:
    """
    Background task — persist the text metadata from HERMES (RTX 2050)
    into the `frame_vision_metadata` staging table.

    The metadata counts (chunks/boxes) are passed along without validation.

    Idempotency: (packet_id, timestamp, source_node) UNIQUE constraint
    ensures duplicate deliveries are silently discarded.

    asset_id is populated only when payload.packet_id is a valid UUID.
    """
    asset_id_val: UUID | None = _resolve_asset_id(
        payload.packet_id, trace_id, "frame_text"
    )

    async with AsyncSessionLocal() as db:
        try:
            asset_is_golden: bool | None = None
            if asset_id_val is not None:
                asset_is_golden = await db.scalar(
                    select(Asset.is_golden).where(Asset.id == asset_id_val)
                )
                if asset_is_golden is None:
                    logger.warning(
                        f"[{payload.source_node}] frame_text ignored for frame_vectors — "
                        f"Asset {asset_id_val} not found. trace={trace_id}"
                    )
                    asset_id_val = None

            # ── Dual-vector ingestion into frame_vectors (UPSERT merge) ──
            if asset_id_val is not None:
                # Task 1: Explicitly transition status to 'analyzing' on first frame
                await db.execute(
                    update(Asset)
                    .where(Asset.id == asset_id_val, Asset.status == "processing")
                    .values(status="analyzing")
                )
                
                is_temporary = not bool(asset_is_golden)
                insert_stmt = (
                    pg_insert(FrameVector)
                    .values(
                        id=uuid.uuid4(),
                        asset_id=asset_id_val,
                        timestamp=payload.timestamp,
                        text_vector=payload.text_vector,
                        is_temporary=is_temporary,
                    )
                )
                upsert_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=["asset_id", "timestamp"],
                    set_={
                        "text_vector": insert_stmt.excluded.text_vector,
                        "is_temporary": insert_stmt.excluded.is_temporary,
                    },
                )
                await db.execute(upsert_stmt)

            stmt = (
                pg_insert(FrameVisionMetadata)
                .values(
                    id=uuid.uuid4(),
                    packet_id=payload.packet_id,
                    asset_id=asset_id_val,
                    timestamp=payload.timestamp,
                    source_node=payload.source_node,
                    chunks_extracted=payload.chunks_extracted,
                    boxes_mapped=payload.boxes_mapped,
                    ocr_text=payload.ocr_text,
                )
                .on_conflict_do_nothing(
                    index_elements=["packet_id", "timestamp", "source_node"]
                )
            )
            res = await db.execute(stmt)
            await db.commit()
            
            if res.rowcount > 0:
                logger.debug(f"[{payload.source_node}] 💾 Staging metadata persisted: ts={payload.timestamp:.3f}s")
        except Exception as exc:
            await db.rollback()
            logger.error(f"[{payload.source_node}] Metadata staging error: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Feeder event dispatchers  (one per payload type)
# ══════════════════════════════════════════════════════════════════════════════

def _dispatch_system_ping(
    payload: SystemPingPayload,
    trace_id: str,
) -> dict:
    """
    Log node health snapshot.  No DB side-effect — purely observability.
    """
    # Only flag explicit error statuses. 'UNKNOWN' or 'OFFLINE' are acceptable
    # for nodes that only report their own local health.
    unhealthy = [
        svc
        for svc, st in payload.services.model_dump().items()
        if st.upper() in ("ERR", "ERROR", "FAILED")
    ]

    if unhealthy:
        logger.warning(
            f"[FEEDER] ⚠ System ping — degraded services={unhealthy} "
            f"nodes_online={payload.nodes_online} "
            f"packet={payload.packet_id} trace={trace_id}"
        )
    else:
        logger.info(
            f"[FEEDER] 💚 System ping — OK (Nodes: {payload.nodes_online}) "
            f"packet={payload.packet_id} trace={trace_id}"
        )

    # ── Update Dashboard Heartbeats (CONTRACT ALIGNMENT) ──
    # Map the service names from the ping payload to the keys the 
    # Command Centre dashboard uses for its health lights.
    current_time = time.time()
    for svc, status in payload.services.model_dump().items():
        if status.upper() == "OK" and svc in NODE_LAST_SEEN:
            NODE_LAST_SEEN[svc] = current_time

    return {
        "status": "acknowledged",
        "type": payload.type,
        "nodes_online": payload.nodes_online,
        "degraded_services": unhealthy,
        "trace_id": trace_id,
    }


# ── Source-node → dashboard-key mapping ──────────────────────────────────
# When ANY payload arrives from a live node, update its heartbeat so
# the Command Centre shows it as green/OK.
_SOURCE_TO_DASHBOARD_KEY: dict[str, str] = {
    "ml_vision": "vision_engine",
    "ml_context": "text_processor",
    "ATLAS": "orchestrator",
}

def _touch_node_heartbeat(source_node: str) -> None:
    """Update NODE_LAST_SEEN for the source node if it maps to a dashboard key."""
    key = _SOURCE_TO_DASHBOARD_KEY.get(source_node)
    if key:
        NODE_LAST_SEEN[key] = time.time()


def _dispatch_frame_vision(
    payload: FrameVisionPayload,
    trace_id: str,
) -> dict:
    """
    Fire-and-forget: schedule the DB write as a background task so the
    HTTP response is returned immediately without blocking on I/O.
    """
    _touch_node_heartbeat(payload.source_node)

    asyncio.create_task(
        _handle_frame_vision(payload, trace_id),
        name=f"frame_vision:{payload.packet_id}:{payload.timestamp}",
    )

    logger.debug(
        f"[{payload.source_node}] frame_vision queued: "
        f"packet={payload.packet_id} ts={payload.timestamp:.3f}s "
        f"node={payload.source_node} trace={trace_id}"
    )

    return {
        "status": "accepted",
        "type": payload.type,
        "timestamp": payload.timestamp,
        "source_node": payload.source_node,
        "trace_id": trace_id,
    }


def _dispatch_frame_text(
    payload: FrameTextPayload,
    trace_id: str,
) -> dict:
    """
    Fire-and-forget: schedule the metadata persist as a background task.
    """
    _touch_node_heartbeat(payload.source_node)

    asyncio.create_task(
        _handle_frame_text(payload, trace_id),
        name=f"frame_text:{payload.packet_id}:{payload.timestamp}",
    )

    logger.debug(
        f"[{payload.source_node}] frame_text queued: "
        f"packet={payload.packet_id} ts={payload.timestamp:.3f}s "
        f"node={payload.source_node} trace={trace_id}"
    )

    return {
        "status": "accepted",
        "type": payload.type,
        "timestamp": payload.timestamp,
        "source_node": payload.source_node,
        "chunks_extracted": payload.chunks_extracted,
        "trace_id": trace_id,
    }


def _dispatch_vision_final_summary(
    payload: VisionFinalSummaryPayload,
    trace_id: str,
) -> dict:
    """
    Log Vision-node completion metrics.
    No asset state transition — that is owned exclusively by
    pipeline_final_summary to prevent race conditions.
    """
    _touch_node_heartbeat(payload.source_node)

    m = payload.metrics
    logger.info(
        f"[{payload.source_node}] 📊 Vision summary from {payload.source_node}: "
        f"embeddings={m.vector_embeddings} "
        f"dimensionality='{m.dimensionality}' "
        f"index_status='{m.index_status}' "
        f"node_time={m.node_time_s:.2f}s "
        f"packet={payload.packet_id} trace={trace_id}"
    )

    # Persist metrics to Asset table (backgrounded)
    asset_id_val = _resolve_asset_id(payload.packet_id, trace_id, "vision_summary")
    if asset_id_val:
        async def _save():
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Asset)
                    .where(Asset.id == asset_id_val)
                    .values(vision_latency_ms=int(m.node_time_s * 1000))
                )
                await db.commit()
        asyncio.create_task(_save(), name=f"vision_summary:{asset_id_val}")

    return {
        "status": "acknowledged",
        "type": payload.type,
        "source_node": payload.source_node,
        "metrics_recorded": True,
        "trace_id": trace_id,
    }


def _dispatch_text_final_summary(
    payload: TextFinalSummaryPayload,
    trace_id: str,
) -> dict:
    """
    Log Text-node completion metrics.
    Same metrics-only, no-state-change contract as _dispatch_vision_final_summary.
    """
    _touch_node_heartbeat(payload.source_node)

    m = payload.metrics
    logger.info(
        f"[{payload.source_node}] 📊 Text summary from {payload.source_node}: "
        f"ocr_chunks={m.ocr_text_chunks} "
        f"bounding_boxes={m.bounding_boxes_mapped} "
        f"node_time={m.node_time_s:.2f}s "
        f"packet={payload.packet_id} trace={trace_id}"
    )

    # Persist metrics to Asset table (backgrounded)
    asset_id_val = _resolve_asset_id(payload.packet_id, trace_id, "text_summary")
    if asset_id_val:
        async def _save():
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Asset)
                    .where(Asset.id == asset_id_val)
                    .values(text_latency_ms=int(m.node_time_s * 1000))
                )
                await db.commit()
        asyncio.create_task(_save(), name=f"text_summary:{asset_id_val}")

    return {
        "status": "acknowledged",
        "type": payload.type,
        "source_node": payload.source_node,
        "metrics_recorded": True,
        "trace_id": trace_id,
    }


async def _handle_audio_summary(
    payload: AudioSummaryPacket,
    trace_id: str,
) -> None:
    """
    Background task — persist audio segments and full transcript
    from the Vision Node.
    """
    asset_id_val: UUID | None = _resolve_asset_id(
        payload.packet_id, trace_id, "audio_final_summary"
    )
    if asset_id_val is None:
        logger.warning(
            f"[{payload.source_node}] Cannot process audio summary — "
            f"packet_id={payload.packet_id} is not a valid UUID. trace={trace_id}"
        )
        return

    async with AsyncSessionLocal() as db:
        try:
            # Verify asset exists
            asset = await db.scalar(select(Asset).where(Asset.id == asset_id_val))
            if not asset:
                logger.warning(
                    f"[{payload.source_node}] Audio summary ignored — "
                    f"Asset {asset_id_val} not found. trace={trace_id}"
                )
                return

            # Update asset with full transcript
            await db.execute(
                update(Asset)
                .where(Asset.id == asset_id_val)
                .values(
                    full_transcript=payload.full_script,
                    audio_summary_completed=True,
                )
            )

            # Insert audio segments using bulk insert pattern
            if payload.transcript:
                segments_data = [
                    {
                        "id": uuid.uuid4(),
                        "asset_id": asset_id_val,
                        "start_time": item.start,
                        "end_time": item.end,
                        "segment_text": item.text,
                    }
                    for item in payload.transcript
                ]
                await db.execute(pg_insert(AudioSegment), segments_data)

            logger.info(
                f"[{payload.source_node}] 💾 Audio summary persisted: "
                f"asset_id={asset_id_val} segments={len(payload.transcript)} "
                f"trace={trace_id}"
            )
            await _maybe_dispatch_auditor(asset_id_val, db, trace_id)
        except Exception as exc:
            await db.rollback()
            logger.error(
                f"[{payload.source_node}] audio_final_summary persist error: "
                f"packet={payload.packet_id} error={exc!r} trace={trace_id}"
            )


def _dispatch_audio_summary(
    payload: AudioSummaryPacket,
    trace_id: str,
) -> dict:
    """
    Fire-and-forget: schedule audio transcript persist as a background task.
    """
    _touch_node_heartbeat(payload.source_node)

    asyncio.create_task(
        _handle_audio_summary(payload, trace_id),
        name=f"audio_summary:{payload.packet_id}",
    )

    logger.debug(
        f"[{payload.source_node}] audio_final_summary queued: "
        f"packet={payload.packet_id} segments={len(payload.transcript)} trace={trace_id}"
    )

    return {
        "status": "accepted",
        "type": payload.type,
        "source_node": payload.source_node,
        "segments": len(payload.transcript),
        "trace_id": trace_id,
    }


async def _dispatch_pipeline_final_summary(
    payload: PipelineFinalSummaryPayload,
    db: AsyncSession,
    trace_id: str,
) -> dict:
    """
    Authoritative pipeline completion signal from Yogesh / M2 Extractor.

    This is the ONLY dispatcher that mutates Asset.status.  It mirrors the
    logic in mark_asset_complete exactly:
      • 422  — packet_id is not a valid UUID (simulator mode — fix simulator)
      • 404  — asset not found
      • 200  — already completed (idempotent, no re-trigger)
      • 409  — asset in 'failed' state (terminal)
      • 200  — transition processing → completed + optional similarity task

    Why this is awaited while frame dispatchers are fire-and-forget:
    The asset state transition (processing → completed) and the similarity
    task launch must be serialized against the request session to guarantee
    the commit() completes before the HTTP 200 is returned.  A race between
    the response and the similarity task reading a still-'processing' asset
    would cause the similarity engine to silently skip the job.
    """
    m = payload.metrics

    # ── packet_id → UUID (mandatory for state transition) ─────────────────
    try:
        asset_id = UUID(payload.packet_id)
    except ValueError:
        logger.error(
            f"[FEEDER] pipeline_final_summary requires a real UUID packet_id. "
            f"Received: '{payload.packet_id}'. "
            f"Update simulator to send real Asset UUIDs. trace={trace_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"packet_id '{payload.packet_id}' is not a valid UUID. "
                "The pipeline_final_summary handler requires a real Asset UUID "
                "to transition asset state. Update the simulator."
            ),
        )

    logger.info(
        f"[FEEDER] 🏁 Pipeline summary from {payload.source_node}: "
        f"total_frames={m.total_frames_extracted} "
        f"successful={m.successful_broadcasts} "
        f"failed={m.failed_broadcasts} "
        f"pipeline_time={m.total_pipeline_time_s:.2f}s "
        f"asset={asset_id} trace={trace_id}"
    )

    # Validate asset state via shared guard (raises 404 / 409 as appropriate)
    asset = await _get_asset_or_raise(asset_id, db, trace_id)

    # Idempotency — completed assets have already passed the lifecycle lock.
    if asset.status == "completed" and asset.auditor_dispatched:
        logger.info(
            f"[FEEDER] Asset already completed (idempotent): "
            f"asset={asset_id} trace={trace_id}"
        )
        return {
            "status": "already_completed",
            "type": payload.type,
            "asset_id": str(asset_id),
            "trace_id": trace_id,
        }

    # Mark only the pipeline side of the barrier. The Auditor is dispatched
    # by _maybe_dispatch_auditor after audio_final_summary is also durable.
    await db.execute(
        update(Asset)
        .where(Asset.id == asset_id)
        .values(pipeline_summary_completed=True)
    )

    logger.info(
        f"[FEEDER] ✅ Pipeline summary persisted: "
        f"asset={asset_id} is_golden={asset.is_golden} trace={trace_id}"
    )

    auditor_queued = await _maybe_dispatch_auditor(asset_id, db, trace_id)

    return {
        "status": "completed" if auditor_queued else "waiting_for_audio_summary",
        "type": payload.type,
        "asset_id": str(asset_id),
        "is_golden": asset.is_golden,
        "auditor_queued": auditor_queued,
        "frames_reported": m.total_frames_extracted,
        "trace_id": trace_id,
    }


# ══════════════════════════════════════════════════════════════════════════════
# /feeder  — polymorphic ingestion endpoint
# ══════════════════════════════════════════════════════════════════════════════

# Build the TypeAdapter once at module load — avoids re-constructing it on
# every request (TypeAdapter construction is not free in Pydantic v2).
_feeder_adapter: TypeAdapter[FeederPayload] = TypeAdapter(FeederPayload)


@router.post(
    "/feeder",
    status_code=status.HTTP_200_OK,
    summary="Polymorphic ML-node event ingestion (Data Feeder pipeline)",
)
async def feeder_ingest(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _secret: str = Depends(require_webhook_secret),
) -> dict:
    """
    Single entry-point for the entire Data Feeder event stream.

    Accepts all six payload shapes emitted by `simulate_ml_stream.py`.
    Pydantic's discriminated union parses the `type` field and returns a
    fully-typed model — the router dispatches to the appropriate handler.

    Why raw Request body instead of a typed `payload` parameter?
    ─────────────────────────────────────────────────────────────
    FastAPI resolves Annotated union types correctly, but catching
    ValidationError and returning an enriched 422 (listing all valid types)
    requires manual parsing.  The two extra lines are a worthwhile trade for
    a dramatically more debuggable error payload.
    """
    trace_id = get_trace_id(request)

    # ── 1. Parse body through the discriminated union ──────────────────────
    try:
        raw = await request.json()
        payload = _feeder_adapter.validate_python(raw)
    except ValidationError as exc:
        logger.warning(
            f"[FEEDER] Payload validation failed: errors={exc.errors()} "
            f"trace={trace_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Payload did not match any known feeder event type.",
                "valid_types": [
                    "system_ping",
                    "frame_vision",
                    "frame_text",
                    "vision_final_summary",
                    "text_final_summary",
                    "pipeline_final_summary",
                    "audio_final_summary",
                ],
                "validation_errors": exc.errors(),
            },
        )
    except Exception as exc:
        logger.error(
            f"[FEEDER] Malformed JSON body: error={exc!r} trace={trace_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be valid JSON.",
        )

    logger.debug(
        f"[FEEDER] Received event: type={payload.type} "
        f"packet={payload.packet_id} trace={trace_id}"
    )

    # ── 2. Dispatch ────────────────────────────────────────────────────────
    match payload:
        case SystemPingPayload():
            return _dispatch_system_ping(payload, trace_id)

        case FrameVisionPayload():
            return _dispatch_frame_vision(payload, trace_id)

        case FrameTextPayload():
            return _dispatch_frame_text(payload, trace_id)

        case VisionFinalSummaryPayload():
            return _dispatch_vision_final_summary(payload, trace_id)

        case TextFinalSummaryPayload():
            return _dispatch_text_final_summary(payload, trace_id)

        case AudioSummaryPacket():
            return _dispatch_audio_summary(payload, trace_id)

        case PipelineFinalSummaryPayload():
            # Awaited — drives DB state transition; must not be fire-and-forget
            return await _dispatch_pipeline_final_summary(payload, db, trace_id)

        case _:
            # Unreachable if FeederPayload union and dispatchers are in sync.
            # Guards against a future schema addition without a matching branch.
            logger.error(
                f"[FEEDER] Unhandled payload type={payload.type!r} "
                f"trace={trace_id} — add a dispatcher branch."
            )
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=(
                    f"Payload type '{payload.type}' has no registered handler. "
                    "This is a server-side configuration error."
                ),
            )


# ══════════════════════════════════════════════════════════════════════════════
# Legacy endpoints  (preserved — no changes to business logic)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/vector",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="[Legacy] Receive a frame vector from a GPU node (internal)",
)
async def receive_vector(
    payload: WebhookVectorPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _secret: str = Depends(require_webhook_secret),
) -> WebhookAck:
    """
    GPU node → Orchestrator vector delivery (pre-feeder architecture).

    The Vision Node (RTX 3050) sends visual_vector.
    The Text Node (RTX 2050) sends text_vector.
    Either may arrive first — this handler UPSERT-merges partial vectors
    directly into frame_vectors on (asset_id, timestamp).
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

    asset = await _get_asset_or_raise(payload.packet_id, db, trace_id)
    is_temporary = not asset.is_golden

    # Compatibility path for mixed deployments:
    # Some nodes may still POST text-only or visual-only payloads to /vector
    # while other nodes already use /feeder. We UPSERT directly so partial
    # vectors are merged in SQL (asset_id, timestamp) without TTL drops.
    if payload.visual_vector is None and payload.text_vector is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of visual_vector or text_vector is required.",
        )

    insert_stmt = (
        pg_insert(FrameVector)
        .values(
            id=uuid.uuid4(),
            asset_id=payload.packet_id,
            timestamp=payload.timestamp,
            visual_vector=payload.visual_vector,
            text_vector=payload.text_vector,
            is_temporary=is_temporary,
        )
    )

    set_map: dict[str, object] = {}
    if payload.visual_vector is not None:
        set_map["visual_vector"] = insert_stmt.excluded.visual_vector
    if payload.text_vector is not None:
        set_map["text_vector"] = insert_stmt.excluded.text_vector
    set_map["is_temporary"] = insert_stmt.excluded.is_temporary

    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=["asset_id", "timestamp"],
        set_=set_map,
    )

    try:
        await db.execute(upsert_stmt)

        # Preserve legacy response semantics:
        # flushed_to_db=True means both modalities are now present on the row.
        row = await db.execute(
            select(FrameVector.visual_vector, FrameVector.text_vector).where(
                FrameVector.asset_id == payload.packet_id,
                FrameVector.timestamp == payload.timestamp,
            )
        )
        stored = row.first()
        flushed = bool(
            stored
            and stored[0] is not None
            and stored[1] is not None
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error(
            f"[WEBHOOK] /vector UPSERT failed: asset={payload.packet_id} "
            f"ts={payload.timestamp:.3f}s error={exc!r} trace={trace_id}"
        )
        raise

    return WebhookAck(
        status="accepted",
        packet_id=payload.packet_id,
        timestamp=payload.timestamp,
        flushed_to_db=flushed,
        trace_id=trace_id,
    )


@router.post(
    "/complete",
    status_code=status.HTTP_200_OK,
    summary="[Legacy] Mark an asset as fully processed (called by M2 Extractor)",
)
async def mark_asset_complete(
    payload: WebhookCompletePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _secret: str = Depends(require_webhook_secret),
) -> dict:
    """
    M2 Extractor → Orchestrator completion signal (pre-feeder architecture).

    Transitions asset from 'processing' → 'completed'.
    For non-golden assets, fires the Similarity Engine as a background task.

    State transition guard:
      'failed'    → 409  (terminal state)
      'completed' → 200  (idempotent, no re-trigger)
    """
    trace_id = get_trace_id(request)
    asset_id = payload.packet_id

    logger.info(
        f"[WEBHOOK] Completion signal: asset={asset_id} "
        f"total_frames={payload.total_frames} trace={trace_id}"
    )

    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset: Asset | None = result.scalar_one_or_none()

    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found.",
        )

    if asset.status == "completed" and asset.auditor_dispatched:
        logger.info(
            f"[WEBHOOK] Asset already completed (idempotent): "
            f"asset={asset_id} trace={trace_id}"
        )
        return {
            "status": "already_completed",
            "asset_id": str(asset_id),
            "trace_id": trace_id,
        }

    if asset.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset {asset_id} is in 'failed' state and cannot be completed.",
        )

    await db.execute(
        update(Asset)
        .where(Asset.id == asset_id)
        .values(pipeline_summary_completed=True)
    )

    logger.info(
        f"[WEBHOOK] ✅ Pipeline completion persisted: id={asset_id} "
        f"is_golden={asset.is_golden} trace={trace_id}"
    )

    auditor_queued = await _maybe_dispatch_auditor(asset_id, db, trace_id)

    return {
        "status": "completed" if auditor_queued else "waiting_for_audio_summary",
        "asset_id": str(asset_id),
        "is_golden": asset.is_golden,
        "auditor_queued": auditor_queued,
        "trace_id": trace_id,
    }
