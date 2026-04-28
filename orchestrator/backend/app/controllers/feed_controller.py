"""
Feed & Asset Status Controller — read-only dashboard surface.

Endpoints
---------
GET /                          — health check
GET /buffer/status             — buffer diagnostics
GET /api/v1/assets             — paginated asset list
GET /api/v1/assets/{id}/status — processing state for a single asset
GET /api/v1/assets/{id}/result — similarity result (non-golden only)
"""

from __future__ import annotations

from uuid import UUID

from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import get_trace_id
from app.core.database import get_db
from app.core.logger import get_logger
from app.models.db_models import Asset, FrameVector, SimilarityResult
from app.models.schemas import (
    AssetStatusResponse,
    FeedEntry,
    HealthResponse,
    SimilarityResultResponse,
    AnalysisPayload,
)
from sqlalchemy import update
import asyncio


logger = get_logger("sourcegraph.feed")

router = APIRouter(tags=["Dashboard"])

import time
from pydantic import BaseModel, model_validator

NODE_LAST_SEEN = { 
    "atlas": 0.0, 
    "argus": 0.0, 
    "hermes": 0.0, 
    "orchestrator": time.time() 
}


def _normalize_confidence_score(score: float | None) -> float:
    if score is None:
        return 0.0
    raw_score = score / 100.0 if score > 1 else score
    return max(0.0, min(1.0, raw_score))


def _piracy_tier(score: float | None) -> dict[str, str]:
    raw_score = _normalize_confidence_score(score)
    if raw_score >= 0.80:
        return {
            "label": "High Confidence (Piracy)",
            "action": "Automated Takedown Initiated",
            "status": "alert",
        }
    if raw_score >= 0.60:
        return {
            "label": "Suspicious",
            "action": "Manual Review Required",
            "status": "alert",
        }
    if raw_score >= 0.40:
        return {
            "label": "Low Confidence",
            "action": "Flagged for Observation",
            "status": "alert",
        }
    return {
        "label": "Clean",
        "action": "Discarded",
        "status": "complete",
    }

class HeartbeatRequest(BaseModel):
    node: Literal["atlas", "argus", "hermes", "orchestrator"]

    @model_validator(mode='before')
    @classmethod
    def remap_legacy_node(cls, data: Any) -> Any:
        if isinstance(data, dict) and "node" in data:
            mapping = {
                "ingest_api":     "atlas",
                "vision_engine":  "argus",
                "text_processor": "hermes"
            }
            if data["node"] in mapping:
                data["node"] = mapping[data["node"]]
        return data

@router.post(
    "/api/v1/health/heartbeat",
    summary="Update heartbeat for a node"
)
async def heartbeat(req: HeartbeatRequest):
    NODE_LAST_SEEN[req.node] = time.time()
    return {"status": "ok"}

# ── Health ───────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=HealthResponse,
    summary="Orchestrator health check",
)
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """Aggregate asset counts from PostgreSQL."""
    trace_id = get_trace_id(request)
    
    # Auto-update orchestrator heartbeat when polled
    NODE_LAST_SEEN["orchestrator"] = time.time()

    try:
        total_result = await db.execute(select(func.count(Asset.id)))
        total = total_result.scalar_one_or_none() or 0

        golden_result = await db.execute(
            select(func.count(Asset.id)).where(Asset.is_golden.is_(True))
        )
        golden = golden_result.scalar_one_or_none() or 0

    except Exception as exc:
        logger.error(f"[FEED] Health check DB error: {exc} trace={trace_id}")
        total, golden = 0, 0

    current_time = time.time()
    # Nodes ping every 30s; 45s grace period avoids frequent ERR toggling.
    nodes_health = {
        node: "OK" if current_time - last_seen < 45.0 else "ERR"
        for node, last_seen in NODE_LAST_SEEN.items()
    }

    return HealthResponse(
        status="online",
        machine="Tanmay-M4",
        role="Orchestrator",
        version="3.0.0",
        total_assets=total,
        golden_assets=golden,
        suspect_assets=total - golden,
        tailscale_ip=settings.tailscale_ip,
        nodes=nodes_health,
    )


# ── Buffer diagnostics ────────────────────────────────────────────────────

@router.get(
    "/buffer/status",
    summary="Sync buffer diagnostics",
)
async def buffer_status(request: Request) -> dict:
    """Current buffer state: pending entries, ages, per-node breakdown."""
    buffer = request.app.state.buffer
    return await buffer.get_state()


# ── Asset feed ────────────────────────────────────────────────────────────

@router.get(
    "/api/v1/assets",
    response_model=list[FeedEntry],
    summary="Recent assets (paginated)",
)
async def list_assets(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[FeedEntry]:
    """Return recently ingested assets with frame counts."""
    trace_id = get_trace_id(request)

    try:
        stmt = (
            select(
                Asset,
                func.count(FrameVector.id).label("frame_count"),
            )
            .outerjoin(FrameVector, FrameVector.asset_id == Asset.id)
            .group_by(Asset.id)
            .order_by(Asset.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        rows = result.all()

    except Exception as exc:
        logger.error(f"[FEED] list_assets error: {exc} trace={trace_id}")
        raise HTTPException(status_code=500, detail=str(exc))

    return [
        FeedEntry(
            asset_id=str(row.Asset.id),
            filename=row.Asset.filename,
            is_golden=row.Asset.is_golden,
            status=row.Asset.status,
            frame_count=row.frame_count or 0,
            created_at=row.Asset.created_at.isoformat(),
        )
        for row in rows
    ]


# ── Asset status ──────────────────────────────────────────────────────────

@router.get(
    "/api/v1/assets/{asset_id}/status",
    response_model=AssetStatusResponse,
    summary="Get processing status for a single asset",
)
async def get_asset_status(
    asset_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AssetStatusResponse:
    """
    Poll this endpoint after uploading to track extraction progress.

    status values:
      'processing' — extractor is still running
      'completed'  — all frames written; similarity done (if non-golden)
      'failed'     — extractor unreachable after retries
    """
    trace_id = get_trace_id(request)

    stmt = (
        select(Asset, func.count(FrameVector.id).label("frame_count"))
        .outerjoin(FrameVector, FrameVector.asset_id == Asset.id)
        .where(Asset.id == asset_id)
        .group_by(Asset.id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found.",
        )

    buffered_count = 0
    if hasattr(request.app.state, "buffer"):
        buffered_count = await request.app.state.buffer.get_asset_count(asset_id)

    return AssetStatusResponse(
        asset_id=row.Asset.id,
        filename=row.Asset.filename,
        is_golden=row.Asset.is_golden,
        status=row.Asset.status,
        frame_count=(row.frame_count or 0) + buffered_count,
        vision_latency_ms=row.Asset.vision_latency_ms,
        text_latency_ms=row.Asset.text_latency_ms,
        created_at=row.Asset.created_at.isoformat(),
        trace_id=trace_id,
    )


# ── Asset Finalization (Manual/Fallback) ──────────────────────────────────

@router.post(
    "/api/v1/assets/{asset_id}/finalize",
    summary="Manually break the finalization barrier and trigger the Auditor",
)
async def finalize_asset(
    asset_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Force-transitions an asset to 'completed' and triggers inference.
    Use this if a GPU node crashes and fails to send its final summary.
    """
    trace_id = get_trace_id(request)
    
    # Import here to avoid circular dependencies if any
    from app.controllers.webhook_controller import _run_auditor_background

    # Atomically update status and prevent double-dispatch
    stmt = (
        update(Asset)
        .where(
            Asset.id == asset_id,
            Asset.status != "completed",
            Asset.auditor_dispatched.is_(False),
        )
        .values(
            status="completed",
            auditor_dispatched=True,
            pipeline_summary_completed=True, # Mark as done to satisfy UI logic
            audio_summary_completed=True
        )
        .returning(Asset.is_golden)
    )
    result = await db.execute(stmt)
    row = result.first()
    await db.commit()

    if row is None:
        return {
            "status": "already_completed",
            "asset_id": str(asset_id),
            "trace_id": trace_id
        }

    is_golden = bool(row[0])
    
    # Trigger Auditor in background
    asyncio.create_task(
        _run_auditor_background(asset_id, is_golden, trace_id),
        name=f"manual_finalize:{asset_id}",
    )

    logger.info(
        f"[FEED] ⚡ Manual finalization triggered for asset={asset_id} trace={trace_id}"
    )

    return {
        "status": "completed",
        "asset_id": str(asset_id),
        "trace_id": trace_id,
        "message": "Asset manually finalized and Auditor dispatched."
    }


# ── Forensic Analysis ─────────────────────────────────────────────────────────

from app.models.db_models import FrameVisionMetadata, FrameEmbedding, AudioSegment as AudioSegmentModel

@router.get(
    "/api/v1/analysis/{asset_id}",
    response_model=AnalysisPayload,
    summary="Generate forensic graph data for an asset",
)
async def get_forensic_analysis(
    asset_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AnalysisPayload:
    """
    Synthesizes a rich graph visualization for the NexusScreen from real
    pipeline data — frame counts, audio segments, similarity verdicts, and
    timestamped ingest logs are all queried from the database.
    """
    trace_id = get_trace_id(request)

    # ── 1. Fetch Asset ────────────────────────────────────────────────────────
    asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # ── 2. Fetch real pipeline metrics ────────────────────────────────────────
    # Frame vectors (paired production surface)
    fv_count_result = await db.execute(
        select(func.count(FrameVector.id)).where(FrameVector.asset_id == asset_id)
    )
    frame_vector_count = fv_count_result.scalar_one_or_none() or 0

    # Vision staging frames (ARGUS)
    vision_count_result = await db.execute(
        select(func.count(FrameEmbedding.id)).where(FrameEmbedding.asset_id == asset_id)
    )
    vision_frame_count = vision_count_result.scalar_one_or_none() or 0

    # Text staging frames (HERMES)
    text_count_result = await db.execute(
        select(func.count(FrameVisionMetadata.id)).where(FrameVisionMetadata.asset_id == asset_id)
    )
    text_frame_count = text_count_result.scalar_one_or_none() or 0

    # Audio segments
    audio_count_result = await db.execute(
        select(func.count(AudioSegmentModel.id)).where(AudioSegmentModel.asset_id == asset_id)
    )
    audio_segment_count = audio_count_result.scalar_one_or_none() or 0

    # Similarity result
    sim_result = None
    if not asset.is_golden and asset.status == "completed":
        res = await db.execute(
            select(SimilarityResult).where(SimilarityResult.suspect_asset_id == asset_id)
        )
        sim_result = res.scalar_one_or_none()

    # ── 3. Determine node statuses ────────────────────────────────────────────
    is_completed  = asset.status == "completed"
    is_processing = asset.status == "processing"

    atlas_status  = "complete" if (asset.pipeline_summary_completed or is_completed) else ("processing" if is_processing else "idle")
    argus_status  = "complete" if vision_frame_count > 0 and (is_completed or asset.pipeline_summary_completed) else ("processing" if is_processing else "idle")
    hermes_status = "complete" if text_frame_count > 0 and (is_completed or asset.pipeline_summary_completed) else ("processing" if is_processing else "idle")

    total_frames = max(vision_frame_count, text_frame_count, frame_vector_count)

    # ── 4. Construct Nodes ────────────────────────────────────────────────────
    nodes: list[dict] = [
        {
            "id": "asset_root",
            "type": "asset",
            "data": {
                "label": asset.filename,
                "role": "Golden Asset" if asset.is_golden else "Suspect Asset",
                "status": asset.status,
                "score": 0,
                "nodeType": "asset",
            },
            "position": {"x": 320, "y": 60},
        },
        {
            "id": "engine_atlas",
            "type": "engine",
            "data": {
                "label": "ATLAS",
                "role": f"Extracted {total_frames} frames",
                "engine_type": "FRAME_EXTRACT",
                "status": atlas_status,
                "score": 100 if atlas_status == "complete" else (50 if atlas_status == "processing" else 0),
                "nodeType": "engine",
            },
            "position": {"x": 320, "y": 210},
        },
        {
            "id": "engine_argus",
            "type": "engine",
            "data": {
                "label": "ARGUS",
                "role": f"Vision — {vision_frame_count} embeddings",
                "engine_type": "CLIP_512D",
                "status": argus_status,
                "score": 100 if argus_status == "complete" else (50 if argus_status == "processing" else 0),
                "nodeType": "engine",
            },
            "position": {"x": 560, "y": 360},
        },
        {
            "id": "engine_hermes",
            "type": "engine",
            "data": {
                "label": "HERMES",
                "role": f"Context — {text_frame_count} OCR chunks",
                "engine_type": "MINILM_384D",
                "status": hermes_status,
                "score": 100 if hermes_status == "complete" else (50 if hermes_status == "processing" else 0),
                "nodeType": "engine",
            },
            "position": {"x": 80, "y": 360},
        },
    ]

    # Audio engine node (only if audio data exists)
    if audio_segment_count > 0 or asset.audio_summary_completed:
        audio_status = "complete" if asset.audio_summary_completed else "processing"
        nodes.append({
            "id": "engine_audio",
            "type": "engine",
            "data": {
                "label": "Whisper Audio",
                "role": f"Transcribed {audio_segment_count} segments",
                "engine_type": "WHISPER_ASR",
                "status": audio_status,
                "score": 100 if audio_status == "complete" else 50,
                "nodeType": "engine",
            },
            "position": {"x": 320, "y": 510},
        })

    # ── 5. Construct Edges ────────────────────────────────────────────────────
    edges: list[dict] = [
        {"id": "e-src-atlas",    "source": "asset_root",    "target": "engine_atlas",  "label": "Bitstream"},
        {"id": "e-atlas-argus",  "source": "engine_atlas",  "target": "engine_argus",  "label": f"{total_frames} Frames"},
        {"id": "e-atlas-hermes", "source": "engine_atlas",  "target": "engine_hermes", "label": "Metadata"},
    ]

    if audio_segment_count > 0 or asset.audio_summary_completed:
        edges.append({"id": "e-atlas-audio", "source": "engine_atlas", "target": "engine_audio", "label": "WAV Track"})

    # Similarity / Threat / Verdict nodes
    if sim_result:
        visual_pct = round(_normalize_confidence_score(sim_result.visual_score) * 100, 1)
        text_pct   = round(_normalize_confidence_score(sim_result.text_score) * 100, 1)
        fused_raw  = _normalize_confidence_score(sim_result.fused_score)
        fused_pct  = round(fused_raw * 100, 1)
        verdict_tier = _piracy_tier(sim_result.fused_score)

        is_threat = fused_raw >= 0.40

        if is_threat:
            nodes.append({
                "id": "threat_match",
                "type": "threat",
                "data": {
                    "label": f"Match: {str(sim_result.golden_asset_id)[:8]}",
                    "role": f"Visual {visual_pct}% · Text {text_pct}%",
                    "status": "alert",
                    "score": fused_pct,
                    "nodeType": "threat",
                },
                "position": {"x": 560, "y": 510},
            })
            edges.append({"id": "e-argus-threat",  "source": "engine_argus",  "target": "threat_match", "label": f"Visual ↑{visual_pct}%"})
            edges.append({"id": "e-hermes-threat", "source": "engine_hermes", "target": "threat_match", "label": f"Text ↑{text_pct}%"})

        nodes.append({
            "id": "verdict_final",
            "type": "verdict",
            "data": {
                "label": verdict_tier["label"],
                "role": verdict_tier["action"],
                "status": verdict_tier["status"],
                "score": fused_pct,
                "nodeType": "verdict",
            },
            "position": {"x": 320, "y": 660},
        })

        if is_threat:
            edges.append({"id": "e-threat-verdict", "source": "threat_match", "target": "verdict_final", "label": "Escalated"})
        else:
            edges.append({"id": "e-argus-verdict",  "source": "engine_argus",  "target": "verdict_final", "label": f"Fused {fused_pct}%"})
            edges.append({"id": "e-hermes-verdict", "source": "engine_hermes", "target": "verdict_final", "label": "Correlated"})

    elif asset.is_golden and is_completed:
        nodes.append({
            "id": "verdict_final",
            "type": "verdict",
            "data": {
                "label": "INDEXED",
                "role": "Golden Library Protected",
                "status": "complete",
                "score": 100,
                "nodeType": "verdict",
            },
            "position": {"x": 320, "y": 560},
        })
        edges.append({"id": "e-argus-verdict",  "source": "engine_argus",  "target": "verdict_final", "label": "FAISS Indexed"})
        edges.append({"id": "e-hermes-verdict", "source": "engine_hermes", "target": "verdict_final", "label": "FAISS Indexed"})

    # ── 6. Construct timestamped Ingest Logs ──────────────────────────────────
    ts_fmt = lambda dt: dt.isoformat() if dt else "—"
    logs: list[str] = []

    logs.append(f"{ts_fmt(asset.created_at)} [INFO]  Asset ingested: {asset.filename} — role={'GOLDEN' if asset.is_golden else 'SUSPECT'}")
    logs.append(f"{ts_fmt(asset.created_at)} [INFO]  TraceID: {trace_id}")
    logs.append(f"{ts_fmt(asset.created_at)} [INFO]  Dispatching to Titan Protocol nodes")

    if total_frames > 0:
        logs.append(f"{ts_fmt(asset.created_at)} [OK]    ATLAS: Extracted {total_frames} frames @ 1 FPS")

    if vision_frame_count > 0:
        latency_str = f" — latency {asset.vision_latency_ms}ms" if asset.vision_latency_ms else ""
        logs.append(f"{ts_fmt(asset.created_at)} [OK]    ARGUS: {vision_frame_count} visual embeddings (512-D CLIP){latency_str}")

    if text_frame_count > 0:
        latency_str = f" — latency {asset.text_latency_ms}ms" if asset.text_latency_ms else ""
        logs.append(f"{ts_fmt(asset.created_at)} [OK]    HERMES: {text_frame_count} OCR chunks processed{latency_str}")

    if frame_vector_count > 0:
        logs.append(f"{ts_fmt(asset.created_at)} [OK]    BufferService: {frame_vector_count} paired vectors flushed to DB")

    if audio_segment_count > 0:
        logs.append(f"{ts_fmt(asset.created_at)} [OK]    Whisper: {audio_segment_count} audio segments transcribed")
    elif asset.audio_summary_completed:
        logs.append(f"{ts_fmt(asset.created_at)} [WARN]  Whisper: Audio summary received (0 segments — silent/corrupt)")

    if asset.pipeline_summary_completed:
        logs.append(f"{ts_fmt(asset.updated_at)} [OK]    Pipeline summary received from ATLAS")
    if asset.audio_summary_completed:
        logs.append(f"{ts_fmt(asset.updated_at)} [OK]    Audio summary received from ARGUS/Whisper")

    if is_completed:
        logs.append(f"{ts_fmt(asset.updated_at)} [OK]    Asset status → COMPLETED")

    if sim_result:
        logs.append(f"{ts_fmt(sim_result.created_at)} [INFO]  Similarity engine fired — FAISS KNN search")
        logs.append(f"{ts_fmt(sim_result.created_at)} [INFO]  Visual: {sim_result.visual_score:.2f}% · Text: {sim_result.text_score:.2f}% · Fused: {sim_result.fused_score:.2f}%")
        verdict_tier = _piracy_tier(sim_result.fused_score)
        level = "ALERT" if _normalize_confidence_score(sim_result.fused_score) >= 0.40 else "OK"
        logs.append(
            f"{ts_fmt(sim_result.created_at)} [{level}] VERDICT: {verdict_tier['label']} — "
            f"{verdict_tier['action']} — composite confidence={_normalize_confidence_score(sim_result.fused_score) * 100:.1f}%"
        )

    if asset.status == "failed":
        logs.append(f"{ts_fmt(asset.updated_at)} [ERROR] Asset processing FAILED")

    # ── 7. Construct Temporal Data ────────────────────────────────────────────
    # Query real vision metadata to show "intensity" over time
    fvm_result = await db.execute(
        select(FrameVisionMetadata)
        .where(FrameVisionMetadata.asset_id == asset_id)
        .order_by(FrameVisionMetadata.timestamp.asc())
    )
    temporal_points = fvm_result.scalars().all()
    
    temporal_data = [
        {
            "ts": p.timestamp,
            "val": p.chunks_extracted + p.boxes_mapped,
            "type": "vision_load"
        }
        for p in temporal_points
    ]

    return AnalysisPayload(
        nodes=nodes,
        edges=edges,
        ingest_logs=logs,
        temporal_data=temporal_data
    )


# ── Similarity result ─────────────────────────────────────────────────────

@router.get(
    "/api/v1/assets/{asset_id}/result",
    response_model=SimilarityResultResponse,
    summary="Retrieve similarity / piracy verdict for a suspect asset",
)
async def get_similarity_result(
    asset_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SimilarityResultResponse:
    """
    Returns the persisted SimilarityResult for a non-golden asset.

    Returns 404 if inference has not completed yet — poll /status first
    to confirm status='completed', then call this endpoint.
    """
    trace_id = get_trace_id(request)

    # Validate asset exists
    asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset: Asset | None = asset_result.scalar_one_or_none()

    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found.",
        )

    if asset.is_golden:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Similarity results are only available for non-golden (suspect) assets.",
        )

    if asset.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=(
                f"Asset {asset_id} is still '{asset.status}'. "
                "Wait for status='completed' before fetching results."
            ),
        )

    # Fetch result
    sim_result = await db.execute(
        select(SimilarityResult).where(
            SimilarityResult.suspect_asset_id == asset_id
        )
    )
    row: SimilarityResult | None = sim_result.scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No similarity result found for asset {asset_id}. "
                "The engine may still be running — try again in a moment."
            ),
        )

    return SimilarityResultResponse(
        suspect_asset_id=row.suspect_asset_id,
        golden_asset_id=row.golden_asset_id,
        matched_timestamp=row.matched_timestamp,
        visual_score=row.visual_score,
        text_score=row.text_score,
        fused_score=row.fused_score,
        verdict=row.verdict,  # type: ignore[arg-type]
        trace_id=trace_id,
    )
