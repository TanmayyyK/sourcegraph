"""
client.py — Async Orchestrator Client
Fire-and-forget HTTPX poster for SourcePacket payloads.

Environment variables (via .env):
    ORCHESTRATOR_URL  — full URL of the ingest endpoint, e.g.
                        http://100.69.253.89:8000/ingest/visual
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()  # Reads ml_vision/.env (or any .env found up the directory tree)

logger = logging.getLogger("vision.client")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration — sourced exclusively from the environment
# ─────────────────────────────────────────────────────────────────────────────
_ORCHESTRATOR_URL: str = os.environ.get(
    "ORCHESTRATOR_URL", "http://localhost:8000/ingest/visual"
)

# Timeouts: connect=5 s, write=10 s, read=30 s (Orchestrator may be under load)
_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)

# Retry budget: 3 attempts with exponential back-off (0.5 s, 1 s, 2 s)
_MAX_RETRIES    = 3
_RETRY_BACKOFF  = [0.5, 1.0, 2.0]


# ─────────────────────────────────────────────────────────────────────────────
# Async send helper
# ─────────────────────────────────────────────────────────────────────────────

async def post_source_packet(payload: dict[str, Any]) -> None:
    """
    Asynchronously POST *payload* to the Master Orchestrator with retry logic.

    Designed to run as a FastAPI ``BackgroundTask`` — it MUST NOT raise.
    All errors are logged and swallowed so the main worker is never
    blocked or crashed by downstream failures.

    Retry policy
    ------------
    Up to ``_MAX_RETRIES`` attempts on transient network/5xx errors.
    4xx errors (caller faults) are NOT retried — they are logged and dropped.

    Parameters
    ----------
    payload : dict
        A fully-formed SourcePacket dict (see SourcePacket schema in main.py).
    """
    import asyncio

    packet_id: str = payload.get("packet_id", "<unknown>")

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await client.post(_ORCHESTRATOR_URL, json=payload)

                # 4xx → caller-side fault, do not retry
                if 400 <= response.status_code < 500:
                    logger.error(
                        "[%s] Orchestrator rejected packet (HTTP %d) — "
                        "not retrying: %s",
                        packet_id,
                        response.status_code,
                        response.text[:300],
                    )
                    return

                response.raise_for_status()  # raises on 5xx

                logger.info(
                    "[%s] SourcePacket delivered → %s  [HTTP %d]  attempt=%d",
                    packet_id,
                    _ORCHESTRATOR_URL,
                    response.status_code,
                    attempt,
                )
                return  # ← success, exit retry loop

            except httpx.TimeoutException:
                logger.warning(
                    "[%s] Orchestrator POST timed out (attempt %d/%d).",
                    packet_id, attempt, _MAX_RETRIES,
                )

            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "[%s] Orchestrator returned HTTP %d (attempt %d/%d): %s",
                    packet_id,
                    exc.response.status_code,
                    attempt,
                    _MAX_RETRIES,
                    exc.response.text[:300],
                )

            except httpx.RequestError as exc:
                logger.warning(
                    "[%s] Network error posting to Orchestrator (attempt %d/%d): %s",
                    packet_id, attempt, _MAX_RETRIES, exc,
                )

            except Exception:
                logger.exception(
                    "[%s] Unexpected error in post_source_packet (attempt %d/%d).",
                    packet_id, attempt, _MAX_RETRIES,
                )
                return  # Non-transient — abort immediately

            # Back-off before next attempt (skip sleep after last attempt)
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_BACKOFF[attempt - 1])

        logger.error(
            "[%s] All %d delivery attempts exhausted — packet dropped.",
            packet_id, _MAX_RETRIES,
        )