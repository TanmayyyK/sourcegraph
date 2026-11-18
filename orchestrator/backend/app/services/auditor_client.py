import httpx
import asyncio
import logging
import math
from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.db_models import AudioSegment, FrameVector, SimilarityResult

logger = logging.getLogger("sourcegraph.auditor_client")


def _resolve_auditor_base(url: str) -> str:
    """
    Normalise AUDITOR_URL from Render env.

    Accepts either:
      • Base Space URL     → https://<user>-<space>.hf.space
      • Full API base      → https://<user>-<space>.hf.space/api/v1/auditor
    """
    base = url.strip().rstrip("/")
    if base.endswith("/api/v1/auditor"):
        return base
    return f"{base}/api/v1/auditor"


AUDITOR_URL = _resolve_auditor_base(settings.auditor_url)
logger.info("[AUDITOR] Resolved endpoint base: %s", AUDITOR_URL)
logger.info("[AUDITOR] Matching mode: %s", settings.auditor_mode)


def _uuid_or_none(value: object) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        logger.warning(f"[AUDITOR] Ignoring invalid golden asset UUID: {value!r}")
        return None


async def _run_native_similarity(asset_id: UUID, db: AsyncSession, trace_id: str) -> bool:
    from app.services.similarity_service import similarity_service

    result = await similarity_service.run_for_asset(asset_id=asset_id, db=db, trace_id=trace_id)
    return result is not None

async def process_asset_with_auditor(
    asset_id: UUID, is_golden: bool, db: AsyncSession, trace_id: str,
    expected_frames: int | None = None,
) -> bool:
    """
    Fetches all vectors for an asset, and either indexes them (if golden)
    or searches them against the Auditor microservice.
    """
    try:
        # 1. Fetch the correct vector population for this asset role.
        # Golden rows are permanent library data; suspect rows are disposable.
        is_temporary = not is_golden
        frames = []
        for attempt in range(30):
            result = await db.execute(
                select(FrameVector)
                .where(
                    FrameVector.asset_id == asset_id,
                    FrameVector.is_temporary.is_(is_temporary),
                )
                .order_by(FrameVector.timestamp)
            )
            frames = result.scalars().all()
            paired_frames = sum(
                frame.visual_vector is not None and frame.text_vector is not None
                for frame in frames
            )
            ready = bool(frames) if expected_frames is None else paired_frames >= expected_frames
            if ready:
                break
            if attempt < 29:
                await asyncio.sleep(1.0)
        else:
            if expected_frames is not None:
                logger.error(
                    "[AUDITOR] Expected %s paired frames for %s, received %s",
                    expected_frames, asset_id, paired_frames,
                )
                return False

        result_audio = await db.execute(
            select(AudioSegment)
            .where(AudioSegment.asset_id == asset_id)
            .order_by(AudioSegment.start_time)
        )
        audio_segments_records = result_audio.scalars().all()
        if not frames and not audio_segments_records:
            logger.warning("[AUDITOR] No frames or audio segments for asset %s", asset_id)
            return False

        visual_vectors = []
        text_vectors = []
        audio_vectors = []
        for f in frames:
            if f.visual_vector is not None:
                v_vec = f.visual_vector.tolist() if hasattr(f.visual_vector, "tolist") else f.visual_vector
                visual_vectors.append(v_vec)
            if f.text_vector is not None:
                t_vec = f.text_vector.tolist() if hasattr(f.text_vector, "tolist") else f.text_vector
                text_vectors.append(t_vec)

        # Reuse stored embeddings on retries; HERMES creates missing vectors
        # with the same MiniLM model used for OCR embeddings.
        missing = [a for a in audio_segments_records if a.audio_vector is None and a.segment_text.strip()]
        if missing:
            try:
                vectors = []
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    for offset in range(0, len(missing), 128):
                        batch = missing[offset:offset + 128]
                        embed_resp = await client.post(
                            f"{settings.context_node_url.rstrip('/')}/embed/transcript",
                            json={"texts": [a.segment_text for a in batch]},
                            headers={"X-Webhook-Secret": settings.webhook_secret},
                            timeout=90.0,
                        )
                        embed_resp.raise_for_status()
                        vectors.extend(embed_resp.json()["vectors"])
                if len(vectors) != len(missing) or any(
                    len(vec) != 384 or not all(math.isfinite(float(x)) for x in vec)
                    for vec in vectors
                ):
                    raise ValueError("HERMES returned invalid transcript vectors")
                for segment, vector in zip(missing, vectors):
                    segment.audio_vector = vector
                await db.commit()
            except Exception as exc:
                logger.warning("[AUDITOR] Transcript embedding unavailable for %s: %r", asset_id, exc)
                await db.rollback()
                result_audio = await db.execute(
                    select(AudioSegment)
                    .where(AudioSegment.asset_id == asset_id)
                    .order_by(AudioSegment.start_time)
                )
                audio_segments_records = result_audio.scalars().all()

        if settings.auditor_mode == "native":
            # Golden vectors are already durable in PostgreSQL.
            return is_golden or await _run_native_similarity(asset_id, db, trace_id)

        for segment in audio_segments_records:
            if segment.audio_vector is not None:
                vec = segment.audio_vector
                audio_vectors.append(vec.tolist() if hasattr(vec, "tolist") else vec)

        payload = {
            "asset_id": str(asset_id),
            "visual_vectors": visual_vectors,
            "text_vectors": text_vectors,
            "audio_vectors": audio_vectors
        }

        if not is_golden and audio_segments_records and not audio_vectors:
            logger.warning(
                "[AUDITOR] No transcript vectors for %s; using transcript-aware PostgreSQL matching",
                asset_id,
            )
            return await _run_native_similarity(asset_id, db, trace_id)

        # 2. Communicate with Auditor microservice.
        # Golden assets are indexed into FAISS; suspect assets search FAISS and
        # persist only the verdict/result row in Postgres.
        async with httpx.AsyncClient(follow_redirects=True) as client:
            if is_golden:
                logger.info(
                    f"[AUDITOR] Sending golden asset {asset_id} to {AUDITOR_URL}/index trace={trace_id}"
                )
                resp = await client.post(f"{AUDITOR_URL}/index", json=payload, timeout=60.0)
                resp.raise_for_status()
                logger.info(f"[AUDITOR] Golden asset {asset_id} indexed successfully.")
                return True
            else:
                logger.info(
                    f"[AUDITOR] Sending suspect asset {asset_id} to {AUDITOR_URL}/search trace={trace_id}"
                )
                resp = await client.post(f"{AUDITOR_URL}/search", json=payload, timeout=60.0)
                resp.raise_for_status()

                search_data = resp.json()
                verdict = search_data.get("verdict", "CLEAN")
                if verdict == "THREAT":
                    verdict = "PIRACY_DETECTED"
                fused_score = search_data.get("fused_score", 0.0)
                visual_score = search_data.get("visual_score", fused_score)
                text_score = search_data.get("text_score", 0.0)
                audio_score = search_data.get("audio_score", 0.0)
                golden_asset_id = _uuid_or_none(
                    search_data.get("golden_asset_id") or search_data.get("matched_asset_id")
                )
                matched_timestamp = search_data.get("matched_timestamp")

                logger.info(f"[AUDITOR] Search complete for {asset_id}. Verdict={verdict}, Score={fused_score:.2f}")

                stmt = pg_insert(SimilarityResult).values(
                    suspect_asset_id=asset_id,
                    golden_asset_id=golden_asset_id,
                    matched_timestamp=matched_timestamp,
                    visual_score=visual_score,
                    text_score=text_score,
                    audio_score=audio_score,
                    fused_score=fused_score,
                    verdict=verdict,
                ).on_conflict_do_update(
                    index_elements=[SimilarityResult.suspect_asset_id],
                    set_={
                        "golden_asset_id": golden_asset_id,
                        "matched_timestamp": matched_timestamp,
                        "visual_score": visual_score,
                        "text_score": text_score,
                        "audio_score": audio_score,
                        "fused_score": fused_score,
                        "verdict": verdict,
                    },
                )
                await db.execute(stmt)
                purge_result = await db.execute(
                    delete(FrameVector).where(
                        FrameVector.asset_id == asset_id,
                        FrameVector.is_temporary.is_(True),
                    )
                )
                await db.commit()
                logger.info(
                    f"[AUDITOR] Purged {purge_result.rowcount or 0} temporary vectors "
                    f"for suspect asset {asset_id}. trace={trace_id}"
                )
                return True

    except Exception as exc:
        await db.rollback()
        if settings.auditor_mode == "native":
            logger.exception("[AUDITOR] Native audit failed for %s trace=%s", asset_id, trace_id)
            return False
        logger.warning(
            f"[AUDITOR] Remote ML Auditor endpoint unavailable ({exc!r}). "
            f"Falling back to native PostgreSQL pgvector SimilarityService for asset {asset_id} trace={trace_id}"
        )
        # If it's a golden asset, the vectors are already persisted in frame_vectors.
        if is_golden:
            logger.info(f"[AUDITOR] Golden asset {asset_id} vectors safely stored in PostgreSQL frame_vectors.")
            return True

        # For suspect assets, run native pgvector KNN similarity search
        try:
            return await _run_native_similarity(asset_id, db, trace_id)
        except Exception as sim_exc:
            logger.error(f"[AUDITOR] Native similarity service failed: {sim_exc!r} trace={trace_id}")
            return False
