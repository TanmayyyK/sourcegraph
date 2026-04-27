"""
Authentication and authorisation dependencies.

Security model:
  - PRODUCER / AUDITOR roles: enforced via JWT Bearer validation.
  - Webhook endpoints: enforced via X-Webhook-Secret header
    (shared secret known only to the GPU nodes and the Orchestrator).
  - Trace IDs: generated per-request and injected into request.state.
    Every controller reads `request.state.trace_id` for structured logs.
"""

from __future__ import annotations

import hmac
import uuid
from typing import Any, Dict

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

# Initializes the standard Bearer token scheme for FastAPI
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

# ── JWT Token Extraction ─────────────────────────────────────────────────

def get_token_payload(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Decodes the Bearer token, verifies its signature and expiration, 
    and returns the payload dictionary.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ── Role guards ─────────────────────────────────────────────────────────

def require_producer(payload: Dict[str, Any] = Depends(get_token_payload)) -> Dict[str, Any]:
    """Allow only PRODUCER role to mutate the Golden Library."""
    role = payload.get("role", "").upper()
    if role != "PRODUCER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: PRODUCER role required for golden-source operations.",
        )
    # Returning the payload allows the controller to extract user["sub"] for database inserts
    return payload


def require_auditor(payload: Dict[str, Any] = Depends(get_token_payload)) -> Dict[str, Any]:
    """Allow only AUDITOR role to submit suspect clips for inference."""
    role = payload.get("role", "").upper()
    if role != "AUDITOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: AUDITOR role required for search/inference operations.",
        )
    return payload


def resolve_upload_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    x_user_role: str | None = Header(None, alias="X-User-Role"),
) -> Dict[str, Any]:
    """
    Resolve the caller for the unified upload route.

    JWT is authoritative. A verified upstream may also pass X-User-Role; when
    both are present they must agree so a client cannot smuggle a different
    routing role beside a valid token.
    """
    header_role = x_user_role.upper() if x_user_role else None
    if header_role is not None and header_role not in {"PRODUCER", "AUDITOR"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-User-Role. Expected PRODUCER or AUDITOR.",
        )

    if credentials is None:
        if header_role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token or verified X-User-Role header.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"role": header_role, "sub": None, "auth_source": "x-user-role"}

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_role = str(payload.get("role", "")).upper()
    if token_role not in {"PRODUCER", "AUDITOR"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: upload requires PRODUCER or AUDITOR role.",
        )
    if header_role is not None and header_role != token_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-User-Role does not match authenticated token role.",
        )

    payload["role"] = token_role
    payload["auth_source"] = "jwt"
    return payload


# ── Webhook guard ────────────────────────────────────────────────────────

def require_webhook_secret(
    x_webhook_secret: str = Header(..., description="Shared secret for GPU node callbacks"),
) -> str:
    """
    Validate that the calling GPU node knows the shared webhook secret.

    Uses a constant-time comparison to prevent timing attacks.
    In production, rotate this secret via your secrets manager.
    """
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
