# syntax=docker/dockerfile:1

# ══════════════════════════════════════════════════════════════════════════════
#  extractor — Overwatch Media Processor  (HF Spaces · CPU Basic)
#
#  Multi-stage build:
#    builder  → installs all pip deps into a venv
#    runtime  → slim image with ffmpeg + system libs + venv + app code
# ══════════════════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    # ── HF Spaces strict port ──
    PORT=7860 \
    # ── Temporary storage for video/frame processing ──
    TMPDIR=/tmp \
    XDG_CACHE_HOME=/tmp/cache

# System libraries for media processing on headless Linux:
#   ffmpeg        → video frame extraction + audio extraction
#   libgl1-mesa-glx → OpenGL (required by opencv-python-headless)
#   libglib2.0-0  → GLib (required by opencv internals)
# Cache cleaned in same layer to minimize image size.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1-mesa-glx \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# UID 1000 non-root user (HF Spaces sandbox requirement)
RUN useradd --uid 1000 --create-home --shell /bin/bash appuser \
    && mkdir -p /app /tmp/cache /tmp/sg_extractor \
    && chown -R 1000:1000 /app /tmp/cache /tmp/sg_extractor /home/appuser

COPY --from=builder --chown=1000:1000 /opt/venv /opt/venv

WORKDIR /app
COPY --chown=1000:1000 . .

USER 1000

EXPOSE 7860

CMD ["uvicorn", "worker:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
