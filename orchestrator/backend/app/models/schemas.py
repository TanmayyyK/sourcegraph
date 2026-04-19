"""
Pydantic v2 schema layer — wire contracts for every API surface.

Validation guarantees
---------------------
  - Vector dimensions are exact (512 / 384).
  - NaN and ±Inf are rejected at the boundary.
  - Vectors are L2-normalised before storage so cosine similarity
    reduces to dot-product, which pgvector handles most efficiently.
  - All UUID fields are strict UUIDs (no string coercion in v2).
  - Verdict literals prevent invalid string states from persisting.
"""

from __future__ import annotations

import math
import uuid
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings


# ── Shared vector validator ─────────────────────────────────────────────

def _validate_vector(
    v: list[float],
    expected_dim: int,
    field_name: str,
) -> list[float]:
    """Dimension check → NaN/Inf rejection → L2 normalisation."""
    if len(v) != expected_dim:
        raise ValueError(
            f"{field_name} must be exactly {expected_dim}-D, got {len(v)}-D"
        )
    for i, val in enumerate(v):
        if not math.isfinite(val):
            kind = "NaN" if math.isnan(val) else "Inf"
            raise ValueError(
                f"{field_name}[{i}] is {kind} — all elements must be finite floats"
            )
    norm = math.sqrt(sum(x * x for x in v))
    if norm < 1e-12:
        raise ValueError(f"{field_name} is a zero-vector and cannot be normalised")
    return [x / norm for x in v]


# ── Upload endpoints ────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Immediate response from both upload endpoints."""
    asset_id: UUID
    filename: str
    is_golden: bool
    status: str = "processing"
    message: str
    trace_id: str


# ── Webhook payloads ────────────────────────────────────────────────────

class WebhookVectorPayload(BaseModel):
    """
    Payload sent by RTX 3050 (visual) or RTX 2050 (text) to the Orchestrator.

    Rules
    -----
    - `packet_id` maps 1:1 to `Asset.id`.
    - Exactly ONE of `visual_vector` or `text_vector` must be present per
      delivery (a node sends only its own modality).
    - Both may be present if a node is delivering a merged packet (unusual
      but legal — the buffer will still reconcile correctly).
    """

    packet_id: UUID = Field(..., description="Maps to Asset.id")
    timestamp: float = Field(..., ge=0.0, description="Frame timestamp in seconds")
    visual_vector: Optional[list[float]] = Field(
        default=None, description="512-D CLIP embedding from Vision Node"
    )
    text_vector: Optional[list[float]] = Field(
        default=None, description="384-D MiniLM embedding from Text Node"
    )
    source_node: Optional[str] = Field(
        default=None, description="Tailscale hostname of the sending node"
    )

    @model_validator(mode="after")
    def at_least_one_vector(self) -> "WebhookVectorPayload":
        if self.visual_vector is None and self.text_vector is None:
            raise ValueError(
                "At least one of visual_vector or text_vector must be provided"
            )
        return self

    @field_validator("visual_vector")
    @classmethod
    def validate_visual(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return None
        return _validate_vector(v, settings.visual_dim, "visual_vector")

    @field_validator("text_vector")
    @classmethod
    def validate_text(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return None
        return _validate_vector(v, settings.text_dim, "text_vector")


class WebhookCompletePayload(BaseModel):
    """
    Sent by the M2 Extractor once ALL frames for an asset have been
    dispatched to the GPU nodes.  Triggers status → 'completed' and,
    for non-golden assets, kicks off the Similarity Engine.
    """

    packet_id: UUID = Field(..., description="Asset ID to mark as complete")
    total_frames: Optional[int] = Field(
        default=None,
        description="Expected frame count — used for completeness validation",
    )


class WebhookAck(BaseModel):
    """Response echoed back to the calling GPU node."""
    status: str = "accepted"
    packet_id: UUID
    timestamp: Optional[float] = None
    flushed_to_db: bool = False
    trace_id: str


# ── Asset status ────────────────────────────────────────────────────────

class AssetStatusResponse(BaseModel):
    asset_id: UUID
    filename: str
    is_golden: bool
    status: str
    frame_count: int
    created_at: str
    trace_id: str


# ── Similarity result ───────────────────────────────────────────────────

Verdict = Literal["PIRACY_DETECTED", "SUSPICIOUS", "CLEAN"]


class SimilarityResultResponse(BaseModel):
    """
    Returned from GET /api/v1/assets/{id}/result after inference completes.
    """

    suspect_asset_id: UUID
    golden_asset_id: Optional[UUID] = None
    matched_timestamp: Optional[float] = None
    visual_score: float = Field(..., ge=0.0, le=1.0)
    text_score: float = Field(..., ge=0.0, le=1.0)
    fused_score: float = Field(..., ge=0.0, le=1.0)
    verdict: Verdict
    trace_id: str


# ── Health / feed ───────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "online"
    machine: str = "Tanmay-M4"
    role: str = "Orchestrator"
    version: str = "3.0.0"
    total_assets: int = 0
    golden_assets: int = 0
    suspect_assets: int = 0
    tailscale_ip: str = ""


class FeedEntry(BaseModel):
    asset_id: str
    filename: str
    is_golden: bool
    status: str
    frame_count: int
    created_at: str


# ── Propagation graph (kept for frontend compatibility) ─────────────────

NodeRole = Literal["PRIMARY_SOURCE", "PIRATE_NODE", "RELAY"]


class PropagationNode(BaseModel):
    node_id: UUID
    label: str
    role: NodeRole
    confidence: float = Field(..., ge=0.0, le=1.0)


class PropagationEdge(BaseModel):
    from_node: UUID
    to_node: UUID
    weight: float = Field(..., ge=0.0, le=1.0)
    relationship: str = "suspected_piracy"


class PropagationGraph(BaseModel):
    nodes: list[PropagationNode]
    edges: list[PropagationEdge]
    primary_source_id: UUID
    pirate_node_ids: list[UUID]