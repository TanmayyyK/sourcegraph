# SourceGraph Platform Overview

The **M4 Orchestrator Asset Intelligence Network** is a distributed forensic media-analysis platform designed to inspect ingested assets before publication, syndication, or archival. It combines **visual embeddings, OCR, semantic context extraction, audio transcription, vector similarity, and incident scoring** into a single operational workflow.

The platform is architected around a clear separation of responsibilities:

- **Control plane**: the Orchestrator service manages lifecycle state, persistence, synchronization, policy thresholds, and operator-facing APIs.
- **Data plane**: the Extractor, Vision, and Context nodes process the raw media payload and emit structured evidence back to the Orchestrator.
- **Command layer**: the React-based UI provides ingest controls, runtime status, analytics, and per-asset forensic summaries.

## Leadership and Architectural Ownership

The platform architecture is led by **Tanmay Kumar, Lead Architect**, who owns the distributed system shape, backend coordination layer, contract design, and end-to-end product integration across the command center and worker topology.

Node-level execution is distributed across the engineering team:

| Layer | Primary Owner | Responsibility |
| --- | --- | --- |
| M4 Orchestrator | Tanmay Kumar | Coordination, persistence, thresholds, APIs, UI integration |
| M2 Extractor | Yogesh Sharma | Asset intake, FFmpeg normalization, worker dispatch |
| Vision Node / ARGUS | Rohit Kumar | CLIP embeddings, YOLO detections, audio Ghost Node |
| Context Node / HERMES | Yug | OCR, semantic embeddings, watermark conflict detection |

## System Objectives

The platform is optimized around four engineering goals:

1. **Pre-publication risk detection** for piracy, stolen broadcasts, deepfakes, or cross-source contamination.
2. **Auditable evidence production** through structured metadata, timestamps, trace IDs, and persistent vectors.
3. **Low-VRAM deployment viability** so multimodal inference can run on modest edge hardware instead of requiring oversized GPU infrastructure.
4. **Operational resilience** through asynchronous node contracts, retry logic, health probes, degraded fallbacks, and explicit terminal states.

## Topology Summary

| Service | Runtime | Main Role | Key Output |
| --- | --- | --- | --- |
| M4 Orchestrator | FastAPI + PostgreSQL + pgvector | State, sync, search, verdicts | Asset records, vector rows, similarity results |
| M2 Extractor | FastAPI + FFmpeg + httpx | Ingest, normalize, broadcast | Frames, audio track, pipeline summary |
| ARGUS Vision Node | FastAPI + CLIP + YOLOv8n | Visual inference | `512-D` vectors, object detections |
| HERMES Context Node | FastAPI + EasyOCR + MiniLM | OCR + semantic inference | `384-D` vectors, OCR evidence |
| Ghost Audio Path | Whisper on demand | Audio transcription | transcript and audio summary |

## End-to-End Processing Lifecycle

The platform follows a deterministic multi-stage lifecycle for each asset:

1. **Asset registration**
   - A producer or auditor initiates ingest with a media reference and a logical asset context.
   - The Orchestrator assigns or propagates a `trace_id` and starts the asset lifecycle record.

2. **Extraction and normalization**
   - The Extractor downloads the source file or receives an upload.
   - `FFmpeg` emits `1 FPS` normalized frames at `224x224`.
   - Audio is extracted as `16 kHz`, mono WAV when available.

3. **Parallel visual dispatch**
   - Each frame is posted concurrently to the Vision Node and Context Node.
   - The two nodes work independently and may report results out of order.

4. **Asynchronous evidence reconciliation**
   - The Orchestrator buffers and joins visual and text events using `packet_id`, frame timestamp, and temporal slop rules.
   - Vector rows are created even when one modality arrives before the other.

5. **Audio phase sequencing**
   - Audio transcription begins only after the visual workers report idle conditions.
   - This avoids CLIP/YOLO and Whisper competing for the same VRAM envelope.

6. **Fusion and verdict synthesis**
   - Similarity scores are computed against protected golden assets.
   - Conflict rules, embedding matches, and metadata cues are translated into a verdict.

7. **Incident delivery**
   - The asset becomes visible in the command center with traceable evidence, operational timings, and final risk status.

## Control Plane vs Data Plane

### Control Plane

The Orchestrator owns the following concerns:

- request identity and `trace_id` propagation
- API authentication and operator session flows
- asset lifecycle state transitions
- webhook buffering and reconciliation
- vector persistence in PostgreSQL / `pgvector`
- similarity search and threshold-based verdicting
- health aggregation and dashboard exposure

### Data Plane

The worker nodes focus exclusively on deterministic inference and evidence generation:

- the Extractor performs media normalization and dispatch
- the Vision node emits visual signatures and object detections
- the Context node emits OCR text and semantic embeddings
- the audio path emits transcript evidence after visual drain completes

This boundary is important because it keeps inference nodes stateless at the product level while allowing the Orchestrator to remain the durable source of truth.

## Design Principles

### 1. Asynchronous contracts over synchronous coupling

The worker nodes do not need to coordinate directly with each other. Each node speaks only to the Orchestrator or to the Extractor through a narrow, explicit transport contract.

### 2. Deterministic fallback paths

If a frame cannot be embedded due to corruption or GPU pressure, the node returns a safe fallback instead of poisoning downstream state. This is visible in the Vision node's zero-vector guard and the Context node's `"Empty Context"` semantic fallback.

### 3. Low-VRAM safety first

The platform assumes real deployment constraints:

- Vision runs CLIP and YOLO on an RTX 3050 profile.
- Context runs OCR and MiniLM on an RTX 2050 profile.
- Audio work is deferred until the visual queue is drained.
- explicit cleanup is part of the design, not an afterthought.

### 4. Evidence must be explainable

Similarity signals are only useful if the operator can understand the decision. The platform therefore preserves:

- timestamps
- OCR snippets
- object detections
- matched asset identifiers
- threshold outcomes
- per-stage durations

## Security and Trust Model

Internal worker traffic is protected by shared webhook secrets and controlled cluster routing. The platform also enforces separation between external media downloads and internal cluster calls so sensitive internal headers are not leaked to untrusted content sources.

Key trust assumptions:

- only internal services may call worker endpoints with valid node secrets
- the Orchestrator remains the authoritative asset registry
- terminal failure states must short-circuit continued processing
- evidence should be append-only from the perspective of user-facing audit review

## Operational Characteristics

| Characteristic | Implementation |
| --- | --- |
| Traceability | request-scoped `trace_id` is propagated across services |
| Sync tolerance | dual-vector reconciliation supports out-of-order modality arrival |
| Health reporting | active node probing plus worker heartbeats |
| Persistence | PostgreSQL with `pgvector` and lifecycle columns |
| Failure handling | bounded retries, terminal `409` handling, schema-safe `422` logging |

## Current Engineering Constraints

The current architecture is intentionally pragmatic rather than over-generalized:

- the audio path is expensive and therefore sequential
- GPU workers are designed as specialized single-purpose services rather than generic batch executors
- schema patching is currently handled in startup logic rather than a full migration framework
- some public-facing docs still describe the worker topology using internal codenames, which is acceptable for demo-stage engineering docs but should be normalized in a production documentation pass

## Why This Architecture Matters

The system is not just a set of models behind an upload form. It is a **forensic runtime**: each asset passes through a traceable sequence of extract, infer, reconcile, score, and report. That structure is what allows the platform to support both **producer assurance** and **auditor investigation** from the same core pipeline.
