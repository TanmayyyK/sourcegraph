"""
SQLAlchemy ORM models — production schema.

Tables
──────
assets              — One row per ingested video (golden or suspect).
frame_vectors       — Per-frame paired embeddings; core similarity-search surface.
                      Populated by the LEGACY /vector webhook via BufferService.
                      Only written once BOTH visual (512-D) + text (384-D)
                      modalities have arrived and been paired by the buffer.

frame_vision_metadata — Raw OCR/detection metadata from the Vision Node (Yug).
                        Populated by the NEW /feeder webhook (frame_vision events).
                        Stores chunk counts and bounding-box counts per frame.
                        Staging table — does NOT feed the similarity engine.

frame_embeddings    — Raw 512-D text embeddings from the Text Node (Rohit).
                      Populated by the NEW /feeder webhook (frame_text_vector events).
                      Staging table — does NOT feed the similarity engine directly.

similarity_results  — Persisted inference outcomes for audit trail.
users               — Passwordless user accounts and OTP handling.

Architecture note on the two staging tables
────────────────────────────────────────────
The feeder simulator fires `frame_vision` (Yug) and `frame_text_vector`
(Rohit) independently.  Unlike the legacy architecture which merges both
modalities in-memory (BufferService → FrameVector), the feeder stores
them in separate tables to preserve the raw audit trail.  The similarity
engine continues to operate on `frame_vectors` populated by the legacy
path until the feeder pipeline is fully promoted.

Idempotency design for staging tables
──────────────────────────────────────
Because the feeder simulator sends a string `packet_id` (e.g.
"ingest_a1b2c3d4") rather than a real UUID, the UNIQUE constraint on the
staging tables is keyed on (packet_id, timestamp, source_node) — not on
(asset_id, timestamp, source_node) — so idempotency works even when
asset_id cannot yet be resolved.  The `asset_id` FK column is NULLABLE
and will be populated once the simulator is updated to send real UUIDs.

HNSW indexes (frame_vectors)
─────────────────────────────
  m=16             — graph connectivity (pgvector default)
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
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ══════════════════════════════════════════════════════════════════════════════
# users
# Defined FIRST so the FK in Asset(users.id) resolves without forward-ref
# issues.
# ══════════════════════════════════════════════════════════════════════════════

class User(Base):
    """
    Overwatch user accounts (Passwordless).

    Roles: 'PRODUCER' | 'AUDITOR'
    OTP flow uses login_code and login_code_expires.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Commander"
    )
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="AUDITOR"
    )

    # Temporary fields for OTP / Magic Link login
    login_code: Mapped[str | None] = mapped_column(
        String(6), nullable=True
    )
    login_code_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationships
    assets: Mapped[list["Asset"]] = relationship(
        "Asset", back_populates="uploader"
    )


# ══════════════════════════════════════════════════════════════════════════════
# assets
# ══════════════════════════════════════════════════════════════════════════════

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
    is_golden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # 'processing' | 'completed' | 'failed'
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="processing"
    )
    full_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_summary_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    pipeline_summary_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    auditor_dispatched: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Telemetry metrics from GPU nodes
    vision_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Auth linkage (nullable to protect legacy data)
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    # Relationships
    uploader: Mapped["User | None"] = relationship(
        "User", back_populates="assets"
    )
    frames: Mapped[list["FrameVector"]] = relationship(
        "FrameVector", back_populates="asset", cascade="all, delete-orphan"
    )
    similarity_result: Mapped["SimilarityResult | None"] = relationship(
        "SimilarityResult",
        foreign_keys="SimilarityResult.suspect_asset_id",
        back_populates="suspect_asset",
        uselist=False,
    )
    # Feeder staging relationships (nullable asset_id → viewlist only for
    # rows where the FK was resolved; rows with NULL asset_id are excluded
    # from these collections automatically by SQLAlchemy's FK join).
    vision_metadata: Mapped[list["FrameVisionMetadata"]] = relationship(
        "FrameVisionMetadata",
        back_populates="asset",
        cascade="all, delete-orphan",
    )
    embeddings: Mapped[list["FrameEmbedding"]] = relationship(
        "FrameEmbedding",
        back_populates="asset",
        cascade="all, delete-orphan",
    )
    audio_segments: Mapped[list["AudioSegment"]] = relationship(
        "AudioSegment",
        back_populates="asset",
        cascade="all, delete-orphan",
    )


# ══════════════════════════════════════════════════════════════════════════════
# frame_vectors  (legacy / production similarity surface)
# ══════════════════════════════════════════════════════════════════════════════

class FrameVector(Base):
    """
    Per-frame dual embedding — the core search surface for the similarity engine.

    visual_vector  — 512-D CLIP embedding from the RTX 3050 Vision Node.
    text_vector    — 384-D MiniLM embedding from the RTX 2050 Text Node.

    Rows are written by the legacy /vector webhook once BufferService has
    received and paired BOTH modalities.  The feeder staging tables
    (FrameVisionMetadata, FrameEmbedding) do NOT populate this table.

    Idempotency: (asset_id, timestamp) UNIQUE prevents duplicate rows from
    network retries on the legacy path.
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
    visual_vector = mapped_column(Vector(512), nullable=True)
    text_vector = mapped_column(Vector(384), nullable=True)
    is_temporary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    asset: Mapped[Asset] = relationship("Asset", back_populates="frames")

    __table_args__ = (
        # Idempotency: prevent duplicate (asset, timestamp) rows
        Index(
            "uq_frame_asset_timestamp",
            "asset_id",
            "timestamp",
            unique=True,
        ),
        Index(
            "ix_frame_asset_temporary",
            "asset_id",
            "is_temporary",
        ),
        # HNSW cosine index on visual_vector — sub-50ms KNN at scale
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


# ══════════════════════════════════════════════════════════════════════════════
# frame_vision_metadata  (feeder staging — Vision Node / Yug)
# ══════════════════════════════════════════════════════════════════════════════

class FrameVisionMetadata(Base):
    """
    Staging table for `frame_vision` events from the Vision Node (Yug / RTX 2050).

    Stores OCR chunk counts and bounding-box counts per frame.  This is
    NOT the visual embedding — it is raw detection metadata used for audit
    and pipeline observability.

    Idempotency key: (packet_id, timestamp, source_node)
    ────────────────────────────────────────────────────
    The feeder simulator sends an opaque hex token (e.g. "ingest_a1b2c3d4")
    as packet_id rather than a real UUID.  The unique constraint is therefore
    keyed on the string packet_id so idempotency is guaranteed even when
    asset_id cannot be resolved.

    asset_id is NULLABLE:
      • NULL  — packet_id was not a valid UUID (simulator mode)
      • UUID  — packet_id resolved to a real Asset row (production mode)

    Promotion path: once the simulator sends real UUIDs, a backfill migration
    can UPDATE asset_id WHERE asset_id IS NULL AND packet_id = assets.id::text.
    """

    __tablename__ = "frame_vision_metadata"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Raw feeder token — always present, drives idempotency
    packet_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # FK to assets — nullable until packet_id is a real UUID
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    source_node: Mapped[str] = mapped_column(String(128), nullable=False)

    # OCR / detection payload from Yug
    chunks_extracted: Mapped[int] = mapped_column(Integer, nullable=False)
    boxes_mapped: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationship (only populated when asset_id is non-NULL)
    asset: Mapped[Asset | None] = relationship(
        "Asset", back_populates="vision_metadata"
    )

    __table_args__ = (
        # Idempotency — keyed on packet_id (string), not asset_id (nullable UUID)
        Index(
            "uq_fvm_packet_ts_node",
            "packet_id",
            "timestamp",
            "source_node",
            unique=True,
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# frame_embeddings  (feeder staging — Text Node / Rohit)
# ══════════════════════════════════════════════════════════════════════════════

class FrameEmbedding(Base):
    """
    Staging table for `frame_text_vector` events from the Text Node
    (Rohit / RTX 3050).

    Stores the 512-D embedding vector for each frame.  The vector is
    validated to exactly 512 dimensions by the Pydantic schema before
    it reaches this table.

    This table is a staging store for the feeder pipeline.  The similarity
    engine currently operates on `frame_vectors` (legacy path).  A future
    migration will promote these embeddings into `frame_vectors` once the
    feeder pipeline is fully verified.

    Idempotency key: (packet_id, timestamp, source_node)
    ────────────────────────────────────────────────────
    Same nullable asset_id design as FrameVisionMetadata — see that
    docstring for the full rationale.

    HNSW index:
      An HNSW cosine index is declared on `vector` so that future KNN
      queries against this staging table are fast from day one.
    """

    __tablename__ = "frame_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Raw feeder token — always present, drives idempotency
    packet_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # FK to assets — nullable until packet_id is a real UUID
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    source_node: Mapped[str] = mapped_column(String(128), nullable=False)

    # 512-D embedding from Rohit (validated in FrameTextVectorPayload)
    vector = mapped_column(Vector(512), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationship (only populated when asset_id is non-NULL)
    asset: Mapped[Asset | None] = relationship(
        "Asset", back_populates="embeddings"
    )

    __table_args__ = (
        # Idempotency — keyed on packet_id (string), not asset_id (nullable UUID)
        Index(
            "uq_fe_packet_ts_node",
            "packet_id",
            "timestamp",
            "source_node",
            unique=True,
        ),
        # HNSW cosine index — ready for future KNN queries against this table
        Index(
            "ix_fe_vector_hnsw",
            "vector",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"vector": "vector_cosine_ops"},
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# similarity_results
# ══════════════════════════════════════════════════════════════════════════════

class SimilarityResult(Base):
    """
    Persisted inference result for a suspect asset.

    Created after the Similarity Engine completes for a non-golden asset.
    Provides a full audit trail: which golden asset matched, at what score,
    at what frame timestamp.
    """

    __tablename__ = "similarity_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    suspect_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One result row per suspect asset
    )
    golden_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    matched_timestamp: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    visual_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    text_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    fused_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    # 'PIRACY_DETECTED' | 'SUSPICIOUS' | 'CLEAN'
    verdict: Mapped[str] = mapped_column(
        String(32), nullable=False, default="CLEAN"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    suspect_asset: Mapped[Asset] = relationship(
        "Asset",
        foreign_keys=[suspect_asset_id],
        back_populates="similarity_result",
    )


# ══════════════════════════════════════════════════════════════════════════════
# audio_segments
# ══════════════════════════════════════════════════════════════════════════════

class AudioSegment(Base):
    """
    Temporal audio data from the Vision Node.
    """
    __tablename__ = "audio_segments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    segment_text: Mapped[str] = mapped_column(Text, nullable=False)

    asset: Mapped[Asset] = relationship("Asset", back_populates="audio_segments")
