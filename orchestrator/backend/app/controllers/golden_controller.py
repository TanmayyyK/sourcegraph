"""
Unified Asset Upload Controller — Role-routed V2 ingestion.

POST /api/v1/assets/upload
--------------------------
Accepts a raw media file from either role, creates an Asset record
with is_golden derived from the authenticated role, and asynchronously
forwards the file to the M2 Extractor Node for FFmpeg frame extraction.

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

from app.config import settings
from app.core.auth import get_trace_id, resolve_upload_identity
from app.core.database import get_db
from app.core.logger import get_logger
from app.models.db_models import Asset
from app.models.schemas import UploadResponse

logger = get_logger("sourcegraph.assets")

router = APIRouter(prefix="/api/v1/assets", tags=["Assets — Unified Upload"])


# ── Retry-decorated extractor forwarding ────────────────────────────────

async def _forward_to_extractor(
    asset_id: UUID,
    filename: str,
    file_bytes: bytes,
    is_golden: bool,
    trace_id: str,
) -> None:
    """
    POST the raw video bytes to the M2 Extractor.

    Tells the Extractor:
      - `packet_id`  — so it can embed this ID in every webhook it fires
      - `is_golden`  — PRODUCER assets index as golden, AUDITOR assets search
      - `callback_url` — Orchestrator webhook endpoint for vector delivery

    Retry: 3 attempts, exponential backoff 2→4→8 s.
    On permanent failure: caller updates asset status to 'failed'.
    """

    callback_url = f"http://{settings.tailscale_ip}:8000/api/v1/webhooks/feeder"
    route_label = "PRODUCER" if is_golden else "AUDITOR"

    attempt = 0
    last_exc: Exception | None = None

    for attempt in range(1, settings.extractor_max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.extractor_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.extractor_url}/ingest",
                    files={"video": (filename, file_bytes, "video/mp4")},
                    data={
                        "packet_id": str(asset_id),
                        "is_golden": str(is_golden).lower(),
                        "callback_url": callback_url,
                        "trace_id": trace_id,
                    },
                    headers={"X-Webhook-Secret": settings.webhook_secret},
                )
                if response.status_code >= 400:
                    logger.error(
                        f"[ASSETS:{route_label}] Extractor error body: {response.text}  asset={asset_id}"
                    )
                response.raise_for_status()
                logger.info(
                    f"[ASSETS:{route_label}] Forwarded to extractor "
                    f"asset={asset_id} is_golden={is_golden} attempt={attempt} trace={trace_id}"
                )
                return

        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_exc = exc
            wait = 2 ** attempt  # 2, 4, 8 s
            logger.warning(
                f"[ASSETS:{route_label}] Extractor attempt {attempt}/{settings.extractor_max_retries} "
                f"failed: {exc} - retrying in {wait}s  asset={asset_id} trace={trace_id}"
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
    is_golden: bool,
    trace_id: str,
) -> None:
    """
    Background task: forward file and handle persistent failure by
    updating asset.status → 'failed'.
    """
    from app.core.database import AsyncSessionLocal

    try:
        await _forward_to_extractor(asset_id, filename, file_bytes, is_golden, trace_id)
    except Exception as exc:
        logger.error(
            f"[ASSETS] Permanent extractor failure "
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
                    f"[ASSETS] Failed to mark asset as failed: {db_exc} trace={trace_id}"
                )


# ── Route ────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload an asset and route as PRODUCER golden or AUDITOR suspect",
)
async def upload_asset(
    request: Request,
    file: UploadFile = File(..., description="Raw video file (.mp4, .mov, etc.)"),
    user: dict = Depends(resolve_upload_identity),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """
    Unified V2 role router.

    1. Validate file presence.
    2. Derive is_golden from role: PRODUCER=True, AUDITOR=False.
    3. Create Asset(is_golden=role-derived, status='processing') in PostgreSQL.
    3. Read file bytes and fire-and-forget to M2 Extractor.
    4. Return asset_id immediately — caller polls /status for progress.
    """
    uploader_id = user.get("sub")
    role = str(user.get("role", "")).upper()
    if role not in {"PRODUCER", "AUDITOR"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: upload requires PRODUCER or AUDITOR role.",
        )
    is_golden = role == "PRODUCER"
    trace_id = get_trace_id(request)

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )

    logger.info(
        f"[ASSETS] Upload received: file={file.filename} "
        f"role={role} is_golden={is_golden} uploader={uploader_id} trace={trace_id}"
    )

    # ── Persist asset record ─────────────────────────────────────────────
    asset = Asset(
        filename=file.filename,
        is_golden=is_golden,
        status="processing",
    )
    db.add(asset)

    try:
        await db.commit()
        await db.refresh(asset)
    except Exception as exc:
        await db.rollback()
        logger.error(
            f"[ASSETS] DB insert failed: {exc} trace={trace_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register asset: {exc}",
        )

    asset_id = asset.id
    logger.info(
        f"[ASSETS] Asset created: id={asset_id} "
        f"file={file.filename} is_golden={is_golden} trace={trace_id}"
    )

    # ── Read file bytes then fire-and-forget ─────────────────────────────
    file_bytes = await file.read()

    asyncio.create_task(
        _forward_and_update(asset_id, file.filename, file_bytes, is_golden, trace_id)
    )

    message = (
        "Golden asset registered. Extraction job dispatched for FAISS indexing."
        if is_golden
        else "Auditor asset registered. Extraction job dispatched for FAISS search."
    )

    return UploadResponse(
        asset_id=asset_id,
        filename=file.filename,
        is_golden=is_golden,
        status="processing",
        message=message,
        trace_id=trace_id,
    )
