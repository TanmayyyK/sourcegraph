# syntax=docker/dockerfile:1

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
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && python -m pip install -r requirements.txt


FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PORT=7860 \
    VISION_HOST=0.0.0.0 \
    VISION_PORT=7860 \
    ML_VISION_CACHE_DIR=/tmp/cache \
    HF_HOME=/tmp/cache/huggingface \
    HF_HUB_CACHE=/tmp/cache/huggingface/hub \
    TRANSFORMERS_CACHE=/tmp/cache/huggingface/transformers \
    TORCH_HOME=/tmp/cache/torch \
    XDG_CACHE_HOME=/tmp/cache/xdg \
    YOLO_CONFIG_DIR=/tmp/cache/ultralytics \
    MPLCONFIGDIR=/tmp/cache/matplotlib \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    CUDA_VISIBLE_DEVICES="" \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    NUMEXPR_NUM_THREADS=2 \
    VISION_TORCH_THREADS=2 \
    VISION_TORCH_INTEROP_THREADS=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 1000 --create-home --shell /bin/bash appuser \
    && mkdir -p /app /tmp/cache \
    && chown -R 1000:1000 /app /tmp/cache /home/appuser

COPY --from=builder --chown=1000:1000 /opt/venv /opt/venv

WORKDIR /app
COPY --chown=1000:1000 . .

USER 1000

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
