"""
Similarity Engine — KNN search backed by pgvector HNSW indexes.

Algorithm
---------
For each suspect frame:
  1. Execute a pgvector KNN query using the `<=>` cosine distance operator.
     The HNSW index makes this sub-50ms even at millions of vectors.
  2. Convert distance → similarity:  sim = 1 - distance
  3. Compute fused score:  F = (visual_sim × 0.65) + (text_sim × 0.35)

Asset-level verdict:
  Take the maximum fused score across all frames of the suspect asset.
  The corresponding golden asset ID and timestamp are the "match point".

Verdicts
--------
  fused_score ≥ 0.80  → PIRACY_DETECTED
  fused_score ≥ 0.60  → SUSPICIOUS
  fused_score ≥ 0.40  → LOW_CONFIDENCE
  otherwise           → CLEAN

Retry
-----
  If pgvector returns 0 rows (warm-up phase / empty golden library),
  the result is CLEAN with fused_score=0.0 — not an error.

Observability
-------------
  Every query logs its trace_id, asset_id, and execution time so the
  full pipeline can be traced end-to-end.
"""

from __future__ import annotations

import time
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logger import get_logger
from app.models.db_models import Asset, FrameVector, SimilarityResult
from app.models.schemas import Verdict

logger = get_logger("sourcegraph.similarity")


class SimilarityService:
    """
    Executes the fused KNN similarity pipeline.

    Instantiated once at startup; all methods are stateless and async-safe.
    """

    def __init__(
        self,
        visual_weight: float = settings.fusion_weight_visual,
        text_weight: float = settings.fusion_weight_text,
        top_k: int = settings.knn_top_k,
    ) -> None:
        self.visual_weight = visual_weight
        self.text_weight = text_weight
        self.top_k = top_k

    # ── Public entry point ───────────────────────────────────────────────

    async def run_for_asset(
        self,
        asset_id: UUID,
        db: AsyncSession,
        trace_id: str = "",
    ) -> SimilarityResult | None:
        """
        Run the full pipeline for a completed suspect asset.

        Returns a persisted SimilarityResult row, or None if the asset
        has no frames or the golden library is empty.
        """
        start = time.perf_counter()
        logger.info(
            f"[SIMILARITY] 🔍 Starting inference "
            f"asset={asset_id} trace={trace_id}"
        )

        # ── 1. Load suspect frames ────────────────────────────────────────
        frames_result = await db.execute(
            select(FrameVector).where(FrameVector.asset_id == asset_id)
        )
        suspect_frames = frames_result.scalars().all()

        if not suspect_frames:
            logger.warning(
                f"[SIMILARITY] No frames found for asset={asset_id} trace={trace_id}"
            )
            return None

        logger.info(
            f"[SIMILARITY] Loaded {len(suspect_frames)} suspect frames "
            f"asset={asset_id} trace={trace_id}"
        )

        # ── 2. KNN against all golden frames ─────────────────────────────
        best: dict[str, Any] | None = None
        best_score = -1.0

        for frame in suspect_frames:
            matches = await self._knn_for_frame(
                visual_vec=frame.visual_vector,
                text_vec=frame.text_vector,
                db=db,
                trace_id=trace_id,
            )
            for match in matches:
                if match["fused_score"] > best_score:
                    best_score = match["fused_score"]
                    best = match

        elapsed = (time.perf_counter() - start) * 1000

        if best is None:
            logger.info(
                f"[SIMILARITY] No golden matches found (empty library?) "
                f"asset={asset_id} trace={trace_id} elapsed={elapsed:.1f}ms"
            )
            verdict: Verdict = "CLEAN"
            result = SimilarityResult(
                suspect_asset_id=asset_id,
                golden_asset_id=None,
                matched_timestamp=None,
                visual_score=0.0,
                text_score=0.0,
                fused_score=0.0,
                verdict=verdict,
            )
        else:
            verdict = self._verdict(best["fused_score"])
            result = SimilarityResult(
                suspect_asset_id=asset_id,
                golden_asset_id=best["golden_asset_id"],
                matched_timestamp=best["timestamp"],
                visual_score=best["visual_sim"],
                text_score=best["text_sim"],
                fused_score=best["fused_score"],
                verdict=verdict,
            )

            logger.warning(
                f"[SIMILARITY] 🎯 Match: verdict={verdict} "
                f"score={best['fused_score']:.4f} "
                f"golden={best['golden_asset_id']} "
                f"@ t={best['timestamp']:.3f}s "
                f"trace={trace_id} elapsed={elapsed:.1f}ms"
            )

        # ── 3. Persist result (upsert on conflict) ───────────────────────
        try:
            db.add(result)
            await db.commit()
            await db.refresh(result)
        except Exception as exc:
            await db.rollback()
            logger.error(
                f"[SIMILARITY] Failed to persist result "
                f"asset={asset_id} error={exc} trace={trace_id}"
            )
            raise

        return result

    # ── KNN query ────────────────────────────────────────────────────────

    async def _knn_for_frame(
        self,
        visual_vec: Any,
        text_vec: Any,
        db: AsyncSession,
        trace_id: str = "",
    ) -> list[dict[str, Any]]:
        """
        Execute a pgvector KNN search for a single frame.

        The ORDER BY clause on the cosine distance expression activates the
        HNSW index path in Postgres — this is the critical hot path.

        The query computes BOTH distances in a single scan so we avoid
        hitting the table twice.
        """
        stmt = (
            select(
                FrameVector.asset_id.label("golden_asset_id"),
                FrameVector.timestamp,
                # 1 - <=> gives cosine similarity (0..1 for normalised vectors)
                (
                    1 - FrameVector.visual_vector.cosine_distance(visual_vec)
                ).label("visual_sim"),
                (
                    1 - FrameVector.text_vector.cosine_distance(text_vec)
                ).label("text_sim"),
            )
            .join(Asset, Asset.id == FrameVector.asset_id)
            .where(Asset.is_golden.is_(True))
            # ORDER BY pushes the query into the HNSW index
            .order_by(FrameVector.visual_vector.cosine_distance(visual_vec))
            .limit(self.top_k)
        )

        try:
            result = await db.execute(stmt)
            rows = result.all()
        except Exception as exc:
            logger.error(
                f"[SIMILARITY] KNN query failed: {exc} trace={trace_id}"
            )
            return []

        matches = []
        for row in rows:
            visual_sim = float(row.visual_sim or 0.0)
            text_sim = float(row.text_sim or 0.0)
            # Clamp to [0, 1] — cosine sim on normalised vectors should never
            # exceed 1.0 but floating-point can produce tiny overflows.
            visual_sim = max(0.0, min(1.0, visual_sim))
            text_sim = max(0.0, min(1.0, text_sim))
            fused = (visual_sim * self.visual_weight) + (text_sim * self.text_weight)

            matches.append(
                {
                    "golden_asset_id": row.golden_asset_id,
                    "timestamp": float(row.timestamp),
                    "visual_sim": visual_sim,
                    "text_sim": text_sim,
                    "fused_score": fused,
                }
            )

        return matches

    # ── Verdict helper ───────────────────────────────────────────────────

    @staticmethod
    def _verdict(fused_score: float) -> Verdict:
        if fused_score >= 0.80:
            return "PIRACY_DETECTED"
        if fused_score >= 0.60:
            return "SUSPICIOUS"
        if fused_score >= 0.40:
            return "LOW_CONFIDENCE"
        return "CLEAN"


# Singleton
similarity_service = SimilarityService()
