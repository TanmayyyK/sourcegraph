"""
SQLAlchemy ORM models — production schema.

Tables
------
assets          — One row per ingested video (golden or suspect).
frame_vectors   — Per-frame embeddings; the core search surface.
similarity_results — Persisted inference outcomes for audit trail.

HNSW indexes are declared inside __table_args__ so they are created
atomically with the table during `Base.metadata.create_all`.

Index parameters
  m=16             — graph connectivity; 16 is the pgvector default
  ef_construction=64 — build-time beam width (accuracy vs. speed)
  vector_cosine_ops — cosine distance operator class
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── assets ───────────────────────────────────────────────────────────────

class Asset(Base):
    """
    One row per ingested video file.

    is_golden=True  → Protected Library (PRODUCER upload)
    is_golden=False → Suspect Clip (AUDITOR upload)

    Status lifecycle:
        processing → completed
                   ↘ failed
    """

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    is_golden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 'processing' | 'completed' | 'failed'
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    frames: Mapped[list["FrameVector"]] = relationship(
        "FrameVector", back_populates="asset", cascade="all, delete-orphan"
    )
    similarity_result: Mapped["SimilarityResult | None"] = relationship(
        "SimilarityResult",
        foreign_keys="SimilarityResult.suspect_asset_id",
        back_populates="suspect_asset",
        uselist=False,
    )


# ── frame_vectors ────────────────────────────────────────────────────────

class FrameVector(Base):
    """
    Per-frame dual embedding.

    visual_vector  — 512-D CLIP embedding from the RTX 3050 Vision Node.
    text_vector    — 384-D MiniLM embedding from the RTX 2050 Text Node.

    Both arrive asynchronously via the webhook buffer; a row is only
    inserted once BOTH modalities have landed (buffer guarantees this).

    Idempotency: (asset_id, timestamp) has a UNIQUE constraint so that
    duplicate webhook deliveries are silently rejected.
    """

    __tablename__ = "frame_vectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    visual_vector = mapped_column(Vector(512), nullable=False)
    text_vector = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    asset: Mapped[Asset] = relationship("Asset", back_populates="frames")

    __table_args__ = (
        # Idempotency: prevent duplicate (asset, timestamp) rows
        Index("uq_frame_asset_timestamp", "asset_id", "timestamp", unique=True),
        # HNSW cosine index on visual_vector — sub-50ms at scale
        Index(
            "ix_frame_visual_hnsw",
            "visual_vector",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"visual_vector": "vector_cosine_ops"},
        ),
        # HNSW cosine index on text_vector
        Index(
            "ix_frame_text_hnsw",
            "text_vector",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"text_vector": "vector_cosine_ops"},
        ),
    )


# ── similarity_results ───────────────────────────────────────────────────

class SimilarityResult(Base):
    """
    Persisted inference result for a suspect asset.

    Created after the Similarity Engine completes for a non-golden asset.
    Provides a full audit trail: who matched what, at what confidence.
    """

    __tablename__ = "similarity_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    suspect_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One result per suspect asset
    )
    golden_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    matched_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    visual_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    text_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fused_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 'PIRACY_DETECTED' | 'SUSPICIOUS' | 'CLEAN'
    verdict: Mapped[str] = mapped_column(String(32), nullable=False, default="CLEAN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    suspect_asset: Mapped[Asset] = relationship(
        "Asset",
        foreign_keys=[suspect_asset_id],
        back_populates="similarity_result",
    )