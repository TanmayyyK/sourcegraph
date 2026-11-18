"""Find protected assets with pgvector and align their ordered embeddings."""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from difflib import SequenceMatcher
from uuid import UUID

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db_models import Asset, AudioSegment, FrameVector, SimilarityResult

# Bound the cost of candidate discovery and sequence alignment on long uploads.
SEQUENCE_LIMIT = 96
PROBE_LIMIT = 12
CANDIDATE_LIMIT = 12
MODALITIES = (
    (FrameVector, FrameVector.visual_vector, FrameVector.timestamp, "visual_score"),
    (FrameVector, FrameVector.text_vector, FrameVector.timestamp, "text_score"),
    (AudioSegment, AudioSegment.audio_vector, AudioSegment.start_time, "audio_score"),
)


def _sample(rows, limit):
    if len(rows) <= limit:
        return rows
    return [rows[i * (len(rows) - 1) // (limit - 1)] for i in range(limit)]


def _unit_vectors(rows):
    vectors = np.asarray([row[1] for row in rows], dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def _align(query, reference):
    """DTW tolerates changes in playback speed and embedding segment boundaries."""
    similarities = np.clip(_unit_vectors(query) @ _unit_vectors(reference).T, 0, 1)
    n, m = similarities.shape
    cost = np.full((n + 1, m + 1), np.inf)
    steps = np.zeros((n + 1, m + 1), dtype=np.int32)
    cost[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            prev = min(((i - 1, j - 1), (i - 1, j), (i, j - 1)), key=cost.__getitem__)
            cost[i, j] = cost[prev] + 1.0 - similarities[i - 1, j - 1]
            steps[i, j] = steps[prev] + 1
    score = float(np.clip(1.0 - cost[n, m] / steps[n, m], 0, 1))
    timestamp = reference[int(np.argmax(similarities) % m)][0]
    return score, float(timestamp)


def _words(text):
    return re.findall(r"\w+", text.casefold())[:4096]


class SimilarityService:
    async def run_for_asset(
        self, asset_id: UUID, db: AsyncSession, trace_id: str = "",
    ) -> SimilarityResult | None:
        sequences = {}
        candidate_ids = set()
        for model, column, timestamp, name in MODALITIES:
            query = await self._sequence(db, model, column, timestamp, asset_id)
            if not query:
                continue
            sequences[name] = query
            nearest = {}
            for _, vector in _sample(query, PROBE_LIMIT):
                distance = column.cosine_distance(vector)
                stmt = (
                    select(model.asset_id, distance.label("distance"))
                    .join(Asset, Asset.id == model.asset_id)
                    .where(Asset.is_golden.is_(True), Asset.status == "completed",
                           model.asset_id != asset_id, column.is_not(None))
                    .order_by(distance)
                    .limit(settings.knn_top_k)
                )
                for golden_id, value in (await db.execute(stmt)).all():
                    if value is not None:
                        nearest[golden_id] = min(float(value), nearest.get(golden_id, float("inf")))
            candidate_ids.update(sorted(nearest, key=nearest.get)[:CANDIDATE_LIMIT])

        # Older assets may have a transcript but no MiniLM vectors.
        script = await db.scalar(select(Asset.full_transcript).where(Asset.id == asset_id))
        words = _words(script or "")
        if not sequences and not words:
            return None

        legacy_audio = {}
        if words:
            stmt = select(Asset.id, Asset.full_transcript).where(
                Asset.is_golden.is_(True), Asset.status == "completed", Asset.id != asset_id,
                Asset.full_transcript.is_not(None), Asset.full_transcript != "",
            )
            transcripts = (await db.execute(stmt)).all()
            legacy_audio = await asyncio.to_thread(self._transcript_scores, words, transcripts)
            if "audio_score" not in sequences or not candidate_ids:
                candidate_ids.update(sorted(legacy_audio, key=legacy_audio.get, reverse=True)[:CANDIDATE_LIMIT])

        comparisons = defaultdict(dict)
        for model, column, timestamp, name in MODALITIES:
            if name not in sequences:
                continue
            for golden_id in sorted(candidate_ids):
                reference = await self._sequence(db, model, column, timestamp, golden_id)
                if reference:
                    comparisons[golden_id][name] = (sequences[name], reference)

        scores, golden_id, timestamp = await asyncio.to_thread(
            self._rank, candidate_ids, comparisons, legacy_audio,
        )
        fused = scores["fused_score"]
        values = dict(
            **scores, golden_asset_id=golden_id, matched_timestamp=timestamp,
            verdict=self._verdict(fused),
        )
        result = await db.scalar(
            insert(SimilarityResult)
            .values(suspect_asset_id=asset_id, **values)
            .on_conflict_do_update(index_elements=[SimilarityResult.suspect_asset_id], set_=values)
            .returning(SimilarityResult)
        )
        await db.execute(delete(FrameVector).where(
            FrameVector.asset_id == asset_id, FrameVector.is_temporary.is_(True),
        ))
        await db.commit()
        return result

    @staticmethod
    async def _sequence(db, model, column, timestamp, asset_id):
        rows = (await db.execute(
            select(timestamp, column).where(model.asset_id == asset_id, column.is_not(None))
            .order_by(timestamp, model.id)
        )).all()
        return _sample([row for row in rows if np.any(row[1])], SEQUENCE_LIMIT)

    @staticmethod
    def _transcript_scores(words, transcripts):
        scores = {}
        for asset_id, transcript in transcripts:
            reference = _words(transcript)
            if reference:
                score = SequenceMatcher(None, words, reference).ratio()
                if score > 0:
                    scores[asset_id] = score
        return scores

    @staticmethod
    def _rank(candidate_ids, comparisons, legacy_audio):
        weights = {
            "visual_score": settings.fusion_weight_visual,
            "text_score": settings.fusion_weight_text,
            "audio_score": settings.fusion_weight_audio,
        }
        best = {**dict.fromkeys(weights, 0.0), "fused_score": 0.0}
        best_id = best_timestamp = None
        available = {name for channels in comparisons.values() for name in channels}
        if any(asset_id in legacy_audio for asset_id in candidate_ids):
            available.add("audio_score")
        total = sum(weights[name] for name in available)
        for asset_id in sorted(candidate_ids):
            channels = comparisons[asset_id]
            scores = {name: 0.0 for name in weights}
            timestamps = {}
            for name, (query, reference) in channels.items():
                scores[name], timestamps[name] = _align(query, reference)
            if "audio_score" not in channels:
                scores["audio_score"] = legacy_audio.get(asset_id, 0.0)
            fused = sum(weights[name] * scores[name] for name in available) / total if total else 0.0
            if fused > best["fused_score"]:
                best = {**scores, "fused_score": fused}
                best_id = asset_id
                best_timestamp = next((timestamps[name] for name in weights if name in timestamps), None)
        return best, best_id, best_timestamp

    @staticmethod
    def _verdict(score):
        if score >= settings.piracy_threshold:
            return "PIRACY_DETECTED"
        if score >= settings.suspicious_threshold:
            return "SUSPICIOUS"
        if score >= 0.40:
            return "LOW_CONFIDENCE"
        return "CLEAN"


similarity_service = SimilarityService()
