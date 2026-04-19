"""
Application configuration via environment variables.

All settings are configurable via .env file or docker-compose environment block.
Pydantic Settings provides validation + type coercion automatically.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global orchestrator configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://sourcegraph:sg_vector_2024@localhost:5432/sourcegraph_vectors"

    # ── Vector Dimensions (strict) ──────────────────────────────
    visual_dim: int = 512
    text_dim: int = 384

    # ── Fusion Weights (must sum to 1.0) ────────────────────────
    fusion_weight_visual: float = 0.60
    fusion_weight_text: float = 0.30
    fusion_weight_temporal: float = 0.10

    # ── Matching Thresholds ─────────────────────────────────────
    confidence_threshold: float = 0.85
    pirate_threshold: float = 0.80
    suspicious_threshold: float = 0.60

    # ── Temporal Slop ───────────────────────────────────────────
    temporal_slop_seconds: float = 1.0

    # ── Buffer TTL (eviction after N seconds) ───────────────────
    buffer_ttl_seconds: float = 60.0
    buffer_cleanup_interval: float = 10.0

    # ── Network / Tailscale ─────────────────────────────────────
    tailscale_ip: str = "100.69.253.89"
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Logging ─────────────────────────────────────────────────
    log_level: str = "DEBUG"

    # ── Similarity Engine ───────────────────────────────────────
    cosine_epsilon: float = 1e-8


# Singleton — import this everywhere
settings = Settings()
