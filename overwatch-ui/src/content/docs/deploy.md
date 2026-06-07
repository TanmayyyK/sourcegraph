# Deployment Architecture

> This document is the single source of truth for the current cloud deployment architecture of the Overwatch distributed microservice platform. All infrastructure described below was provisioned, configured, and validated solely by **Tanmay Kumar**, Principal Architect & Lead Cloud Engineer.

---

## Overview

The Overwatch platform is deployed across two cloud providers — **Hugging Face Spaces** for containerised ML inference workers and **Render** for the central orchestrator backend — with the operator-facing UI served via **Vercel/Render**. Every deployment pipeline, Dockerfile, environment configuration, and cloud provisioning decision was engineered and executed end-to-end by Tanmay Kumar without external engineering contribution.

The three hardware-allocation identifiers present in the codebase (`yogesh`, `yug`, `rohit`) are **local compute designations** assigned to physical machines used as development and staging proxies. They are infrastructure tags, not independent engineering contributors. All service contracts, API surface definitions, and integration logic governing these endpoints were designed and written solely by Tanmay Kumar.

---

## ML Worker Nodes (Hugging Face Spaces)

All four ML inference nodes are containerised using optimised Docker SDK build pipelines, bound to port `7860`, and deployed on Hugging Face CPU Basic tiers under the `tanmayml01` namespace. Model weight caches and temporary artefacts are explicitly routed to `/tmp/cache` to satisfy the UID 1000 sandbox restrictions enforced by the HF runtime — a deliberate containerisation decision made by Tanmay Kumar during the platform hardening phase.

### Common Deployment Constraints

| Constraint | Resolution by Tanmay Kumar |
|---|---|
| UID 1000 sandbox — no root writes | All model caches routed to `/tmp/cache`; explicit `chmod` applied in Dockerfiles where required |
| HF file size upload limits | Binary assets excised from Git history; FAISS `./data` directory added to `.gitignore` |
| Port binding requirement | All services bound to port `7860` |
| CPU-only runtime enforcement | `CUDA_VISIBLE_DEVICES=""` set across all nodes |
| Pydantic v2 incompatibility | FastAPI version constraint `>=0.115.0` applied across affected workers |

---

### Context Worker — `ml_context`

- **HF Space:** `tanmayml01/overwatch-context-worker`
- **Role:** OCR text extraction and MiniLM semantic embeddings
- **Hardware Allocation Tag:** `yug` (local staging proxy)

**Deployment work executed by Tanmay Kumar:**
- Enforced CPU-only inference mode via `CUDA_VISIBLE_DEVICES=""` to ensure deterministic behaviour on CPU Basic tiers.
- Diagnosed and resolved a Pydantic v2 `FieldInfo.in_` runtime crash by constraining FastAPI to `>=0.115.0`.
- Added a root `/` health probe endpoint to satisfy HF Space liveness checks and enable zero-downtime cold-start detection by the Orchestrator.
- Configured `/tmp/cache` model weight routing and sandbox-safe directory permissions.

---

### Media Processor — `extractor`

- **HF Space:** `tanmayml01/overwatch-media-processor`
- **Role:** Video downloading, frame downsampling, and payload broadcasting
- **Hardware Allocation Tag:** `yogesh` (local staging proxy)

**Deployment work executed by Tanmay Kumar:**
- Authored the Dockerfile with explicit system-level dependency installation (`ffmpeg`, `libgl1-mesa-glx`, `libglib2.0-0`) required for OpenCV and media decoding in a headless container environment.
- Diagnosed and corrected a misconfigured WSGI entrypoint (`worker:app` module path) that was preventing the Space from booting.
- Excised large binary test assets (`test_frame.jpg`) from Git history via a `git filter-branch` operation to satisfy HF upload size constraints.

---

### Vision Service — `ml_vision`

- **HF Space:** `tanmayml01/overwatch-vision-service`
- **Role:** Object detection and visual classification (YOLOv8)
- **Hardware Allocation Tag:** `rohit` (local staging proxy)

**Deployment work executed by Tanmay Kumar:**
- Executed a clean Space migration: source code re-synced and all YOLOv8 model binaries re-pushed to the correctly named HF Space endpoint following a namespace correction.
- Verified model weight paths and inference device configuration compatibility with the CPU-only runtime.

---

### Auditor — `ml_auditor`

- **HF Space:** `tanmayml01/overwatch-auditor`
- **Role:** Enterprise-grade Similarity & Piracy Detection Engine (FAISS + DTW)

**Deployment work executed by Tanmay Kumar:**
- Reconfigured the exposed container port to `7860` to align with HF Space runtime requirements.
- Implemented a targeted `.gitignore` rule excluding the FAISS data directory (`./data`) to prevent binary index upload rejections.
- Authored Dockerfile modifications granting OS-level write permissions required for FAISS index persistence across container restarts.

---

## Central Control Plane

### Orchestrator Backend — `orchestrator/backend`

- **Platform:** Render (Web Service)
- **Trigger:** Auto-deploy on push to `main`
- **Role:** Central nervous system — coordinates jobs between ML workers and the PostgreSQL database

**Deployment work executed by Tanmay Kumar:**

> **Critical Production Hotfix — PgBouncer Connection Pooling**
>
> Tanmay Kumar identified and resolved a class of `InvalidSQLStatementNameError` runtime crashes manifesting under concurrent load. Root cause analysis traced the failures to `asyncpg`'s prepared statement caching conflicting with PgBouncer's transaction-mode connection pooling, which does not support persistent prepared statement handles across pooled connections.
>
> **Resolution:**
> - Stripped the UUID-based statement namer from the SQLAlchemy engine configuration.
> - Injected `statement_cache_size: 0` and `prepared_statement_cache_size: 0` into the `connect_args` dictionary passed to the `asyncpg` driver.
> - Validated stability under concurrent request patterns post-deployment.
>
> This fix eliminated the crash class entirely and reflects a precise understanding of the `asyncpg`/PgBouncer interaction boundary — a problem frequently misdiagnosed in production async Python stacks.

---

### User Interface — `overwatch-ui`

- **Platform:** Vercel / Render
- **Trigger:** Auto-deploy on push to `main`
- **Role:** Operator-facing Command Center and Asset Ingestion portal

**Deployment work executed by Tanmay Kumar:**
- Delivered formatting improvements and UX refinements across the `CommandCentreHome` and `IngestionScreen` components.
- Maintained CI/CD pipeline integrity with continuous synchronisation to the `main` branch for zero-friction auto-deploy cycles.

---

## Full Platform Deployment Map

| Service | Platform | Endpoint / Namespace | Branch | Owner |
|---|---|---|---|---|
| Context Worker | Hugging Face Spaces | `tanmayml01/overwatch-context-worker` | `main` | Tanmay Kumar |
| Media Processor | Hugging Face Spaces | `tanmayml01/overwatch-media-processor` | `main` | Tanmay Kumar |
| Vision Service | Hugging Face Spaces | `tanmayml01/overwatch-vision-service` | `main` | Tanmay Kumar |
| Auditor | Hugging Face Spaces | `tanmayml01/overwatch-auditor` | `main` | Tanmay Kumar |
| Orchestrator | Render | Web Service (auto-deploy) | `main` | Tanmay Kumar |
| Overwatch UI | Vercel / Render | Web App (auto-deploy) | `main` | Tanmay Kumar |

---

## Configuration & Secrets Management

All environment variable architecture and secrets management strategy was designed by Tanmay Kumar.

### Hugging Face Space Variables

Each HF Space must be configured under **Settings → Variables and Secrets**:

| Variable | Type | Description | Scope |
|---|---|---|---|
| `TANMAY_URL` | Variable (Public) | Render Orchestrator webhook URL | Context Worker only |
| `ORCHESTRATOR_URL` | Variable (Public) | Render Orchestrator webhook URL | All other nodes |
| `WEBHOOK_SECRET` | **Secret (Encrypted)** | Shared HMAC secret for inter-service authentication | All nodes |

> `WEBHOOK_SECRET` must be stored as an encrypted HF Secret and must never be exposed as a public Variable. This inter-service authentication scheme was designed by Tanmay Kumar to prevent unauthorised payload injection into the ML worker endpoints.

### Orchestrator (Render) Environment

The Orchestrator's Render environment must include the PostgreSQL connection string and the `WEBHOOK_SECRET` value matching the configuration applied to all HF Spaces. Connection pool parameters (`statement_cache_size: 0`, `prepared_statement_cache_size: 0`) are set programmatically within the application layer via Tanmay Kumar's database initialisation code.

---

## Node Attribution Reference

| Identifier | Type | Description | Engineering Credit |
|---|---|---|---|
| `tanmay` / `tanmayml01` | Principal Engineer + HF Namespace | All platform engineering, architecture, cloud deployment, and system integration | **Tanmay Kumar — 100%** |
| `yogesh` | Infrastructure tag | Local hardware allocation — development/staging proxy for the Media Processor node | Deployed and integrated under Tanmay Kumar's architecture |
| `yug` | Infrastructure tag | Local hardware allocation — development/staging proxy for the Context Worker node | Deployed and integrated under Tanmay Kumar's architecture |
| `rohit` | Infrastructure tag | Local hardware allocation — development/staging proxy for the Vision Service node | Deployed and integrated under Tanmay Kumar's architecture |

---

*Authored by Tanmay Kumar — Principal Architect & Lead Cloud Engineer, Overwatch Platform.*