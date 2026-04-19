"""
SourceGraph Orchestrator — Central Intelligence Backend.

App factory with async lifespan management incorporating PostgreSQL, SQLAlchemy Async,
and strict RBAC authentication matrices.

    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logger import get_logger, log_handshake
from app.core.database import engine, Base

# Route registrations
from app.controllers import (
    feed_controller,
    ingest_controller,
    search_controller
)
from app.services.buffer_service import SyncBuffer

logger = get_logger("sourcegraph.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Async lifespan:
    1. Initialize the PostgreSQL schema via async SQLAlchemy engine.
    2. Start processing buffer flows safely.
    """
    logger.info("[STARTUP] 🚀 SourceGraph Orchestrator v2.0.0 initializing...")

    # Boot PostgreSQL Database
    try:
        async with engine.begin() as conn:
            # Note: For production architectures, integrate alembic here.
            # create_all builds `assets` and `frame_vectors` if they do not exist.
            await conn.run_sync(Base.metadata.create_all)
        logger.info("[STARTUP] 🗄️ PostgreSQL connection & schema bindings finalized.")
    except Exception as e:
        logger.error(f"[STARTUP EXCEPTION] Failed to connect to Database: {e}")

    app.state.settings = settings

    # Sync buffer
    app.state.sync_buffer = SyncBuffer()
    app.state.sync_buffer.start()
    logger.info(
        f"[STARTUP] ⚡ Sync buffer online "
        f"(TTL={settings.buffer_ttl_seconds}s, "
        f"slop=±{settings.temporal_slop_seconds}s)"
    )

    # In-memory feed (for /feed endpoint mock compatibility during P2)
    app.state.feed: list[dict] = []

    log_handshake(
        logger,
        source_node="M4-Orchestrator",
        source_ip=settings.tailscale_ip,
        target_node="Tailscale Mesh",
        target_ip="100.x.x.x",
    )

    logger.info("[STARTUP] ✅ Pipeline open. Awaiting target PRODUCER vectors.")
    yield

    logger.info("[SHUTDOWN] 🔻 Terminating DB connections & sync buffers...")
    app.state.sync_buffer.stop()
    await engine.dispose()
    logger.info("[SHUTDOWN] ✅ Graceful shutdown complete.")


def create_app() -> FastAPI:
    """Application factory for Phase 2 Production Workflow."""
    app = FastAPI(
        title="SourceGraph Orchestrator",
        description="Dual-Workflow Matrix: PRODUCER (Ingest Golden Source) & AUDITOR (Infer Suspicious Vectors). Backed by PostgreSQL.",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(feed_controller.router)
    app.include_router(ingest_controller.router)
    app.include_router(search_controller.router)

    return app

app = create_app()
