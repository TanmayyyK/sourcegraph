"""
SourceGraph Orchestrator — Central Intelligence Backend v3.0.0

PATCH: Updated CORSMiddleware to accept requests from both
  - http://localhost:3000  (legacy / production build)
  - http://localhost:5173  (Vite dev server ← React Command Center)

All other logic is untouched.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.core.database import engine, Base
from app.core.logger import get_logger, log_handshake
from sqlalchemy import text

# Controllers
from app.controllers import (
    feed_controller,
    golden_controller,
    search_controller,
    webhook_controller,
    auth_controller,
)
from app.services.buffer_service import BufferService
from app.services.email_service import missing_smtp_fields
from app.controllers.feed_controller import NODE_LAST_SEEN
import httpx
import time

logger = get_logger("sourcegraph.main")


# ── Trace ID middleware ───────────────────────────────────────────────────

class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    Inject a unique trace_id on every request.

    - Reads X-Trace-ID from the incoming request if present (allows
      clients to propagate their own correlation IDs end-to-end).
    - Falls back to generating a new UUID4.
    - Stores it on request.state.trace_id for all downstream handlers.
    - Echoes it back in the X-Trace-ID response header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        request.state.trace_id = trace_id

        response: Response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response


# ── Lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("[STARTUP] 🚀 SourceGraph Orchestrator v3.0.0 initializing...")
    logger.info(f"[STARTUP] Pool: size={20} overflow={10} recycle=3600s")

    try:
        async with engine.begin() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
            )
            logger.info("[STARTUP] ✅ pgvector extension ready")
    except Exception as exc:
        logger.error(f"[STARTUP] ⚠ pgvector extension check failed: {exc}")
        logger.error("[STARTUP] Ensure pgvector is installed: apt install postgresql-pgvector")

    # ── Lightweight schema patching (no Alembic in this repo) ─────────────
    # Base.metadata.create_all only creates missing tables; it does NOT add
    # new columns to existing tables. We apply a safe, idempotent ALTER here
    # so the feeder can persist OCR text without a manual migration step.
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    ALTER TABLE IF EXISTS frame_vision_metadata
                    ADD COLUMN IF NOT EXISTS ocr_text TEXT NOT NULL DEFAULT '';
                    """
                )
            )
        logger.info("[STARTUP] ✅ Schema patch applied (frame_vision_metadata.ocr_text)")
    except Exception as exc:
        logger.error(f"[STARTUP] ❌ Schema patch failed (ocr_text): {exc}")

    # Allow asynchronous dual-vector upserts into frame_vectors where
    # ml_vision and ml_context may arrive in any order.
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    ALTER TABLE IF EXISTS frame_vectors
                    ALTER COLUMN visual_vector DROP NOT NULL;
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    ALTER TABLE IF EXISTS frame_vectors
                    ALTER COLUMN text_vector DROP NOT NULL;
                    """
                )
            )
        logger.info("[STARTUP] ✅ Schema patch applied (frame_vectors nullable vectors)")
    except Exception as exc:
        logger.error(f"[STARTUP] ❌ Schema patch failed (frame_vectors): {exc}")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("[STARTUP] 🗄️  Schema bindings finalised (assets, frame_vectors, similarity_results)")
    except Exception as exc:
        logger.error(f"[STARTUP] ❌ Schema initialisation failed: {exc}")

    buffer = BufferService()
    buffer.start()
    app.state.buffer = buffer
    logger.info(
        f"[STARTUP] ⚡ Webhook buffer online "
        f"(ttl={settings.buffer_ttl_seconds}s "
        f"slop=±{settings.temporal_slop_seconds}s "
        f"max={settings.max_buffer_size})"
    )

    app.state.settings = settings
    log_handshake(
        logger,
        source_node="M4-Orchestrator",
        source_ip=settings.tailscale_ip,
        target_node="M2-Extractor",
        target_ip=settings.extractor_url,
    )
    logger.info(
        f"[STARTUP] 🔑 Fusion weights: "
        f"visual={settings.fusion_weight_visual} "
        f"text={settings.fusion_weight_text}"
    )
    logger.info(
        f"[STARTUP] 🎯 Thresholds: "
        f"piracy≥{settings.piracy_threshold} "
        f"suspicious≥{settings.suspicious_threshold}"
    )
    missing = missing_smtp_fields()
    if missing:
        logger.warning(
            "[STARTUP] ⚠ OTP email delivery disabled until SMTP is configured. Missing: %s",
            ", ".join(missing),
        )
    else:
        logger.info("[STARTUP] 📧 OTP email delivery configured")
    if not settings.google_oauth_client_id:
        logger.warning("[STARTUP] ⚠ Google OAuth disabled (GOOGLE_OAUTH_CLIENT_ID missing)")
    else:
        logger.info("[STARTUP] 🟢 Google OAuth configured")
    logger.info("[STARTUP] ✅ Pipeline open. Awaiting PRODUCER / AUDITOR requests.")

    # ── Active Health Probe (CONTRACT: pull-based node liveness) ──────────
    _probe_cancel = asyncio.Event()

    async def _health_probe_loop():
        """
        Periodically ping each GPU node's health endpoint.
        If reachable, update NODE_LAST_SEEN so the Command Centre
        shows the node as ONLINE even when no video is being processed.
        """
        targets = [
            ("vision_engine",  settings.vision_node_url),
            ("text_processor", settings.context_node_url),
        ]
        while not _probe_cancel.is_set():
            for key, base_url in targets:
                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        resp = await client.get(f"{base_url}/")
                        if resp.status_code < 500:
                            NODE_LAST_SEEN[key] = time.time()
                except Exception:
                    pass  # node unreachable — leave last_seen stale → ERR
            try:
                await asyncio.wait_for(_probe_cancel.wait(), timeout=settings.health_probe_interval)
                break  # event was set → shutting down
            except asyncio.TimeoutError:
                pass  # normal — loop again

    probe_task = asyncio.create_task(_health_probe_loop(), name="health_probe")
    logger.info(
        f"[STARTUP] 🩺 Active health probe started "
        f"(interval={settings.health_probe_interval}s)"
    )

    yield

    logger.info("[SHUTDOWN] 🔻 Stopping health probe, buffer, and DB pool...")
    _probe_cancel.set()
    probe_task.cancel()
    try:
        await probe_task
    except asyncio.CancelledError:
        pass
    buffer.stop()
    await engine.dispose()
    logger.info("[SHUTDOWN] ✅ Graceful shutdown complete.")


# ── Application factory ───────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="SourceGraph Anti-Piracy Orchestrator",
        description=(
            "Multi-modal Anti-Piracy Intelligence Engine.\n\n"
            "**Workflow A (PRODUCER):** `POST /api/v1/golden/upload`\n\n"
            "**Workflow B (AUDITOR):** `POST /api/v1/search/upload`\n\n"
            "**GPU Sink:** `POST /api/v1/webhooks/vector` + `/complete`\n\n"
            "All requests carry `X-Trace-ID` for end-to-end tracing."
        ),
        version="3.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Trace ID (first — wraps everything) ───────────────────────────────
    app.add_middleware(TraceIDMiddleware)

    # ── CORS ──────────────────────────────────────────────────────────────
    # PATCH: Added http://localhost:5173 (Vite dev server) alongside the
    # original http://localhost:3000 (legacy / production React build).
    # For a production deployment, restrict this to your actual domain.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",   # legacy / production build
            "http://localhost:5173",   # Vite dev server ← ADDED
            "http://localhost:5174",   # alt Vite port
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-ID"],
    )

    # ── Routes ────────────────────────────────────────────────────────────
    app.include_router(feed_controller.router)          # GET /  /buffer/status  /api/v1/assets/*
    app.include_router(golden_controller.router)        # POST /api/v1/golden/upload
    app.include_router(search_controller.router)        # POST /api/v1/search/upload
    app.include_router(webhook_controller.router)       # POST /api/v1/webhooks/*
    app.include_router(auth_controller.router)          # POST /api/v1/auth/* <-- ADD THIS
    return app


app = create_app()