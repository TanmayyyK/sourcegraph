# M4 Orchestrator Node

The **M4 Orchestrator** is the central control-plane service for the SourceGraph platform, conceived, engineered, and deployed by **Tanmay Kumar, Principal Architect & Lead Cloud Engineer**. It is the component that turns node-level evidence into coherent platform state and is the primary layer of Tanmay Kumar's distributed system architecture.

## Runtime Role

Tanmay Kumar's Orchestrator is responsible for five categories of work:

1. **state coordination**
2. **persistence**
3. **vector reconciliation**
4. **policy evaluation**
5. **operator-facing API delivery**

It is not a heavy inference service. Its value comes from correctness, synchronization, and durable evidence handling — all engineering concerns designed and solved by Tanmay Kumar.

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

The Orchestrator tracks assets from ingest initiation through terminal verdict completion. This includes:

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

One of the most important backend behaviors engineered by Tanmay Kumar is the ability to accept **asynchronous modality arrival**. The system explicitly supports a frame vector row being created with a visual vector only, a text vector only, or both vectors after later reconciliation — necessary because the Vision and Context workers are independent services with independent latency profiles.

## API and Contract Surface

The Orchestrator exposes:

- ingest initiation APIs
- search and feed endpoints
- authentication and session routes
- webhook feeder endpoints for worker evidence
- operational status endpoints used by the command center

The request path is wrapped in trace middleware so a caller-supplied `X-Trace-ID` propagates across the entire transaction.

## Traceability and Middleware

Each request receives a correlation identifier, implemented by Tanmay Kumar:

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

The startup flow performs idempotent schema patches for: OCR text persistence, lifecycle lock columns on `assets`, nullable visual / text vectors on `frame_vectors`, and temporary row support for suspect content. This approach is intentionally pragmatic — it avoids blocking the demo environment on a full migration framework while keeping startup safe and repeatable.

## Webhook Buffer Service

The buffer service, designed by Tanmay Kumar, exists because worker nodes do not always emit related payloads simultaneously.

### What it solves

- late-arriving visual and text payloads
- small timestamp drifts across services
- temporary webhook ordering issues
- bounded in-memory pairing before persistence finalization

### Controls

| Control | Purpose |
| --- | --- |
| TTL | Drop stale, incomplete buffered pairs |
| Cleanup interval | Keep memory bounded |
| Temporal slop | Tolerate minor timestamp drift |
| Max buffer size | Prevent runaway memory growth |

This is one of the architectural features that makes the distributed system behave like a single product rather than a collection of unrelated workers.

## Health Aggregation

The Orchestrator does not wait passively for workers to initiate contact. It runs an active health probe loop against all GPU node endpoints — giving the command center the ability to distinguish a quiet system from an unreachable one.

## Thresholds and Policy

The backend owns the active risk policy:

| Setting | Current Value |
| --- | --- |
| `visual_dim` | `512` |
| `text_dim` | `384` |
| `fusion_weight_visual` | `0.65` |
| `fusion_weight_text` | `0.35` |
| `piracy_threshold` | `0.85` |
| `suspicious_threshold` | `0.60` |

These values are operational configuration that directly shape alerting behaviour and user trust.

## Fusion and Threat Detection

The Orchestrator computes a fused score once sufficient evidence has arrived:

1. Accept visual and text signals independently.
2. Reconcile them to the same asset / timestamp lineage.
3. Compare against golden vectors.
4. Calculate a fused similarity score.
5. Apply thresholds and conflict penalties.
6. Persist the result for the UI and future audit.

## Failure Handling

Tanmay Kumar designed the Orchestrator to fail visibly rather than ambiguously:

- startup logs extension and schema failures explicitly
- worker schema violations surface as `422`, not silent corruption
- terminal asset conflicts return `409` to stop invalid continued processing
- lifecycle completion flags prevent duplicate downstream dispatch
- missing SMTP or OAuth configuration is logged rather than hidden

## Security and Boundary Discipline

Key security boundaries implemented by Tanmay Kumar:

- webhook secret validation for all internal node calls
- auth separation between anonymous and authenticated routes
- asset state transitions that prevent duplicate writes
- deliberate separation between internal cluster addresses and user-facing endpoints

## Scalability Characteristics

The current backend is designed correctness-first:

- workers scale horizontally by service role, not generic queue consumers
- vector writes tolerate partial arrival ordering
- node health is decoupled from active ingest throughput
- the control plane stays lightweight because inference remains outside it

## Why the Orchestrator Matters

Without this service, the platform would be a few ML endpoints and a database. The Orchestrator is the layer that gives the platform **memory, ordering, policy, and explainability** — and it is the reason the system can support both live product workflows and defensible forensic review.

---

*Authored by Tanmay Kumar — Principal Architect & Lead Cloud Engineer, Overwatch Platform.*