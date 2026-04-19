"""
Authentication and authorisation dependencies.

Security model:
  - PRODUCER / AUDITOR roles: enforced via X-User-Role header.
    In production, replace with JWT validation (e.g. python-jose).
  - Webhook endpoints: enforced via X-Webhook-Secret header
    (shared secret known only to the GPU nodes and the Orchestrator).
  - Trace IDs: generated per-request and injected into request.state.
    Every controller reads `request.state.trace_id` for structured logs.
"""

from __future__ import annotations

import uuid

from fastapi import Header, HTTPException, Request, status

from app.config import settings


# ── Role guards ─────────────────────────────────────────────────────────

def require_producer(
    x_user_role: str = Header(..., description="Must be 'PRODUCER'"),
) -> str:
    """Allow only PRODUCER role to mutate the Golden Library."""
    if x_user_role.strip().upper() != "PRODUCER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: PRODUCER role required for golden-source operations.",
        )
    return x_user_role.upper()


def require_auditor(
    x_user_role: str = Header(..., description="Must be 'AUDITOR'"),
) -> str:
    """Allow only AUDITOR role to submit suspect clips for inference."""
    if x_user_role.strip().upper() != "AUDITOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: AUDITOR role required for search/inference operations.",
        )
    return x_user_role.upper()


# ── Webhook guard ────────────────────────────────────────────────────────

def require_webhook_secret(
    x_webhook_secret: str = Header(..., description="Shared secret for GPU node callbacks"),
) -> str:
    """
    Validate that the calling GPU node knows the shared webhook secret.

    Uses a constant-time comparison to prevent timing attacks.
    In production, rotate this secret via your secrets manager.
    """
    import hmac

    if not hmac.compare_digest(x_webhook_secret, settings.webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret.",
        )
    return x_webhook_secret


# ── Trace ID ─────────────────────────────────────────────────────────────

def get_trace_id(request: Request) -> str:
    """
    Return the trace_id attached to this request by TraceIDMiddleware.

    Falls back to generating a new one so controllers always get a valid ID
    even if the middleware was bypassed in tests.
    """
    return getattr(request.state, "trace_id", str(uuid.uuid4()))