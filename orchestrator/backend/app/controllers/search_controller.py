"""
Search / Inference Controller — Workflow B (AUDITOR).

POST /api/v1/search/upload
---------------------------
Accepts a suspect video clip from an AUDITOR, creates an Asset record
(is_golden=False, status='processing'), and forwards to the M2 Extractor.

Once the Extractor has dispatched all GPU jobs and the buffer has synced
every frame, the M2 node calls POST /api/v1/webhooks/complete.  That
endpoint marks the asset as 'completed' and triggers the Similarity
Engine asynchronously.

The caller polls GET /api/v1/assets/{asset_id}/result for the verdict.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import get_trace_id, require_auditor
from app.core.database import get_db
from app.core.logger import get_logger
from app.models.db_models import Asset
from app.models.schemas import UploadResponse

logger = get_logger("sourcegraph.search")

router = APIRouter(prefix="/api/v1/search", tags=["Inference — AUDITOR"])


# ── Extractor forwarding (shared logic with golden, different flags) ─────

async def _forward_suspect_to_extractor(
    asset_id: UUID,
    filename: str,
    file_bytes: bytes,
    trace_id: str,
) -> None:
    """
    Forward suspect clip to the M2 Extractor.

    Same retry logic as golden controller.  `is_golden=false` tells the
    Extractor it may skip certain preprocessing steps reserved for golden
    sources (e.g. watermark detection).
    """
    callback_url = (
        f"http://{settings.tailscale_ip}:8000/api/v1/webhooks/vector"
    )
    complete_url = (
        f"http://{settings.tailscale_ip}:8000/api/v1/webhooks/complete"
    )

    last_exc: Exception | None = None
    for attempt in range(1, settings.extractor_max_retries + 1):
        try:
            async with httpx.AsyncClient(
                timeout=settings.extractor_timeout_seconds
            ) as client:
                response = await client.post(
                    f"{settings.extractor_url}/extract",
                    files={"video": (filename, file_bytes, "video/mp4")},
                    data={
                        "packet_id": str(asset_id),
                        "is_golden": "false",
                        "callback_url": callback_url,
                        "complete_url": complete_url,
                        "trace_id": trace_id,
                    },
                    headers={"X-Webhook-Secret": settings.webhook_secret},
                )
                response.raise_for_status()
                logger.info(
                    f"[SEARCH] ✅ Forwarded to extractor "
                    f"asset={asset_id} attempt={attempt} trace={trace_id}"
                )
                return

        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_exc = exc
            wait = 2 ** attempt
            logger.warning(
                f"[SEARCH] ⚠ Extractor attempt {attempt}/{settings.extractor_max_retries} "
                f"failed: {exc} — retrying in {wait}s  asset={asset_id} trace={trace_id}"
            )
            if attempt < settings.extractor_max_retries:
                await asyncio.sleep(wait)

    raise RuntimeError(
        f"Extractor unreachable after {settings.extractor_max_retries} attempts: {last_exc}"
    )


async def _forward_and_update(
    asset_id: UUID,
    filename: str,
    file_bytes: bytes,
    trace_id: str,
) -> None:
    from app.core.database import AsyncSessionLocal

    try:
        await _forward_suspect_to_extractor(asset_id, filename, file_bytes, trace_id)
    except Exception as exc:
        logger.error(
            f"[SEARCH] ❌ Permanent extractor failure "
            f"asset={asset_id} error={exc} trace={trace_id}"
        )
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
                    f"[SEARCH] Failed to mark asset as failed: {db_exc} trace={trace_id}"
                )


# ── Route ────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a suspect clip for inference (AUDITOR only)",
)
async def upload_suspect_clip(
    request: Request,
    file: UploadFile = File(..., description="Suspect video file"),
    role: str = Depends(require_auditor),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """
    Workflow B — AUDITOR

    1. Create Asset(is_golden=False, status='processing').
    2. Forward to M2 Extractor (fire-and-forget with retry).
    3. Return asset_id.  Caller polls:
         GET /api/v1/assets/{id}/status  — track progress
         GET /api/v1/assets/{id}/result  — retrieve verdict once complete
    """
    trace_id = get_trace_id(request)

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )

    logger.info(
        f"[SEARCH] 📥 Suspect upload: file={file.filename} "
        f"role={role} trace={trace_id}"
    )

    asset = Asset(
        filename=file.filename,
        is_golden=False,
        status="processing",
    )
    db.add(asset)

    try:
        await db.commit()
        await db.refresh(asset)
    except Exception as exc:
        await db.rollback()
        logger.error(f"[SEARCH] DB insert failed: {exc} trace={trace_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register suspect asset: {exc}",
        )

    asset_id = asset.id
    logger.info(
        f"[SEARCH] ✅ Suspect asset created: id={asset_id} "
        f"file={file.filename} trace={trace_id}"
    )

    file_bytes = await file.read()

    asyncio.create_task(
        _forward_and_update(asset_id, file.filename, file_bytes, trace_id)
    )

    return UploadResponse(
        asset_id=asset_id,
        filename=file.filename,
        is_golden=False,
        status="processing",
        message="Suspect clip registered. Dispatching to extraction pipeline.",
        trace_id=trace_id,
    )