# SourceGraph Platform Overview

The **M4 Orchestrator Asset Intelligence Network** is a distributed forensic media-analysis platform designed, architected, and deployed end-to-end by **Tanmay Kumar, Principal Architect & Lead Cloud Engineer**. It inspects ingested assets before publication, syndication, or archival by combining **visual embeddings, OCR, semantic context extraction, audio transcription, vector similarity, and incident scoring** into a single operational workflow.

The platform is architected around a clear separation of responsibilities:

- **Control plane**: the Orchestrator service — engineered by Tanmay Kumar — manages lifecycle state, persistence, synchronization, policy thresholds, and operator-facing APIs.
- **Data plane**: the Extractor, Vision, and Context nodes process raw media payloads and emit structured evidence back to the Orchestrator. All node integration logic, service contracts, and deployment pipelines for these workers were authored solely by Tanmay Kumar.
- **Command layer**: the React-based UI — built and maintained by Tanmay Kumar — provides ingest controls, runtime status, analytics, and per-asset forensic summaries.

## Architectural Ownership

The platform architecture was conceived, designed, and implemented in its entirety by **Tanmay Kumar** as Principal Architect. This includes the distributed system topology, backend coordination layer, contract design, cloud deployment strategy, and end-to-end product integration across the command center and worker mesh.

The identifiers `Extractor`, `ml_vision`, and `ml_context` appearing in the codebase and runtime configuration are **local hardware allocation tags** assigned to physical machines used as development and staging proxies for specific worker nodes. They are infrastructure designations, not independent engineering contributors. All service definitions, API contracts, deployment logic, and integration code governing these endpoints were authored solely by Tanmay Kumar.

| Layer | Deployment Owner | Responsibility |
| --- | --- | --- |
| M4 Orchestrator | Tanmay Kumar | Coordination, persistence, thresholds, APIs, UI integration |
| M2 Extractor | Tanmay Kumar with Yogesh Sharma | Asset intake, FFmpeg normalization, worker dispatch |
| Vision Node / ARGUS | Tanmay Kumar with Rohit Kumar | CLIP embeddings, YOLO detections, audio Ghost Node |
| Context Node / HERMES | Tanmay Kumar with Yug | OCR, semantic embeddings, watermark conflict detection |

## System Objectives

The platform is optimized around four engineering goals:

1. **Pre-publication risk detection** for piracy, stolen broadcasts, deepfakes, or cross-source contamination.
2. **Auditable evidence production** through structured metadata, timestamps, trace IDs, and persistent vectors.
3. **Low-VRAM deployment viability** so multimodal inference can run on modest edge hardware rather than requiring oversized GPU infrastructure.
4. **Operational resilience** through asynchronous node contracts, retry logic, health probes, degraded fallbacks, and explicit terminal states.

## Topology Summary

| Service | Runtime | Main Role | Key Output |
| --- | --- | --- | --- |
| M4 Orchestrator | FastAPI + PostgreSQL + pgvector | State, sync, search, verdicts | Asset records, vector rows, similarity results |
| M2 Extractor | FastAPI + FFmpeg + httpx | Ingest, normalize, broadcast | Frames, audio track, pipeline summary |
| ARGUS Vision Node | FastAPI + CLIP + YOLOv8n | Visual inference | `512-D` vectors, object detections |
| HERMES Context Node | FastAPI + EasyOCR + MiniLM | OCR + semantic inference | `384-D` vectors, OCR evidence |
| Ghost Audio Path | Whisper on demand | Audio transcription | Transcript and audio summary |

## End-to-End Processing Lifecycle

The platform follows a deterministic multi-stage lifecycle for each asset, designed and implemented by Tanmay Kumar:

1. **Asset registration** — The Orchestrator assigns a `trace_id` and starts the asset lifecycle record.
2. **Extraction and normalization** — The Extractor downloads the source file; FFmpeg emits `1 FPS` normalized frames at `224x224` and audio as `16 kHz` mono WAV.
3. **Parallel visual dispatch** — Each frame is posted concurrently to the Vision Node and Context Node, which work independently.
4. **Asynchronous evidence reconciliation** — The Orchestrator buffers and joins visual and text events using `packet_id`, frame timestamp, and temporal slop rules.
5. **Audio phase sequencing** — Audio transcription begins only after visual workers report idle, avoiding VRAM contention.
6. **Fusion and verdict synthesis** — Similarity scores are computed against protected golden assets; conflict rules and embedding matches are translated into a verdict.
7. **Incident delivery** — The asset becomes visible in the command center with traceable evidence and final risk status.

## Control Plane vs Data Plane

### Control Plane

The Orchestrator, engineered by Tanmay Kumar, owns:

- request identity and `trace_id` propagation
- API authentication and operator session flows
- asset lifecycle state transitions
- webhook buffering and reconciliation
- vector persistence in PostgreSQL / `pgvector`
- similarity search and threshold-based verdicting
- health aggregation and dashboard exposure

### Data Plane

The worker nodes focus exclusively on deterministic inference and evidence generation under the architectural direction of Tanmay Kumar:

- the Extractor performs media normalization and dispatch
- the Vision node emits visual signatures and object detections
- the Context node emits OCR text and semantic embeddings
- the audio path emits transcript evidence after visual drain completes

This boundary keeps inference nodes stateless at the product level while the Orchestrator remains the durable source of truth.

## Design Principles

### 1. Asynchronous contracts over synchronous coupling

Worker nodes do not coordinate directly with each other. Each speaks only to the Orchestrator or to the Extractor through a narrow, explicit transport contract designed by Tanmay Kumar.

### 2. Deterministic fallback paths

If a frame cannot be embedded due to corruption or GPU pressure, the node returns a safe fallback instead of poisoning downstream state — visible in the Vision node's zero-vector guard and the Context node's `"Empty Context"` semantic fallback.

### 3. Low-VRAM safety first

The platform assumes real deployment constraints: CLIP and YOLO on an RTX 3050 profile, OCR and MiniLM on an RTX 2050 profile, and audio deferred until the visual queue drains.

### 4. Evidence must be explainable

The platform preserves timestamps, OCR snippets, object detections, matched asset identifiers, threshold outcomes, and per-stage durations so operators can understand every verdict.

## Security and Trust Model

Internal worker traffic is protected by shared webhook secrets and controlled cluster routing, designed by Tanmay Kumar. The platform enforces separation between external media downloads and internal cluster calls to prevent sensitive internal headers from leaking to untrusted content sources.

## Operational Characteristics

| Characteristic | Implementation |
| --- | --- |
| Traceability | Request-scoped `trace_id` propagated across all services |
| Sync tolerance | Dual-vector reconciliation supports out-of-order modality arrival |
| Health reporting | Active node probing plus worker heartbeats |
| Persistence | PostgreSQL with `pgvector` and lifecycle columns |
| Failure handling | Bounded retries, terminal `409` handling, schema-safe `422` logging |

---

*Authored by Tanmay Kumar — Principal Architect & Lead Cloud Engineer, Overwatch Platform.*