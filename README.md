# SourceGraph / Overwatch

Distributed media-forensics and anti-piracy platform built around a FastAPI control plane, specialized worker nodes, PostgreSQL + pgvector persistence, and a React command center.

The system ingests video assets, extracts normalized frames and audio, runs multimodal analysis across dedicated worker services, reconciles evidence asynchronously, and produces operator-facing verdicts such as `PIRACY_DETECTED`, `SUSPICIOUS`, `LOW_CONFIDENCE`, and `CLEAN`.

## What This Project Does

- Uploads producer and auditor video assets into a shared pipeline
- Extracts `1 FPS` frames and `16 kHz` mono audio from source media
- Generates `512-D` visual embeddings with CLIP and object detections with YOLO
- Extracts OCR text and `384-D` semantic embeddings from frames
- Runs delayed audio transcription to avoid GPU memory contention
- Persists evidence and vectors in PostgreSQL with `pgvector`
- Fuses multimodal signals into similarity scores and final risk verdicts
- Exposes APIs, health telemetry, and dashboard data for the UI

## Architecture

The repo is organized as a distributed pipeline with one control-plane service and several worker nodes:

```text
overwatch-ui            -> React + Vite operator dashboard
orchestrator/backend    -> FastAPI control plane + PostgreSQL/pgvector
extractor               -> FastAPI ingress/FFmpeg fan-out worker
ml_vision               -> FastAPI visual inference worker (CLIP + YOLO + audio path)
ml_context              -> FastAPI OCR/semantic inference worker
ml_auditor              -> analysis assets / offline support
```

High-level flow:

1. A user uploads a golden asset or suspect clip.
2. The Orchestrator registers the asset and forwards the file to the Extractor.
3. The Extractor normalizes media and fans frames out to the Vision and Context nodes.
4. Workers post structured webhook events back to the Orchestrator.
5. The Orchestrator buffers, reconciles, stores, and scores the evidence.
6. The UI polls status and displays the final forensic result.

## Repository Layout

```text
.
├── artifacts/
│   └── backend_architecture.md
├── extractor/
│   ├── worker.py
│   └── requirements.txt
├── ml_auditor/
├── ml_context/
│   ├── main.py
│   └── requirements.txt
├── ml_vision/
│   ├── main.py
│   └── requirements.txt
├── orchestrator/
│   ├── docker-compose.yml
│   ├── database/
│   └── backend/
│       ├── app/
│       ├── requirements.txt
│       └── Dockerfile
├── overwatch-ui/
│   ├── src/
│   ├── public/
│   └── package.json
└── system_architecture.md
```

## Core Services

### 1. Orchestrator

Location: `orchestrator/backend/`

The Orchestrator is the system of record. It owns:

- asset lifecycle state
- authentication and session APIs
- webhook ingestion
- evidence reconciliation
- vector persistence
- similarity scoring
- dashboard feed and health aggregation

Important implementation notes:

- uses FastAPI + SQLAlchemy async + PostgreSQL
- enables `pgvector` at startup
- applies additive schema patches at startup instead of using Alembic migrations
- injects and propagates `X-Trace-ID` for end-to-end tracing

### 2. Extractor

Location: `extractor/`

The Extractor is the ingress foreman. It:

- receives uploaded media
- runs FFmpeg normalization
- emits `224x224` JPEG frames at `1 FPS`
- extracts `16 kHz` mono WAV audio
- broadcasts each frame to Vision and Context workers
- waits for worker drain before dispatching audio
- posts pipeline completion summaries back to the Orchestrator

### 3. Vision Node

Location: `ml_vision/`

The Vision node:

- computes CLIP `512-D` embeddings
- runs YOLOv8 object detection
- emits `frame_vision` and `vision_final_summary`
- hosts the delayed audio transcription path
- uses a single worker process because CUDA models are not fork-safe

### 4. Context Node

Location: `ml_context/`

The Context node:

- extracts OCR text with EasyOCR
- builds semantic `384-D` embeddings with MiniLM
- emits `frame_text` and `text_final_summary`
- accumulates OCR evidence across a batch
- performs final conflict detection on text-derived evidence

### 5. UI

Location: `overwatch-ui/`

The UI is a React + Vite command center used for:

- uploads
- login and session flows
- node health visibility
- asset status tracking
- forensic summaries and docs pages

## Technology Stack

### Backend

- FastAPI
- SQLAlchemy async
- PostgreSQL 17
- `pgvector`
- `httpx`
- JWT auth
- OTP and Google OAuth integration points

### Worker Nodes

- FastAPI
- FFmpeg
- CLIP
- YOLOv8
- EasyOCR
- Sentence Transformers / MiniLM
- Faster Whisper

### Frontend

- React 19
- TypeScript
- Vite
- Tailwind CSS
- Framer Motion

## Prerequisites

Recommended local prerequisites:

- Python `3.12` or compatible modern Python 3.x runtime
- Node.js `20+`
- npm
- Docker and Docker Compose
- FFmpeg available on the machine that runs `extractor/`
- NVIDIA/CUDA-capable environment for `ml_vision` and likely `ml_context` if you want full ML inference locally

## Quick Start

This is the simplest local bring-up path for the full stack.

### 1. Start PostgreSQL + Orchestrator

From the repo root:

```bash
cd orchestrator
docker compose up --build
```

This starts:

- PostgreSQL + `pgvector` on `localhost:5432`
- the Orchestrator API on `localhost:8000`

API docs will be available at:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

### 2. Run the Extractor

```bash
cd extractor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn worker:app --host 0.0.0.0 --port 8003
```

### 3. Run the Vision Node

```bash
cd ml_vision
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8081 --workers 1
```

### 4. Run the Context Node

```bash
cd ml_context
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8002
```

### 5. Run the UI

```bash
cd overwatch-ui
npm install
npm run dev
```

The Vite dev server runs on:

- `http://localhost:5173`

## Environment Configuration

Each service loads environment variables from its own `.env` file or from the shell environment.

### Orchestrator environment

Defined in `orchestrator/backend/app/config.py`.

Important variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://sourcegraph:...@localhost:5432/sourcegraph_vectors` |
| `TAILSCALE_IP` | host/IP used to build callback URLs back to the Orchestrator | `100.69.253.89` |
| `EXTRACTOR_URL` | Extractor base URL | `http://100.103.180.14:8003` |
| `VISION_NODE_URL` | Vision node base URL | `http://100.119.250.125:8080` |
| `CONTEXT_NODE_URL` | Context node base URL | `http://100.115.89.72:8002` |
| `AUDITOR_URL` | Auditor service base URL | `http://localhost:8004` |
| `WEBHOOK_SECRET` | shared secret for internal worker calls | `change-me-in-production` |
| `JWT_SECRET_KEY` | JWT signing secret | set a custom value |
| `GOOGLE_OAUTH_CLIENT_ID` | Google login integration | empty by default |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | OTP email delivery | unset or demo-safe defaults |
| `FUSION_WEIGHT_VISUAL`, `FUSION_WEIGHT_TEXT` | fusion scoring weights | `0.65`, `0.35` |
| `PIRACY_THRESHOLD`, `SUSPICIOUS_THRESHOLD` | verdict thresholds | `0.85`, `0.60` |
| `BUFFER_TTL_SECONDS` | webhook pairing TTL | `300` |
| `HOST`, `PORT`, `LOG_LEVEL` | API bind settings | `0.0.0.0`, `8000`, `INFO` |

Local dev note:

- `TAILSCALE_IP` matters because upload routes build a callback URL from it before handing work to the Extractor.
- For a purely local setup, set `TAILSCALE_IP=127.0.0.1` or `TAILSCALE_IP=localhost` to keep callbacks local.

### Extractor environment

Defined in `extractor/worker.py`.

Important variables:

| Variable | Purpose |
| --- | --- |
| `ORCHESTRATOR_URL` or `ORCHESTRATOR_WEBHOOK` | full feeder webhook URL |
| `ROHIT_URL` or `VISION_NODE_BASE` | Vision node base URL |
| `YUG_VISUAL_URL` or `CONTEXT_NODE_BASE` | Context node base URL |
| `X_WEBHOOK_SECRET` or `WEBHOOK_SECRET` | shared secret for internal calls |
| `FRAME_RATE` | frame extraction FPS |
| `FRAME_SIZE` | output frame size |
| `JPEG_QUALITY` | JPEG quality scalar |
| `GPU_TIMEOUT_S` | downstream worker timeout |
| `MAX_FRAME_RETRIES` | retry ceiling |
| `BACKOFF_INITIAL_S` | retry backoff starting point |
| `PING_INTERVAL_S` | system ping cadence |
| `GPU_IDLE_TIMEOUT_S` | max wait for worker drain |
| `GPU_IDLE_POLL_S` | polling interval while waiting for idle |

### Vision node environment

Defined in `ml_vision/main.py`.

| Variable | Purpose |
| --- | --- |
| `ORCHESTRATOR_URL` | full webhook feeder URL |
| `WEBHOOK_SECRET` | shared secret |
| `LOG_LEVEL` | log verbosity |
| `VISION_HOST` | bind host |
| `VISION_PORT` | bind port, default `8081` |

### Context node environment

Defined in `ml_context/main.py`.

| Variable | Purpose |
| --- | --- |
| `TANMAY_URL` | full Orchestrator feeder URL |
| `WEBHOOK_SECRET` | shared secret |
| `HOST` | bind host |
| `PORT` | bind port, default `8002` |

Important repo-specific note:

- the Context node currently reads `TANMAY_URL`, not `ORCHESTRATOR_URL`

### UI environment

Used in `overwatch-ui/src/lib/api.ts` and login screens.

| Variable | Purpose |
| --- | --- |
| `VITE_API_URL` | Orchestrator API base URL |
| `VITE_GOOGLE_CLIENT_ID` | Google OAuth client id for the frontend |

## Suggested Local `.env` Values

These are safe examples for local-only wiring:

### `orchestrator/backend/.env`

```env
DATABASE_URL=postgresql+asyncpg://sourcegraph:sg_vector_2024@localhost:5432/sourcegraph_vectors
TAILSCALE_IP=127.0.0.1
EXTRACTOR_URL=http://127.0.0.1:8003
VISION_NODE_URL=http://127.0.0.1:8081
CONTEXT_NODE_URL=http://127.0.0.1:8002
WEBHOOK_SECRET=local-dev-secret
JWT_SECRET_KEY=replace-me
LOG_LEVEL=DEBUG
```

### `extractor/.env`

```env
ORCHESTRATOR_URL=http://127.0.0.1:8000/api/v1/webhooks/feeder
ROHIT_URL=http://127.0.0.1:8081
YUG_VISUAL_URL=http://127.0.0.1:8002
X_WEBHOOK_SECRET=local-dev-secret
FRAME_RATE=1
FRAME_SIZE=224
```

### `ml_vision/.env`

```env
ORCHESTRATOR_URL=http://127.0.0.1:8000/api/v1/webhooks/feeder
WEBHOOK_SECRET=local-dev-secret
VISION_HOST=0.0.0.0
VISION_PORT=8081
LOG_LEVEL=INFO
```

### `ml_context/.env`

```env
TANMAY_URL=http://127.0.0.1:8000/api/v1/webhooks/feeder
WEBHOOK_SECRET=local-dev-secret
HOST=0.0.0.0
PORT=8002
```

### `overwatch-ui/.env`

```env
VITE_API_URL=http://127.0.0.1:8000
VITE_GOOGLE_CLIENT_ID=your-google-client-id
```

## Main API Surface

The most important API endpoints exposed by the Orchestrator are:

### Asset ingestion

- `POST /api/v1/assets/upload`
- `POST /api/v1/search/upload`

### Asset status and results

- `GET /api/v1/assets`
- `GET /api/v1/assets/{asset_id}/status`
- `GET /api/v1/assets/{asset_id}/result`

### Webhooks

- `POST /api/v1/webhooks/feeder`
- `POST /api/v1/webhooks/vector`
- `POST /api/v1/webhooks/complete`

### Auth

- `POST /api/v1/auth/request-otp`
- `POST /api/v1/auth/verify-otp`
- `POST /api/v1/auth/google`
- `GET /api/v1/auth/me`

### Health and dashboard

- `GET /`
- `GET /buffer/status`
- `POST /api/v1/health/heartbeat`

## Worker Event Contract

The feeder endpoint accepts multiple event types. The key ones are:

- `system_ping`
- `frame_vision`
- `frame_text`
- `vision_final_summary`
- `text_final_summary`
- `pipeline_final_summary`
- `audio_final_summary`

Important constraints enforced by the backend:

- visual vectors must be exactly `512` floats
- text vectors must be exactly `384` floats
- events may arrive out of order
- duplicate frame deliveries are handled defensively

## Typical End-to-End Development Flow

1. Start the Orchestrator and database.
2. Start the Extractor, Vision node, and Context node.
3. Start the UI.
4. Open `http://localhost:5173`.
5. Upload a golden asset or suspect clip.
6. Watch asset state move through `processing` to `completed`.
7. Inspect the result in the dashboard or via `GET /api/v1/assets/{asset_id}/result`.

## Observability

The platform includes several useful observability features:

- `X-Trace-ID` propagation from request to response
- worker `system_ping` heartbeats
- Orchestrator active health probing for GPU nodes
- buffer diagnostics via `GET /buffer/status`
- per-asset status polling
- explicit logging of missing SMTP/OAuth configuration

## Current Constraints and Known Sharp Edges

- full local inference may require GPU hardware and model downloads that are not practical on every machine
- the Orchestrator currently performs schema patching at startup instead of using full DB migrations
- some defaults still point to Tailscale or team-specific node addresses and should be overridden for local dev
- the Context node uses `TANMAY_URL` as its webhook target variable name
- the Vision node code defaults to port `8081`; keep your local config aligned with that
- the repo contains service-local `.env`, `venv`, `dist`, and `node_modules` content in places, so be careful about what you treat as source of truth

## Testing and Validation

Useful repo entry points for manual validation:

- `orchestrator/backend/orchestrator_test.py`
- `orchestrator/backend/test_db.py`
- `extractor/extractor_test.py`

You can also validate basic service health with:

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8003/health
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8002/health
```

## Documentation Already in the Repo

For deeper architecture context, see:

- `system_architecture.md`
- `artifacts/backend_architecture.md`
- `overwatch-ui/src/content/docs/intro.md`
- `overwatch-ui/src/content/docs/orchestrator.md`
- `overwatch-ui/src/content/docs/extractor.md`
- `overwatch-ui/src/content/docs/vision.md`
- `overwatch-ui/src/content/docs/context.md`
- `overwatch-ui/src/content/docs/forensics.md`

## Recommended Next Improvements

- add a proper root-level `.env.example` for every service
- replace startup schema patching with tracked database migrations
- unify environment variable names across workers
- add a reproducible `make` or `just` workflow for local bring-up
- add automated integration tests for the webhook contract
- add a single root `docker-compose` stack for all services

## License

No root license file is present in this repository right now. Add one before public distribution.
