"""
Asynchronous Sync Buffer for dual-vector ingestion.

Waits for both Visual (512-D) and Text (384-D) vectors to arrive
for the same (video_name, quantized_timestamp) key before emitting
a "synced" packet to the downstream similarity engine.

Features:
  - Temporal slop handling (±N seconds)
  - TTL-based eviction to prevent unbounded memory growth
  - asyncio.Lock for thread-safe access
  - Background cleanup coroutine
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable
from uuid import UUID

from app.config import settings
from app.core.logger import get_logger
from app.models.schemas import SourcePacket

logger = get_logger("sourcegraph.buffer")


@dataclass
class BufferEntry:
    """A single entry in the sync buffer, possibly partial."""
    video_name: str
    timestamp: float
    visual_vector: list[float] | None = None
    visual_packet_id: UUID | None = None
    text_vector: list[float] | None = None
    text_packet_id: UUID | None = None
    metadata: dict = field(default_factory=dict)
    source_node: str | None = None
    created_at: float = field(default_factory=time.monotonic)

    @property
    def is_synced(self) -> bool:
        """Both vectors are present."""
        return self.visual_vector is not None and self.text_vector is not None

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.created_at


def _quantize_timestamp(ts: float, slop: float) -> float:
    """
    Quantize a timestamp to the nearest slop-sized bucket.
    E.g., with slop=1.0: 10.3 → 10.0, 10.7 → 11.0
    """
    if slop <= 0:
        return ts
    return round(ts / slop) * slop


class SyncBuffer:
    """
    In-memory sync buffer that waits for paired visual + text vectors.

    When both arrive for the same (video, quantized_ts) key,
    the on_synced callback is invoked with the complete SourcePacket.
    """

    def __init__(
        self,
        on_synced: Callable[[SourcePacket], Awaitable[None]] | None = None,
    ) -> None:
        self._buffer: dict[str, BufferEntry] = {}
        self._lock = asyncio.Lock()
        self._on_synced = on_synced
        self._cleanup_task: asyncio.Task | None = None  # type: ignore[type-arg]

    def _make_key(self, video_name: str, timestamp: float) -> str:
        qt = _quantize_timestamp(timestamp, settings.temporal_slop_seconds)
        return f"{video_name}::{qt:.2f}"

    async def ingest(self, packet: SourcePacket) -> bool:
        """
        Buffer a packet.  Returns True if this packet completed a sync pair.
        """
        key = self._make_key(packet.video_name, packet.timestamp)
        has_visual = any(x != 0.0 for x in packet.visual_vector)
        has_text = any(x != 0.0 for x in packet.text_vector)

        async with self._lock:
            entry = self._buffer.get(key)

            if entry is None:
                # First arrival for this key
                entry = BufferEntry(
                    video_name=packet.video_name,
                    timestamp=packet.timestamp,
                    metadata=packet.metadata,
                    source_node=packet.source_node,
                )
                self._buffer[key] = entry

            # Merge vectors
            if has_visual and entry.visual_vector is None:
                entry.visual_vector = packet.visual_vector
                entry.visual_packet_id = packet.id
                logger.info(
                    f"[BUFFER] Visual vector buffered for {packet.video_name} "
                    f"@ t={packet.timestamp:.2f}s (key={key})"
                )

            if has_text and entry.text_vector is None:
                entry.text_vector = packet.text_vector
                entry.text_packet_id = packet.id
                logger.info(
                    f"[BUFFER] Text vector buffered for {packet.video_name} "
                    f"@ t={packet.timestamp:.2f}s (key={key})"
                )

            if entry.is_synced:
                logger.info(
                    f"[SYNC] ⚡ Vectors SYNCED for {entry.video_name} "
                    f"@ t={entry.timestamp:.2f}s — triggering analysis"
                )
                # Build the synced packet
                synced_packet = SourcePacket(
                    video_name=entry.video_name,
                    timestamp=entry.timestamp,
                    visual_vector=entry.visual_vector,  # type: ignore[arg-type]
                    text_vector=entry.text_vector,  # type: ignore[arg-type]
                    metadata=entry.metadata,
                    source_node=entry.source_node,
                )
                # Remove from buffer
                del self._buffer[key]

                # Fire callback (outside lock context would be better,
                # but kept simple for Phase 1)
                if self._on_synced:
                    await self._on_synced(synced_packet)

                return True

        return False

    async def start_cleanup_loop(self) -> None:
        """Background coroutine that evicts stale buffer entries."""
        logger.info("[BUFFER] 🧹 TTL cleanup loop started "
                    f"(ttl={settings.buffer_ttl_seconds}s, "
                    f"interval={settings.buffer_cleanup_interval}s)")

        while True:
            await asyncio.sleep(settings.buffer_cleanup_interval)
            evicted = await self._evict_stale()
            if evicted > 0:
                logger.info(f"[BUFFER] 🗑️  Evicted {evicted} stale entries")

    async def _evict_stale(self) -> int:
        """Remove entries older than TTL. Returns count of evicted entries."""
        evicted = 0
        async with self._lock:
            stale_keys = [
                k for k, v in self._buffer.items()
                if v.age_seconds > settings.buffer_ttl_seconds
            ]
            for key in stale_keys:
                entry = self._buffer.pop(key)
                logger.debug(
                    f"[BUFFER] Evicted partial entry: {entry.video_name} "
                    f"@ t={entry.timestamp:.2f}s (age={entry.age_seconds:.1f}s)"
                )
                evicted += 1
        return evicted

    async def get_buffer_state(self) -> dict:
        """Return current buffer state for diagnostics."""
        async with self._lock:
            return {
                "pending_entries": len(self._buffer),
                "entries": [
                    {
                        "key": k,
                        "video": v.video_name,
                        "timestamp": v.timestamp,
                        "has_visual": v.visual_vector is not None,
                        "has_text": v.text_vector is not None,
                        "age_seconds": round(v.age_seconds, 1),
                    }
                    for k, v in self._buffer.items()
                ],
            }

    def start(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self.start_cleanup_loop())

    def stop(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
