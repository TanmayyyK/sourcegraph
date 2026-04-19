"""
client.py — Async Orchestrator Client
Fire-and-forget HTTPX poster for SourcePacket payloads.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("vision.client")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
ORCHESTRATOR_INGEST_URL = "http://100.69.253.89:8000/ingest"

# Timeouts: connect=5 s, total read=30 s.
# These values are intentionally generous — the Orchestrator may be under load.
_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


# ─────────────────────────────────────────────────────────────────────────────
# Async send helper
# ─────────────────────────────────────────────────────────────────────────────

async def post_source_packet(payload: dict[str, Any]) -> None:
    """
    Asynchronously POST *payload* to the Master Orchestrator.

    This function is designed to be scheduled as a FastAPI BackgroundTask,
    so it MUST NOT raise — all errors are logged and swallowed so the main
    worker thread is never blocked or crashed by downstream failures.

    Parameters
    ----------
    payload : dict
        A fully-formed SourcePacket dict (see schemas.py for structure).
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            response = await client.post(
                ORCHESTRATOR_INGEST_URL,
                json=payload,
            )
            response.raise_for_status()
            logger.info(
                "SourcePacket delivered → %s  [HTTP %d]",
                ORCHESTRATOR_INGEST_URL,
                response.status_code,
            )
        except httpx.TimeoutException:
            logger.error(
                "Orchestrator POST timed-out (%s). Packet dropped.",
                ORCHESTRATOR_INGEST_URL,
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Orchestrator returned HTTP %d: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
        except httpx.RequestError as exc:
            logger.error(
                "Network error posting to Orchestrator: %s", exc
            )
        except Exception:
            logger.exception("Unexpected error in post_source_packet.")