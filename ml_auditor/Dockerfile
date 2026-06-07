# syntax=docker/dockerfile:1

# ══════════════════════════════════════════════════════════════════════════════
#  ml_auditor — Overwatch Auditor  (HF Spaces · CPU Basic)
#
#  Lightweight FAISS + DTW similarity/piracy engine.
#  No GPU needed — faiss-cpu only.
# ══════════════════════════════════════════════════════════════════════════════

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install \
        faiss-cpu \
        fastdtw \
        scipy \
        numpy \
        "fastapi>=0.115.0" \
        pydantic \
        uvicorn


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PORT=7860

# UID 1000 non-root user (HF Spaces sandbox requirement)
RUN useradd --uid 1000 --create-home --shell /bin/bash appuser \
    && mkdir -p /app /app/data \
    && chown -R 1000:1000 /app

COPY --from=builder --chown=1000:1000 /opt/venv /opt/venv

WORKDIR /app
COPY --chown=1000:1000 . .

USER 1000

EXPOSE 7860

CMD ["python", "main.py"]
