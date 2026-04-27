# app/models/schemas.py
# ══════════════════════════════════════════════════════════════════════════════
#
#  SourceGraph — Pydantic Schema Registry
#  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
#  This file is the single source of truth for every request/response shape
#  in the orchestrator.  It is divided into four sections:
#
#  §1  Primitive type aliases
#       └─ Verdict — shared by similarity_service and feed_controller
#
#  §2  Polymorphic Feeder Payload Block
#       └─ Six Pydantic models + FeederPayload discriminated union
#          These model every event emitted by simulate_ml_stream.py.
#
#  §3  Legacy GPU-node webhook schemas
#       └─ WebhookVectorPayload, WebhookCompletePayload, WebhookAck
#          Used by the /vector and /complete endpoints.
#
#  §4  REST API surface schemas
#       └─ UploadResponse, HealthResponse, FeedEntry,
#          AssetStatusResponse, SimilarityResultResponse
#          Used by golden_controller, search_controller, feed_controller.
#
# ══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ══════════════════════════════════════════════════════════════════════════════
# §1  Primitive type aliases
# ══════════════════════════════════════════════════════════════════════════════

# Verdict is a type alias, not a BaseModel.
# Used as an annotation in SimilarityService and SimilarityResultResponse.
Verdict = Literal["PIRACY_DETECTED", "SUSPICIOUS", "CLEAN"]


# ══════════════════════════════════════════════════════════════════════════════
# §2  Polymorphic Feeder Payload Block
# ══════════════════════════════════════════════════════════════════════════════
#
# Every payload from simulate_ml_stream.py shares two root fields:
#   packet_id : str   — opaque ingest token (maps to Asset.id after lookup)
#   type      : Literal[...]  — the discriminator
#
# Pydantic's Annotated + Field(discriminator="type") union gives us:
#   • Zero-cost parsing — only the matching model is instantiated
#   • Clear 422 errors if a known type arrives with wrong fields
#   • A clean extension point — add a new Literal + model, nothing else changes

class FeederPayloadBase(BaseModel):
    """
    Common root for all feeder events.
    Subclasses pin `type` to a Literal so Pydantic can discriminate.
    """
    packet_id: str  # kept as str — simulator sends hex tokens, not UUIDs
    type: str


# ── 1. system_ping ────────────────────────────────────────────────────────────

class ServiceHealthMap(BaseModel):
    ingest_api: str
    vision_engine: str
    text_processor: str
    orchestrator: str


class SystemPingPayload(FeederPayloadBase):
    type: Literal["system_ping"]
    nodes_online: str              # e.g. "3/3"
    services: ServiceHealthMap


# ── 2. frame_vision  (ml_vision / RTX 3050) ──────────────────────────────────

class FrameVisionPayload(FeederPayloadBase):
    """Vision-node frame embedding.  visual_vector must be exactly 512-D."""
    type: Literal["frame_vision"]
    timestamp: float
    source_node: str
    visual_vector: list[float]

    @field_validator("visual_vector")
    @classmethod
    def validate_visual_vector_dim(cls, v: list[float]) -> list[float]:
        if len(v) != 512:
            raise ValueError(
                f"Expected 512-dimensional visual_vector, received {len(v)} elements."
            )
        return v


# ── 3. frame_text  (ml_context / RTX 2050) ───────────────────────────────────

class FrameTextPayload(FeederPayloadBase):
    type: Literal["frame_text"]
    timestamp: float
    source_node: str
    chunks_extracted: int
    boxes_mapped: int
    ocr_text: str
    text_vector: list[float]

    @field_validator("text_vector")
    @classmethod
    def validate_text_vector_dim(cls, v: list[float]) -> list[float]:
        if len(v) != 384:
            raise ValueError(
                f"Expected 384-dimensional text_vector, received {len(v)} elements."
            )
        return v


# ── 4. vision_final_summary  (Rohit) ─────────────────────────────────────────

class VisionSummaryMetrics(BaseModel):
    vector_embeddings: int
    dimensionality: str            # e.g. "512-D mapped"
    index_status: str
    node_time_s: float


class VisionFinalSummaryPayload(FeederPayloadBase):
    type: Literal["vision_final_summary"]
    source_node: str
    metrics: VisionSummaryMetrics


# ── 5. text_final_summary  (Yug) ─────────────────────────────────────────────

class TextSummaryMetrics(BaseModel):
    ocr_text_chunks: int
    bounding_boxes_mapped: int
    node_time_s: float


class TextFinalSummaryPayload(FeederPayloadBase):
    type: Literal["text_final_summary"]
    source_node: str
    metrics: TextSummaryMetrics


# ── 6. pipeline_final_summary  (Yogesh / M2 Extractor) ───────────────────────
#
#  This is the canonical "all frames dispatched" signal.
#  It drives the asset → 'completed' transition and the Similarity Engine
#  trigger, mirroring the old WebhookCompletePayload contract.

class PipelineSummaryMetrics(BaseModel):
    total_frames_extracted: int
    successful_broadcasts: int
    failed_broadcasts: int
    total_pipeline_time_s: float


class PipelineFinalSummaryPayload(FeederPayloadBase):
    type: Literal["pipeline_final_summary"]
    source_node: str
    metrics: PipelineSummaryMetrics


# ── 7. audio_final_summary  (Vision Node) ────────────────────────────────────

class AudioSegmentItem(BaseModel):
    start: float
    end: float
    text: str

class AudioSummaryPacket(FeederPayloadBase):
    type: Literal["audio_final_summary"]
    source_node: str
    transcript: list[AudioSegmentItem]
    full_script: str



# ── Discriminated union — the single type the /feeder endpoint accepts ────────
#
# Pydantic evaluates the `type` field first and instantiates only the
# matching model.  Unknown `type` values produce a clean 422 with a message
# listing every valid Literal — no ambiguous "union did not match" noise.

FeederPayload = Annotated[
    Union[
        SystemPingPayload,
        FrameVisionPayload,
        FrameTextPayload,
        VisionFinalSummaryPayload,
        TextFinalSummaryPayload,
        PipelineFinalSummaryPayload,
        AudioSummaryPacket,
    ],
    Field(discriminator="type"),
]


# ══════════════════════════════════════════════════════════════════════════════
# §3  Legacy GPU-node webhook schemas
# ══════════════════════════════════════════════════════════════════════════════
#
#  Used by POST /api/v1/webhooks/vector and POST /api/v1/webhooks/complete.
#  These endpoints remain active during the feeder migration window and will
#  be deprecated once all GPU nodes are updated to the polymorphic protocol.

class WebhookVectorPayload(BaseModel):
    """
    Dual-modality vector delivery from a GPU node.
    Either visual_vector OR text_vector may be absent — the BufferService
    holds the partial entry until both arrive.
    """
    packet_id: UUID
    timestamp: float
    visual_vector: list[float] | None = None
    text_vector: list[float] | None = None
    source_node: str | None = None


class WebhookCompletePayload(BaseModel):
    """
    M2 Extractor → Orchestrator completion signal (legacy protocol).
    Signals that ALL frame jobs for the asset have been dispatched.
    """
    packet_id: UUID
    total_frames: int


class WebhookAck(BaseModel):
    """
    Synchronous acknowledgement returned by /vector after ingestion.
    `flushed_to_db=True` indicates the buffer paired both modalities and
    persisted the FrameVector row in this request cycle.
    """
    status: str
    packet_id: str | UUID
    timestamp: float | None = None
    flushed_to_db: bool = False
    trace_id: str


# ══════════════════════════════════════════════════════════════════════════════
# §4  REST API surface schemas
# ══════════════════════════════════════════════════════════════════════════════
#
#  These models are the public-facing contract for the dashboard and upload
#  endpoints.  They are intentionally flat (no nested models) to keep the
#  React Command Center's type generation simple.

# ── Upload ────────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """
    Returned by POST /api/v1/assets/upload.
    The caller should poll GET /api/v1/assets/{asset_id}/status for progress.
    """
    asset_id: UUID
    filename: str
    is_golden: bool
    status: str                    # always 'processing' at upload time
    message: str
    trace_id: str


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """
    Returned by GET / — aggregate counts from PostgreSQL.
    Used by the Command Center dashboard header.
    """
    status: str                    # 'online' | 'degraded'
    machine: str                   # e.g. 'Tanmay-M4'
    role: str                      # 'Orchestrator'
    version: str
    total_assets: int
    golden_assets: int
    suspect_assets: int
    tailscale_ip: str
    nodes: dict[str, str] | None = None


# ── Asset feed ────────────────────────────────────────────────────────────────

class FeedEntry(BaseModel):
    """
    Single row in the paginated asset list (GET /api/v1/assets).
    asset_id is a str rather than UUID so JSON serialization is zero-cost.
    """
    asset_id: str
    filename: str
    is_golden: bool
    status: str                    # 'processing' | 'completed' | 'failed'
    frame_count: int
    created_at: str                # ISO 8601 string — avoids TZ serialization issues


# ── Asset status ──────────────────────────────────────────────────────────────

class AssetStatusResponse(BaseModel):
    """
    Detailed status for a single asset (GET /api/v1/assets/{id}/status).
    Polled by the caller after an upload to track extraction progress.
    """
    asset_id: UUID
    filename: str
    is_golden: bool
    status: str                    # 'processing' | 'completed' | 'failed'
    frame_count: int               # number of FrameVector rows written so far
    created_at: str                # ISO 8601 string
    trace_id: str


# ── Similarity result ─────────────────────────────────────────────────────────

class SimilarityResultResponse(BaseModel):
    """
    Persisted inference verdict for a suspect asset
    (GET /api/v1/assets/{id}/result).

    verdict values:
      PIRACY_DETECTED — fused_score ≥ piracy_threshold
      SUSPICIOUS      — fused_score ≥ suspicious_threshold
      CLEAN           — below both thresholds
    """
    suspect_asset_id: UUID
    golden_asset_id: UUID | None       # None when no golden library exists
    matched_timestamp: float | None    # timestamp of the best-matching frame
    visual_score: float                # cosine similarity, visual modality
    text_score: float                  # cosine similarity, text modality
    fused_score: float                 # weighted combination
    verdict: Verdict
    trace_id: str


# ── Forensic Analysis ─────────────────────────────────────────────────────────

class AnalysisPayload(BaseModel):
    """
    Forensic graph data for the NexusScreen visualization.
    Contains nodes and edges for ReactFlow, plus relevant ingest logs.
    """
    nodes: list[dict]
    edges: list[dict]
    ingest_logs: list[str]
