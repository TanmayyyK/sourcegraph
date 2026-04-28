# M4 Orchestrator Node

The **M4 Orchestrator** is the central control-plane service for SourceGraph. It is the component that turns node-level evidence into a coherent platform state, and it is the primary layer owned by **Tanmay Kumar, Lead Architect**.

## Runtime Role

The Orchestrator is responsible for five categories of work:

1. **state coordination**
2. **persistence**
3. **vector reconciliation**
4. **policy evaluation**
5. **operator-facing API delivery**

It is not a heavy inference service. Its value comes from correctness, synchronization, and durable evidence handling.

## Runtime Stack

| Layer | Implementation |
| --- | --- |
| Web framework | FastAPI |
| Database | PostgreSQL |
| Vector extension | `pgvector` |
| HTTP client | `httpx` for node communication and health probing |
| Auth / sessions | JWT + OTP / Google OAuth integration points |
| UI consumer | React command center |

## Architectural Responsibilities

### Asset lifecycle ownership

The Orchestrator tracks assets from the moment ingest begins through terminal verdict completion. This includes:

- producer asset creation
- auditor ingestion and replay
- completion and failure locks
- dispatch coordination between phases

### Evidence persistence

The Orchestrator stores:

- asset records
- frame-level vectors
- OCR text
- similarity results
- final pipeline summaries
- lifecycle flags for audio and pipeline completion

### Vector synchronization

The most important backend behavior is its ability to accept **asynchronous modality arrival**.

The system explicitly supports a frame vector row being created with:

- visual vector only
- text vector only
- both vectors after later reconciliation

This is necessary because the Vision and Context workers are independent services with independent latency profiles.

## API and Contract Surface

At a high level, the Orchestrator exposes:

- ingest initiation APIs
- search and feed endpoints
- authentication and session routes
- webhook feeder endpoints for worker evidence
- operational status endpoints used by the command center

The request path is wrapped in trace middleware so a caller-supplied `X-Trace-ID` can propagate across the entire transaction.

## Traceability and Middleware

Each request receives a correlation identifier:

- reuse incoming `X-Trace-ID` when present
- otherwise generate a new UUID
- write it to `request.state.trace_id`
- echo it back in the response header

This makes distributed debugging significantly more tractable, especially when aligning frontend events with worker webhooks.

## Database Strategy

The backend uses PostgreSQL with `pgvector` enabled at startup.

### Core persistence themes

- vector-aware similarity storage
- durable asset lifecycle rows
- frame-level evidence accumulation
- schema patching at startup for additive evolution

### Practical schema notes

The startup flow currently performs idempotent schema patches for:

- OCR text persistence
- lifecycle lock columns on `assets`
- nullable visual / text vectors on `frame_vectors`
- temporary row support for suspect content

This approach is intentionally pragmatic for the current stage of the product. It avoids blocking the demo environment on a full migration framework while still keeping startup safe and repeatable.

## Webhook Buffer Service

The buffer service exists because worker nodes do not always emit related payloads at the same time.

### What it solves

- late-arriving visual and text payloads
- small timestamp drifts across services
- temporary webhook ordering issues
- bounded in-memory pairing before persistence finalization

### Important controls

| Control | Current Purpose |
| --- | --- |
| TTL | drop stale, incomplete buffered pairs |
| cleanup interval | keep memory bounded |
| temporal slop | tolerate minor timestamp drift |
| max buffer size | prevent runaway memory growth |

This is one of the architectural features that makes the distributed system behave like a single product rather than a collection of unrelated workers.

## Health Aggregation

The Orchestrator does not wait passively for workers to talk first. It also runs an active health probe loop against the GPU node endpoints.

That gives the command center two useful properties:

- workers can appear online even when no ingest is currently active
- operator dashboards can separate a quiet system from an unreachable system

## Thresholds and Policy

The backend owns the currently active risk policy:

| Setting | Current Value |
| --- | --- |
| `visual_dim` | `512` |
| `text_dim` | `384` |
| `fusion_weight_visual` | `0.65` |
| `fusion_weight_text` | `0.35` |
| `piracy_threshold` | `0.85` |
| `suspicious_threshold` | `0.60` |

These values are operational configuration, not model trivia. They directly shape alerting behavior and user trust.

## Fusion and Threat Detection

The backend computes a fused score after enough evidence has arrived to compare the suspect asset against protected content.

The logic is conceptually:

1. accept visual and text signals independently
2. reconcile them to the same asset / timestamp lineage
3. compare against golden vectors
4. calculate a fused similarity score
5. apply thresholds and conflict penalties
6. persist the result for the UI and future audit

## Failure Handling

The Orchestrator is built to fail visibly rather than ambiguously.

### Typical defensive behaviors

- startup logs extension and schema failures explicitly
- worker schema violations surface as `422`, not silent corruption
- terminal asset conflicts return `409` to stop invalid continued processing
- lifecycle completion flags prevent duplicate downstream dispatch
- missing SMTP or OAuth configuration is logged rather than hidden

## Security and Boundary Discipline

Important security boundaries include:

- webhook secret validation for internal node calls
- auth separation between anonymous and authenticated routes
- asset state transitions that prevent duplicate writes
- deliberate separation between internal cluster addresses and user-facing endpoints

## Scalability Characteristics

The current backend is designed for correctness-first scaling:

- workers scale horizontally by service role, not by generic queue consumers
- vector writes tolerate partial arrival ordering
- node health is decoupled from active ingest throughput
- the control plane stays lightweight because inference remains outside it

## Why the Orchestrator Matters

Without this service, the platform would simply be a few ML endpoints and a database. The Orchestrator is the layer that gives the platform **memory, ordering, policy, and explainability**. It is the reason the system can support both live product workflows and defensible forensic review.
