"""
Feed & Health Controller — read-only endpoints.

Preserves the original /feed and / endpoint shapes
for backward compatibility with the existing frontend.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from uuid import UUID

from app.core.logger import get_logger
from app.models.schemas import HealthResponse

logger = get_logger("sourcegraph.feed")

router = APIRouter(tags=["feed"])


@router.get(
    "/",
    response_model=HealthResponse,
    summary="Orchestrator health check",
)
async def health_check(request: Request) -> HealthResponse:
    """
    Root health check endpoint.

    Returns system status, packet/match counts, and Tailscale IP.
    Compatible with the existing frontend dashboard polling.
    """
    repo = request.app.state.repository
    return HealthResponse(
        status="online",
        machine="Tanmay-M4",
        role="Orchestrator",
        version="1.0.0",
        active_packets=await repo.packet_count(),
        active_matches=await repo.match_count(),
        tailscale_ip=request.app.state.settings.tailscale_ip,
    )


@router.get(
    "/feed",
    summary="Recent ingestion feed",
)
async def get_feed(request: Request, limit: int = 10) -> list[dict]:
    """
    Returns the last N pieces of data received from worker nodes.

    Response shape matches the original format for frontend compatibility:
    [{ time, video, timestamp, has_visual, has_text, source_node, matched }]
    """
    feed: list[dict] = request.app.state.feed
    return feed[-limit:]


@router.get(
    "/matches",
    summary="Detected piracy matches",
)
async def get_matches(request: Request, limit: int = 50) -> list[dict]:
    """Return all detected matches with scores and verdicts."""
    repo = request.app.state.repository
    matches = await repo.get_matches(limit)
    return [m.model_dump(mode="json") for m in matches]


@router.get(
    "/matches/{match_id}",
    summary="Get a specific match by ID",
)
async def get_match(request: Request, match_id: UUID) -> dict:
    """Return details for a specific match."""
    repo = request.app.state.repository
    match = await repo.get_match(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    return match.model_dump(mode="json")


@router.get(
    "/graph/{match_id}",
    summary="Get propagation graph for a match",
)
async def get_graph(request: Request, match_id: UUID) -> dict:
    """
    Return the propagation graph for a specific match.

    The graph shows the relationship between the Golden Source
    (PRIMARY_SOURCE) and the suspected pirate content (PIRATE_NODE).
    """
    repo = request.app.state.repository
    graph_builder = request.app.state.graph_builder

    match = await repo.get_match(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

    graph = graph_builder.build_graph(match)
    return graph.model_dump(mode="json")


@router.get(
    "/buffer/status",
    summary="Sync buffer diagnostics",
)
async def buffer_status(request: Request) -> dict:
    """Return current state of the sync buffer (pending entries, ages)."""
    buffer = request.app.state.sync_buffer
    return await buffer.get_buffer_state()


@router.get(
    "/golden-sources",
    summary="List all golden source entries",
)
async def list_golden_sources(request: Request) -> list[dict]:
    """Return all protected golden source entries (without full vectors)."""
    golden_lib = request.app.state.golden_library
    entries = golden_lib.get_all()
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "metadata": e.metadata,
            "visual_dim": len(e.visual_vector),
            "text_dim": len(e.text_vector),
        }
        for e in entries
    ]
