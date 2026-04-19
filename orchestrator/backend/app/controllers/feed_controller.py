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
)

logger = get_logger("sourcegraph.feed")

router = APIRouter(tags=["Dashboard"])


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

    return HealthResponse(
        status="online",
        machine="Tanmay-M4",
        role="Orchestrator",
        version="3.0.0",
        total_assets=total,
        golden_assets=golden,
        suspect_assets=total - golden,
        tailscale_ip=settings.tailscale_ip,
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

    return AssetStatusResponse(
        asset_id=row.Asset.id,
        filename=row.Asset.filename,
        is_golden=row.Asset.is_golden,
        status=row.Asset.status,
        frame_count=row.frame_count or 0,
        created_at=row.Asset.created_at.isoformat(),
        trace_id=trace_id,
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