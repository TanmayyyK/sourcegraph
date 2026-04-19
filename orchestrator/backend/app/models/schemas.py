"""
Pydantic models with strict type safety.

All vector fields undergo:
  1. Dimension validation (512 for visual, 384 for text)
  2. NaN / Inf rejection
  3. L2 normalization before storage

Python 3.12+ type hints throughout.
"""

from __future__ import annotations

import math
from typing import Any, List, Literal, Optional, Dict, Union
from typing_extensions import TypeAlias
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings


# ── Type Aliases (3.9-compatible) ──────────────────────────────

Verdict: TypeAlias = Literal["PIRATE", "CLEAN", "SUSPICIOUS"]
NodeRole: TypeAlias = Literal["PRIMARY_SOURCE", "PIRATE_NODE", "RELAY"]
VectorF: TypeAlias = List[float]


# ══════════════════════════════════════════════════════════════
# Shared Validators
# ══════════════════════════════════════════════════════════════

def _validate_vector(v: list[float], expected_dim: int, field_name: str) -> list[float]:
    """Validate dimensions, reject NaN/Inf, L2-normalize."""
    if len(v) != expected_dim:
        raise ValueError(
            f"{field_name} must be exactly {expected_dim}-D, got {len(v)}-D"
        )

    for i, val in enumerate(v):
        if math.isnan(val) or math.isinf(val):
            raise ValueError(
                f"{field_name}[{i}] contains {'NaN' if math.isnan(val) else 'Inf'} — "
                f"all values must be finite floats"
            )

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in v))
    if norm < 1e-12:
        raise ValueError(f"{field_name} is a zero vector — cannot normalize")

    return [x / norm for x in v]


# ══════════════════════════════════════════════════════════════
# Ingestion Models
# ══════════════════════════════════════════════════════════════

class SourcePacket(BaseModel):
    """
    A single data packet arriving from a worker node.

    Wire-compatible with the existing flat payload format:
    the UUID is auto-generated if not provided.
    """

    id: UUID = Field(default_factory=uuid4)
    video_name: str = Field(..., min_length=1, max_length=256)
    timestamp: float = Field(..., ge=0.0)
    visual_vector: VectorF = Field(..., description="512-D CLIP visual embedding")
    text_vector: VectorF = Field(..., description="384-D MiniLM text embedding")
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_node: str | None = Field(default=None, description="Tailscale node name")

    @field_validator("visual_vector")
    @classmethod
    def validate_visual(cls, v: list[float]) -> list[float]:
        return _validate_vector(v, settings.visual_dim, "visual_vector")

    @field_validator("text_vector")
    @classmethod
    def validate_text(cls, v: list[float]) -> list[float]:
        return _validate_vector(v, settings.text_dim, "text_vector")


class LegacyIngestPayload(BaseModel):
    """
    Backward-compatible payload matching the current worker format.
    Converts to SourcePacket internally.
    """

    video_name: str
    timestamp: float
    visual_vector: list[float]
    text_vector: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_node: str | None = None

    def to_source_packet(self) -> SourcePacket:
        """Convert legacy format → SourcePacket with auto-UUID."""
        text_vec = self.text_vector if self.text_vector else [0.0] * settings.text_dim
        return SourcePacket(
            video_name=self.video_name,
            timestamp=self.timestamp,
            visual_vector=self.visual_vector,
            text_vector=text_vec,
            metadata=self.metadata,
            source_node=self.source_node,
        )


# ══════════════════════════════════════════════════════════════
# Response Models
# ══════════════════════════════════════════════════════════════

class IngestResponse(BaseModel):
    """Response returned from /ingest."""
    status: str = "accepted"
    packet_id: UUID
    buffered: bool = True
    message: str = "Packet buffered; sync check in progress"


class MatchResult(BaseModel):
    """Result of comparing a suspect against a golden source."""
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    source_name: str
    suspect_id: UUID
    suspect_video: str
    visual_score: float = Field(..., ge=0.0, le=1.0)
    text_score: float = Field(..., ge=0.0, le=1.0)
    temporal_score: float = Field(default=0.0, ge=0.0, le=1.0)
    fused_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    verdict: Verdict


# ══════════════════════════════════════════════════════════════
# Propagation Graph Models
# ══════════════════════════════════════════════════════════════

class PropagationNode(BaseModel):
    """A node in the piracy propagation graph."""
    node_id: UUID
    label: str
    role: NodeRole
    confidence: float = Field(..., ge=0.0, le=1.0)


class PropagationEdge(BaseModel):
    """A directed edge in the propagation graph."""
    from_node: UUID
    to_node: UUID
    weight: float = Field(..., ge=0.0, le=1.0)
    relationship: str = "derived_from"


class PropagationGraph(BaseModel):
    """Full propagation graph for a piracy detection event."""
    nodes: list[PropagationNode]
    edges: list[PropagationEdge]
    primary_source_id: UUID
    pirate_node_ids: list[UUID]


# ══════════════════════════════════════════════════════════════
# Simulation Models
# ══════════════════════════════════════════════════════════════

class SimulationRequest(BaseModel):
    """Configuration for a simulation run."""
    noise_level: float = Field(default=0.15, ge=0.0, le=1.0, description="Noise injected into pirate vectors")
    golden_source_name: str | None = Field(default=None, description="Specific golden source to test against")


class SimulationResult(BaseModel):
    """Full result from /simulate/match."""
    golden_source_name: str
    golden_source_id: UUID
    pirate_video_name: str
    pirate_packet_id: UUID
    match_result: MatchResult
    propagation_graph: PropagationGraph
    summary: str


# ══════════════════════════════════════════════════════════════
# Feed / Health Models
# ══════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "online"
    machine: str = "Tanmay-M4"
    role: str = "Orchestrator"
    version: str = "1.0.0"
    active_packets: int = 0
    active_matches: int = 0
    tailscale_ip: str = ""


class FeedEntry(BaseModel):
    """A slim feed entry for the frontend dashboard."""
    time: str
    video: str
    timestamp: float
    has_visual: bool
    has_text: bool
    source_node: str | None = None
    matched: bool = False
