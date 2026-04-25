"""
Application configuration via environment variables.

All settings are populated from .env or the process environment.
Pydantic-Settings performs validation and type coercion automatically.
Import the singleton `settings` everywhere — never re-instantiate.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global orchestrator configuration — single source of truth."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://sourcegraph:sg_vector_2024"
        "@localhost:5432/sourcegraph_vectors"
    )

    # ── Node Topology ───────────────────────────────────────────
    tailscale_ip: str = "100.69.253.89"
    # Full URL of the M2 FFmpeg Extractor (env: EXTRACTOR_URL)
    extractor_url: str = "http://100.103.180.14:8003"
    extractor_timeout_seconds: float = 300.0
    extractor_max_retries: int = 3

    # GPU node health endpoints (used by active health probe)
    vision_node_url: str = "http://100.119.250.125:8080"   # Rohit / RTX 3050
    context_node_url: str = "http://100.115.89.72:8002"    # Yug / RTX 2050
    health_probe_interval: float = 10.0                    # seconds between probes

    # ── Security ────────────────────────────────────────────────
    # GPU nodes must include this in X-Webhook-Secret header
    webhook_secret: str = "change-me-in-production"
    
    # ── Authentication ──────────────────────────────────────────
    jwt_secret_key: str = "super-secret-overwatch-key-change-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 10080  # 60 * 24 * 7 (1 week session)
    otp_expire_minutes: int = 15  # How long the 6-digit code is valid
    otp_request_cooldown_seconds: int = 30
    otp_max_verify_attempts: int = 5
    google_oauth_client_id: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "no-reply@overwatch.local"

    # ── Vector Dimensions (strict) ──────────────────────────────
    visual_dim: int = 512
    text_dim: int = 384

    # ── Fusion Weights ──────────────────────────────────────────
    fusion_weight_visual: float = 0.65
    fusion_weight_text: float = 0.35

    # ── Matching Thresholds ─────────────────────────────────────
    piracy_threshold: float = 0.85
    suspicious_threshold: float = 0.60

    # ── Buffer ──────────────────────────────────────────────────
    buffer_ttl_seconds: float = 300.0
    buffer_cleanup_interval: float = 10.0
    max_buffer_size: int = 10_000
    temporal_slop_seconds: float = 1.0

    # ── KNN ─────────────────────────────────────────────────────
    knn_top_k: int = 10

    # ── App ─────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"


# Singleton — import this everywhere
settings = Settings()