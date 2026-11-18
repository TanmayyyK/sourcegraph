"""
Similarity Engine — KNN search backed by pgvector HNSW indexes.

Algorithm
---------
For each suspect frame:
  1. Execute a pgvector KNN query using the `<=>` cosine distance operator.
     The HNSW index makes this sub-50ms even at millions of vectors.
  2. Convert distance → similarity:  sim = 1 - distance
  3. Compare ordered transcript words when the remote embedding service is
     unavailable, then fuse visual, audio, and OCR scores per golden asset.

Asset-level verdict:
  Take the maximum fused score across golden assets.
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
import re
from difflib import SequenceMatcher
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select, literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logger import get_logger
from app.models.db_models import Asset, AudioSegment, FrameVector, SimilarityResult
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
        audio_weight: float = settings.fusion_weight_audio,
        top_k: int = settings.knn_top_k,
    ) -> None:
        self.visual_weight = visual_weight
        self.text_weight = text_weight
        self.audio_weight = audio_weight
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

        audio_result = await db.execute(
            select(AudioSegment)
            .where(AudioSegment.asset_id == asset_id)
            .order_by(AudioSegment.start_time)
        )
        suspect_audio = audio_result.scalars().all()

        if not suspect_frames and not suspect_audio:
            logger.warning(
                f"[SIMILARITY] No frames found for asset={asset_id} trace={trace_id}"
            )
            return None

        logger.info(
            f"[SIMILARITY] Loaded {len(suspect_frames)} suspect frames "
            f"asset={asset_id} trace={trace_id}"
        )

        # ── 2. KNN against all golden frames ─────────────────────────────
        candidates: dict[UUID, dict[str, Any]] = {}

        for frame in suspect_frames:
            matches = await self._knn_for_frame(
                visual_vec=frame.visual_vector,
                text_vec=frame.text_vector,
                db=db,
                trace_id=trace_id,
            )
            for match in matches:
                golden_id = match["golden_asset_id"]
                current = candidates.get(golden_id)
                if current is None or match["fused_score"] > current["fused_score"]:
                    candidates[golden_id] = match

        if suspect_audio:
            golden_result = await db.execute(
                select(AudioSegment)
                .join(Asset, Asset.id == AudioSegment.asset_id)
                .where(Asset.is_golden.is_(True))
                .order_by(AudioSegment.asset_id, AudioSegment.start_time)
            )
            golden_audio: dict[UUID, list[str]] = defaultdict(list)
            for segment in golden_result.scalars():
                golden_audio[segment.asset_id].append(segment.segment_text)
            suspect_words = self._words([segment.segment_text for segment in suspect_audio])
            for golden_id, texts in golden_audio.items():
                golden_words = self._words(texts)
                if not suspect_words or not golden_words:
                    continue
                audio_sim = SequenceMatcher(None, suspect_words, golden_words, autojunk=False).ratio()
                candidate = candidates.setdefault(golden_id, {
                    "golden_asset_id": golden_id,
                    "timestamp": 0.0,
                    "visual_sim": 0.0,
                    "text_sim": 0.0,
                    "fused_score": 0.0,
                    "has_visual": False,
                    "has_text": False,
                })
                candidate["audio_sim"] = audio_sim

        has_visual = any(candidate.get("has_visual") for candidate in candidates.values())
        has_text = any(candidate.get("has_text") for candidate in candidates.values())
        has_audio = any("audio_sim" in candidate for candidate in candidates.values())
        for candidate in candidates.values():
            weights = []
            if has_visual:
                weights.append((self.visual_weight, candidate["visual_sim"]))
            if has_text:
                weights.append((self.text_weight, candidate["text_sim"]))
            if has_audio:
                weights.append((self.audio_weight, candidate.get("audio_sim", 0.0)))
            total = sum(weight for weight, _ in weights)
            candidate["fused_score"] = sum(weight * score for weight, score in weights) / total if total else 0.0

        best = max(candidates.values(), key=lambda item: item["fused_score"], default=None)

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
                audio_score=0.0,
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
                audio_score=best.get("audio_sim", 0.0),
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

    @staticmethod
    def _words(segments: list[str]) -> list[str]:
        return re.findall(r"\w+", " ".join(segments).casefold())

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
        if visual_vec is None and text_vec is None:
            return []
        ordering_vec = FrameVector.visual_vector if visual_vec is not None else FrameVector.text_vector
        query_vec = visual_vec if visual_vec is not None else text_vec
        stmt = (
            select(
                FrameVector.asset_id.label("golden_asset_id"),
                FrameVector.timestamp,
                # 1 - <=> gives cosine similarity (0..1 for normalised vectors)
                (1 - FrameVector.visual_vector.cosine_distance(visual_vec) if visual_vec is not None else literal(0.0)).label("visual_sim"),
                (1 - FrameVector.text_vector.cosine_distance(text_vec) if text_vec is not None else literal(0.0)).label("text_sim"),
            )
            .join(Asset, Asset.id == FrameVector.asset_id)
            .where(Asset.is_golden.is_(True), ordering_vec.is_not(None))
            # ORDER BY pushes the query into the HNSW index
            .order_by(ordering_vec.cosine_distance(query_vec))
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
                    "has_visual": visual_vec is not None and row.visual_sim is not None,
                    "has_text": text_vec is not None and row.text_sim is not None,
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
