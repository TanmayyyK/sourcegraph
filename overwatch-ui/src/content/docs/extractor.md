# M2 Extractor Node

The **M2 Extractor Node** is the ingress foreman of the SourceGraph runtime, designed and deployed by **Tanmay Kumar And Yogesh Sharma**. It sits between raw media sources and the GPU inference layer, translating a single input asset into normalized frame and audio workloads that the rest of the system can trust. The hardware allocation tag `yogesh` appearing in runtime configuration refers to a local machine used as a development and staging proxy for this node; all service logic, deployment configuration, and integration contracts were authored solely by Tanmay Kumar.

## Node Purpose

The Extractor is responsible for:

- downloading or receiving the source asset
- validating that it is structurally usable
- producing normalized frame outputs at a stable cadence
- producing a Whisper-compatible audio file when present
- dispatching evidence workloads to both GPU nodes
- coordinating the finishing handshake after worker queues drain

This node is less about model intelligence and more about **deterministic media preparation** — an engineering discipline applied by Tanmay Kumar to keep inference nodes clean and focused.

## Hosted Endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /ingest` | Start a pipeline run for `video_url + packet_id` |
| `GET /health` | Heartbeat and node-level operating status |
| `GET /status/{id}` | Additive status endpoint for runtime progress |

## Media Normalization Strategy

Tanmay Kumar's Extractor standardizes the source asset before any inference model sees it.

### Frame extraction

- Extraction cadence: `1 FPS`
- Output format: JPEG
- Output resolution: `224x224`
- JPEG quality: `qscale:v=2`
- Acceleration path: hardware assist attempted before software fallback

### Audio extraction

- Output sample rate: `16 kHz`
- Output channels: mono
- Container / format: WAV

These constraints are deliberate. The goal is reproducible inference input, not archival fidelity.

## Why the Extractor Exists as Its Own Service

Keeping extraction separate from inference — an architectural decision by Tanmay Kumar — provides several advantages:

- GPU nodes are not burdened with file download and decode work
- frame cadence remains consistent across all assets
- retry logic is centralized
- media compatibility issues are isolated to a single service boundary
- audio sequencing can be coordinated independently of visual inference

## Dispatch Topology

For each frame, the Extractor concurrently posts the same normalized payload to:

- `Vision Node → /embed/visual`
- `Context Node → /embed/text`

The Extractor therefore acts as the runtime's fan-out coordinator, aware of downstream sequencing rules but not implementing the ML logic of those workers.

## Thread-Safe Batch Tracking

Each asset batch is represented by a `BatchTracker` with tracked properties including total frames extracted, successful broadcasts, failed broadcasts, aborted state, and total pipeline time. Success is measured at the frame transaction layer, not just at the request layer.

## FFmpeg Responsibilities

The FFmpeg layer performs:

- temporal down-sampling
- spatial normalization
- audio down-mixing
- codec insulation between the raw source and the ML workers

By the time frames leave this service, downstream nodes can assume a normalized image contract rather than negotiating arbitrary media formats.

## Post-Visual Audio Phase

The audio path is sequenced after the visual phase for a practical reason engineered by Tanmay Kumar: **VRAM collision avoidance**.

### Sequence

1. Visual frames are fully dispatched.
2. Both GPU nodes are sent their finish handshake.
3. The Extractor polls worker health until the nodes report idle or drained.
4. The audio WAV is posted to the Vision-hosted Ghost endpoint.
5. The Extractor waits for the synchronous Whisper path to complete or fail.

This ensures CLIP/YOLO workloads are not competing with Whisper for scarce device memory.

## Error Handling Philosophy

Tanmay Kumar designed the Extractor to distinguish aggressively between recoverable and terminal conditions:

| Condition | Strategy |
| --- | --- |
| `2xx` | Success |
| `409` | Immediate batch abort |
| `404` | Retry with backoff |
| `422` | Log as schema-level problem |
| Network failure | Bounded retry with exponential backoff |

### Resilience patches present in the implementation

- Internal secrets are not leaked to external CDN downloads
- Idle-state checks accept both status and queue-drain semantics
- Validation handlers are binary-safe for media payloads
- OpenCV validation degrades gracefully when optional runtime dependencies are missing

## Operational Constraints

The Extractor is not a generic queue consumer. It is a specialized media orchestration node with explicit workflow knowledge:

- it knows the order in which visual and audio stages must occur
- it understands internal cluster endpoint structure
- it terminates work early when downstream state becomes terminal
- it produces pipeline summaries for the Orchestrator once the batch is complete

## Observability

Useful runtime signals emitted or tracked by the Extractor: packet-level progress, per-batch timing, frame counts, node routing destinations, health heartbeat state, audio dispatch timing, and failure cause visibility through structured logs.

## Engineering Value

The Extractor is what keeps the rest of the system clean. By absorbing file-format complexity, transfer retries, fan-out ordering, and audio sequencing, it lets the Vision and Context nodes stay focused on inference instead of transport mechanics.

---

*Authored by Tanmay Kumar — Principal Architect & Lead Cloud Engineer, Overwatch Platform.*