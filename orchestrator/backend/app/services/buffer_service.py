"""
Async Webhook Buffer Service — dual-modality synchronisation.

Problem
-------
The RTX 3050 (Vision) and RTX 2050 (Text) post vectors to the Orchestrator
independently and at different speeds (Text typically arrives first).
A frame row must not be written to `frame_vectors` until BOTH modalities
have landed — otherwise similarity searches run against partial data.

Design
------
  Key:   (asset_id, quantized_timestamp)
  Value: BufferEntry — accumulates visual and/or text vector
  Flush: When both vectors are present, remove entry and return it.

The caller (webhook_controller) is responsible for writing the flushed
entry to the database.  The buffer is intentionally DB-agnostic.

Eviction Policy
---------------
  1. TTL: entries older than `buffer_ttl_seconds` are evicted by a
     background asyncio task that runs every `buffer_cleanup_interval` s.
     Evicted partial entries are logged with WARN so operators can detect
     nodes that stopped sending.
  2. Capacity: if `max_buffer_size` is reached, the oldest entry is
     evicted before the new one is inserted (FIFO under pressure).

Idempotency
-----------
  If the same vector for a key arrives twice (duplicate delivery), the
  second write is silently dropped.  Only the first arrival is kept.

Observability
-------------
  Every log line carries trace_id so individual packets can be traced
  from upload through buffer through DB insertion.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from app.config import settings
from app.core.logger import get_logger

logger = get_logger("sourcegraph.buffer")


# ── Data model ──────────────────────────────────────────────────────────

@dataclass
class BufferEntry:
    """Accumulates vectors for a single (asset, timestamp) pair."""

    asset_id: UUID
    timestamp: float
    visual_vector: Optional[list[float]] = None
    text_vector: Optional[list[float]] = None
    source_node: Optional[str] = None
    created_at: float = field(default_factory=time.monotonic)
    # Track which trace_id originally created this entry
    trace_id: str = ""

    @property
    def is_complete(self) -> bool:
        """True when both modalities have arrived — ready to flush."""
        return self.visual_vector is not None and self.text_vector is not None

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.created_at

    @property
    def has_visual(self) -> bool:
        return self.visual_vector is not None

    @property
    def has_text(self) -> bool:
        return self.text_vector is not None


@dataclass
class IngestResult:
    """Returned from BufferService.ingest() — describes what happened."""
    accepted: bool
    completed_entry: Optional[BufferEntry]  # non-None when buffer flushed
    duplicate: bool = False
    evicted_stale: bool = False


# ── Timestamp quantisation ───────────────────────────────────────────────

def _quantize(ts: float, slop: float) -> float:
    """
    Round `ts` to the nearest `slop`-second bucket.

    Examples (slop=1.0):  10.3 → 10.0,  10.7 → 11.0
    This lets Vision and Text nodes report slightly different timestamps
    for the same logical frame and still be treated as the same key.
    """
    if slop <= 0.0:
        return ts
    return round(ts / slop) * slop


def _make_key(asset_id: UUID, timestamp: float) -> str:
    qt = _quantize(timestamp, settings.temporal_slop_seconds)
    return f"{asset_id}::{qt:.3f}"


# ── Buffer service ───────────────────────────────────────────────────────

class BufferService:
    """
    Thread-safe in-memory buffer for dual-vector synchronisation.

    Usage (in webhook_controller):
        result = await buffer.ingest(asset_id, timestamp, visual_vector=v)
        if result.completed_entry:
            await write_frame_to_db(result.completed_entry)
    """

    def __init__(self) -> None:
        self._buffer: dict[str, BufferEntry] = {}
        self._insertion_order: list[str] = []  # FIFO eviction under capacity
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]
        self._stats = {"flushed": 0, "evicted_ttl": 0, "evicted_capacity": 0, "duplicates": 0}

    # ── Public API ───────────────────────────────────────────────────────

    async def ingest(
        self,
        asset_id: UUID,
        timestamp: float,
        visual_vector: Optional[list[float]] = None,
        text_vector: Optional[list[float]] = None,
        source_node: Optional[str] = None,
        trace_id: str = "",
    ) -> IngestResult:
        """
        Accept a partial or complete vector delivery.

        Returns an IngestResult.  If `completed_entry` is not None, the
        caller must persist it to the database and may then trigger downstream
        processing.
        """
        key = _make_key(asset_id, timestamp)

        async with self._lock:
            # ── Capacity guard (FIFO eviction) ───────────────────────────
            if len(self._buffer) >= settings.max_buffer_size and key not in self._buffer:
                oldest_key = self._insertion_order.pop(0)
                evicted = self._buffer.pop(oldest_key, None)
                self._stats["evicted_capacity"] += 1
                if evicted:
                    logger.warning(
                        f"[BUFFER] ⚠ Capacity eviction: asset={evicted.asset_id} "
                        f"ts={evicted.timestamp:.3f}s trace={evicted.trace_id}"
                    )

            # ── Get or create entry ───────────────────────────────────────
            entry = self._buffer.get(key)
            is_new = entry is None

            if is_new:
                entry = BufferEntry(
                    asset_id=asset_id,
                    timestamp=timestamp,
                    source_node=source_node,
                    trace_id=trace_id,
                )
                self._buffer[key] = entry
                self._insertion_order.append(key)

            # ── Merge vectors (idempotent — first write wins) ─────────────
            duplicate = False

            if visual_vector is not None:
                if entry.visual_vector is not None:
                    duplicate = True
                    self._stats["duplicates"] += 1
                    logger.debug(
                        f"[BUFFER] Duplicate visual dropped: key={key} trace={trace_id}"
                    )
                else:
                    entry.visual_vector = visual_vector
                    logger.info(
                        f"[BUFFER] 👁  Visual buffered  asset={asset_id} "
                        f"ts={timestamp:.3f}s key={key} trace={trace_id}"
                    )

            if text_vector is not None:
                if entry.text_vector is not None:
                    duplicate = True
                    self._stats["duplicates"] += 1
                    logger.debug(
                        f"[BUFFER] Duplicate text dropped:   key={key} trace={trace_id}"
                    )
                else:
                    entry.text_vector = text_vector
                    logger.info(
                        f"[BUFFER] 📝 Text buffered    asset={asset_id} "
                        f"ts={timestamp:.3f}s key={key} trace={trace_id}"
                    )

            # ── Flush check ───────────────────────────────────────────────
            if entry.is_complete:
                flushed_entry = self._buffer.pop(key)
                self._insertion_order.remove(key)
                self._stats["flushed"] += 1
                logger.info(
                    f"[BUFFER] ⚡ SYNC asset={asset_id} ts={timestamp:.3f}s "
                    f"→ flushing to DB  trace={trace_id}"
                )
                return IngestResult(
                    accepted=True,
                    completed_entry=flushed_entry,
                    duplicate=duplicate,
                )

        return IngestResult(accepted=True, completed_entry=None, duplicate=duplicate)

    async def get_state(self) -> dict:
        """Diagnostic snapshot — exposed via GET /buffer/status."""
        async with self._lock:
            return {
                "pending_count": len(self._buffer),
                "stats": dict(self._stats),
                "entries": [
                    {
                        "key": k,
                        "asset_id": str(e.asset_id),
                        "timestamp": e.timestamp,
                        "has_visual": e.has_visual,
                        "has_text": e.has_text,
                        "age_seconds": round(e.age_seconds, 2),
                        "source_node": e.source_node,
                        "trace_id": e.trace_id,
                    }
                    for k, e in self._buffer.items()
                ],
            }

    # ── Lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background TTL eviction loop (call from lifespan)."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info(
                f"[BUFFER] 🧹 TTL eviction loop started "
                f"(ttl={settings.buffer_ttl_seconds}s, "
                f"interval={settings.buffer_cleanup_interval}s, "
                f"max_size={settings.max_buffer_size})"
            )

    def stop(self) -> None:
        """Cancel the background eviction loop (call from lifespan shutdown)."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("[BUFFER] 🛑 Eviction loop stopped")

    # ── Background eviction ──────────────────────────────────────────────

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(settings.buffer_cleanup_interval)
                evicted = await self._evict_stale()
                if evicted:
                    logger.warning(
                        f"[BUFFER] 🗑  TTL evicted {evicted} partial entries "
                        f"(these vectors will NEVER be written to the DB — "
                        f"check Vision/Text node connectivity)"
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"[BUFFER] Eviction loop error: {exc}")

    async def _evict_stale(self) -> int:
        evicted = 0
        async with self._lock:
            stale_keys = [
                k
                for k, e in self._buffer.items()
                if e.age_seconds > settings.buffer_ttl_seconds
            ]
            for key in stale_keys:
                entry = self._buffer.pop(key)
                if key in self._insertion_order:
                    self._insertion_order.remove(key)
                self._stats["evicted_ttl"] += 1
                evicted += 1
                logger.warning(
                    f"[BUFFER] ⏱  Stale eviction: asset={entry.asset_id} "
                    f"ts={entry.timestamp:.3f}s age={entry.age_seconds:.1f}s "
                    f"visual={entry.has_visual} text={entry.has_text} "
                    f"trace={entry.trace_id}"
                )
        return evicted