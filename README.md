# Overwatch — Distributed Forensic Media Intelligence Platform

<div align="center">

![Platform Status](https://img.shields.io/badge/status-production-brightgreen)
![Architecture](https://img.shields.io/badge/architecture-distributed%20microservices-blue)
![Cloud](https://img.shields.io/badge/cloud-HuggingFace%20%7C%20Render%20%7C%20Vercel-orange)
![Lead](https://img.shields.io/badge/lead%20architect-Tanmay%20Kumar-blueviolet)

**A cloud-native, multi-agent forensic media analysis platform built for pre-publication piracy detection, visual similarity scoring, and auditable incident production.**

*Architected, engineered, and deployed by **Tanmay Kumar***

</div>

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Services](#services)
- [End-to-End Pipeline](#end-to-end-pipeline)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Team](#team)

---

## Overview

**Overwatch** (internally referred to as the *M4 Orchestrator Asset Intelligence Network*) is a production-grade distributed platform that inspects media assets before publication, syndication, or archival. It combines visual embeddings, OCR, semantic context extraction, audio transcription, vector similarity search, and incident scoring into a single deterministic forensic workflow.

The platform was conceived, designed, and built end-to-end by **Tanmay Kumar** as Principal Architect and Lead Cloud Engineer. Every component — from the distributed orchestration layer and ML inference nodes to the cloud deployment pipelines and the React command center — was engineered under Tanmay Kumar's sole technical direction.

### What it does

- Detects **piracy, stolen broadcasts, deepfakes, and cross-source content contamination** before publication
- Produces **auditable forensic evidence** — vectors, OCR text, object detections, timestamps, and trace IDs — for every analyzed asset
- Runs across **modest GPU hardware** (RTX 3050 / RTX 2050 profiles) without requiring oversized cloud GPU infrastructure
- Delivers **operator-facing verdicts** through a React command center with full pipeline transparency

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      OVERWATCH PLATFORM                             │
│               Lead Architect: Tanmay Kumar                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │       M4 Orchestrator          │
              │   FastAPI · PostgreSQL         │
              │   pgvector · PgBouncer         │
              │   (Render — auto deploy)       │
              └───────┬────────────────────────┘
                      │
          ┌───────────┼────────────────┐
          │           │                │
          ▼           ▼                ▼
   ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
   │  M2         │ │  ARGUS      │ │  HERMES      │
   │  Extractor  │ │  Vision     │ │  Context     │
   │  FFmpeg     │ │  CLIP+YOLO  │ │  OCR+MiniLM  │
   │  HF Spaces  │ │  HF Spaces  │ │  HF Spaces   │
   └─────────────┘ └──────┬──────┘ └──────────────┘
                          │
                   ┌──────▼──────┐
                   │ Ghost Audio │
                   │  Whisper    │
                   │ (on-demand) │
                   └─────────────┘

              ┌──────────────────────────┐
              │      Overwatch UI        │
              │  React · Command Center  │
              │  (Vercel / Render)       │
              └──────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestrator backend | FastAPI, PostgreSQL, pgvector, asyncpg, SQLAlchemy |
| Connection pooling | PgBouncer (transaction mode) |
| ML inference | CLIP ViT-B/32, YOLOv8n, EasyOCR, MiniLM-L6-v2, Whisper |
| Media processing | FFmpeg, OpenCV |
| HTTP transport | httpx (async) |
| Authentication | JWT, OTP, Google OAuth |
| Frontend | React, TypeScript, Tailwind CSS, Framer Motion |
| Containerization | Docker (HuggingFace Spaces SDK, port 7860, UID 1000 sandbox) |
| Cloud — ML workers | Hugging Face Spaces (CPU Basic tier) |
| Cloud — backend | Render (Web Service, auto-deploy) |
| Cloud — frontend | Vercel / Render (auto-deploy) |
| Vector storage | PostgreSQL + pgvector extension |

---

## Services

### M4 Orchestrator — *Control Plane*
The central nervous system of the platform. Manages the full asset lifecycle, coordinates jobs between ML workers, persists vectors and evidence, and delivers operator-facing APIs. Includes a webhook buffer service for asynchronous modality reconciliation and an active health probe loop against all GPU worker endpoints.

> **Notable engineering:** Tanmay Kumar resolved a production `InvalidSQLStatementNameError` crash caused by `asyncpg` prepared statement caching conflicting with PgBouncer transaction-mode pooling — fixed by injecting `statement_cache_size: 0` and `prepared_statement_cache_size: 0` into SQLAlchemy `connect_args`.

### M2 Extractor — *Media Intake*
The ingress node. Downloads source assets, runs FFmpeg normalization (`1 FPS`, `224×224`, `16 kHz` WAV audio), and fan-outs frames concurrently to the Vision and Context nodes. Coordinates the post-visual audio sequencing phase to prevent VRAM contention.

### ARGUS Vision Node — *Visual Inference*
Generates `512-D` CLIP embeddings and YOLOv8n object detections per frame. Hosts the ephemeral Ghost Audio path (Whisper, loaded and unloaded on demand). Implements a zero-vector guard to prevent corrupt embeddings from entering the similarity store.

### HERMES Context Node — *OCR + Semantics*
Runs EasyOCR on every frame to extract broadcast watermarks, subtitles, and ownership identifiers. Encodes results into `384-D` MiniLM semantic vectors. Runs a batch-level `ConflictDetector` to catch logically impossible watermark combinations — e.g., two competing broadcaster identities in the same content stream.

### Overwatch UI — *Command Center*
React-based operator portal for asset ingestion, real-time pipeline status, and forensic verdict review. Includes an in-platform documentation system with per-doc metadata, table-of-contents generation, word count, and read-time estimation.

---

## End-to-End Pipeline

```
Asset submitted
      │
      ▼
[1] Asset Registration        Orchestrator assigns trace_id, starts lifecycle record
      │
      ▼
[2] Frame & Audio Extraction  FFmpeg → 1 FPS @ 224×224 JPEG + 16 kHz WAV
      │
      ▼
[3] Parallel Inference        Each frame → Vision (CLIP+YOLO) + Context (OCR+MiniLM)
      │                       concurrently, independently
      ▼
[4] Async Reconciliation      Orchestrator buffers and joins visual + text events
      │                       via packet_id, timestamp, and temporal slop rules
      ▼
[5] Audio Sequencing          Whisper runs after visual workers report idle
      │                       (VRAM collision avoidance)
      ▼
[6] Conflict Detection        ConflictDetector scans accumulated OCR for
      │                       logically incompatible broadcaster evidence
      ▼
[7] Fusion & Verdict          Fused score (visual 0.65 + text 0.35) vs thresholds
      │                       piracy: 0.85 · suspicious: 0.60
      ▼
[8] Incident Delivery         Verdict + full evidence record surfaced in UI
```

---

## Deployment

All cloud infrastructure was provisioned and configured by **Tanmay Kumar**.

| Service | Platform | Namespace | Trigger |
|---|---|---|---|
| Context Worker | HuggingFace Spaces | `tanmayml01/overwatch-context-worker` | Push to `main` |
| Media Processor | HuggingFace Spaces | `tanmayml01/overwatch-media-processor` | Push to `main` |
| Vision Service | HuggingFace Spaces | `tanmayml01/overwatch-vision-service` | Push to `main` |
| Auditor | HuggingFace Spaces | `tanmayml01/overwatch-auditor` | Push to `main` |
| Orchestrator | Render | Web Service | Push to `main` |
| Overwatch UI | Vercel / Render | Web App | Push to `main` |

All HF Spaces are containerized with Docker, bound to port `7860`, and run on CPU Basic tiers with model caches routed to `/tmp/cache` to comply with UID 1000 sandbox restrictions.

---

## Configuration

### Hugging Face Space Variables

Configure under **Settings → Variables and Secrets** for each Space:

| Variable | Type | Description |
|---|---|---|
| `TANMAY_URL` | Variable | Render Orchestrator webhook URL (Context Worker) |
| `ORCHESTRATOR_URL` | Variable | Render Orchestrator webhook URL (all other nodes) |
| `WEBHOOK_SECRET` | **Secret** | Shared HMAC secret for inter-service authentication |

> `WEBHOOK_SECRET` must always be stored as an encrypted Secret — never as a public Variable.

### Fusion Policy (Orchestrator)

| Parameter | Value |
|---|---|
| `fusion_weight_visual` | `0.65` |
| `fusion_weight_text` | `0.35` |
| `piracy_threshold` | `0.85` |
| `suspicious_threshold` | `0.60` |

---

## Team

| Name | Role |
|---|---|
| **Tanmay Kumar** | **Principal Architect & Lead Engineer** — system design, orchestration layer, all cloud deployments, backend engineering, frontend integration, ML pipeline architecture, and end-to-end product delivery |
| Yogesh Sharma | Contributor — Media Processor staging |
| Rohit Kumar | Contributor — lVision Node staging |
| Yug | Contributor —  Context Node staging |

---

<div align="center">

Built by **Tanmay Kumar**

</div>
