# syntax=docker/dockerfile:1

# ══════════════════════════════════════════════════════════════════════════════
#  ml_context — Overwatch Context Worker  (HF Spaces · CPU Basic · 512 MB RAM)
#
#  Multi-stage build:
#    builder  → installs CPU-only PyTorch + all pip deps into a venv
#    runtime  → slim image with only the venv + app code
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

# Install CPU-only PyTorch FIRST (from dedicated index), then the rest
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && python -m pip install -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    # ── HF Spaces strict port ──
    PORT=7860 \
    HOST=0.0.0.0 \
    # ── Force CPU-only (no CUDA lookup on CPU Basic tier) ──
    CUDA_VISIBLE_DEVICES="" \
    # ── Route ALL model caches to writeable /tmp/cache ──
    HF_HOME=/tmp/cache/huggingface \
    HF_HUB_CACHE=/tmp/cache/huggingface/hub \
    TRANSFORMERS_CACHE=/tmp/cache/huggingface/transformers \
    TORCH_HOME=/tmp/cache/torch \
    EASYOCR_MODULE_PATH=/tmp/cache/easyocr \
    XDG_CACHE_HOME=/tmp/cache/xdg \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    # ── Thread-limiting for 512 MB RAM constraint ──
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    NUMEXPR_NUM_THREADS=2 \
    KMP_DUPLICATE_LIB_OK=TRUE

# System libraries required by OpenCV (EasyOCR dependency)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# UID 1000 non-root user (HF Spaces sandbox requirement)
RUN useradd --uid 1000 --create-home --shell /bin/bash appuser \
    && mkdir -p /app /tmp/cache \
    && chown -R 1000:1000 /app /tmp/cache /home/appuser

COPY --from=builder --chown=1000:1000 /opt/venv /opt/venv

WORKDIR /app
COPY --chown=1000:1000 . .

USER 1000

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
