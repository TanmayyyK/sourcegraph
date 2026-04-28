# Vision Node

The **Vision Node**, operating under the ARGUS role, is the platform's dedicated visual inference worker. Its job is to convert normalized frames into machine-comparable visual evidence while remaining safe under constrained GPU conditions.

## Core Responsibility

This node performs two visual tasks on every frame:

1. **semantic visual embedding generation**
2. **object-level detection for explainability**

Those outputs serve different purposes. The embedding supports similarity search and fusion scoring, while the detections help operators understand what was actually present in the frame.

## Runtime Profile

| Characteristic | Value |
| --- | --- |
| Node owner | Rohit Kumar |
| Hardware target | `NVIDIA RTX 3050` |
| Primary embedding model | `openai/clip-vit-base-patch32` |
| Embedding dimension | `512-D` |
| Detection model | `YOLOv8n` |

The node is intentionally run with a single worker process because CUDA model instances are not fork-safe once initialized.

## Model Stack

### CLIP path

The CLIP pipeline produces a dense visual signature that can be compared against stored protected content vectors.

Operational characteristics:

- `fp16` execution for memory efficiency
- `512-D` output vector
- L2-normalized embedding
- designed for approximate similarity search downstream

### YOLO path

The YOLO stage extracts explicit object evidence:

- top-K detections
- labels
- confidence values
- bounding-box geometry

This is useful for interpretability and downstream UI presentation even when the embedding already exists.

## Outgoing Contract

The Vision node emits:

- `frame_vision` for each successfully processed frame
- `vision_final_summary` after `/embed/visual/finish`
- periodic `system_ping` events to keep the control plane aware of liveness

The packet schema is intentionally explicit so the Orchestrator can treat the node as a trustworthy but independent worker.

## Batch Tracking

The node maintains a per-`packet_id` tracker to count processed frames and detect duplicate timestamps. This is important because retries or replays must not silently inflate the apparent amount of visual evidence.

## Zero-Vector Guard

One of the more important implementation details is the zero-vector guard.

If CLIP fails because of:

- CUDA pressure
- corrupt image bytes
- preprocessing issues
- model-side runtime failures

the engine returns an all-zero fallback vector. The route layer detects that condition and avoids treating it as valid evidence. This prevents poisoned or meaningless vectors from entering the similarity store.

## Audio Ghost Node

The Vision service also hosts the ephemeral audio path.

### Why audio lives here

Audio transcription is logically adjacent to the visual GPU environment, but it must not interfere with active visual inference. The system therefore treats Whisper as a staged, temporary workload rather than a permanently co-resident model.

### Audio sequence

1. Extractor finishes visual dispatch.
2. GPU nodes report idle.
3. The Vision audio endpoint accepts the `16 kHz` WAV file.
4. Whisper is loaded and transcription runs synchronously.
5. The audio engine is unloaded aggressively after completion.

This design allows the same hardware tier to serve both visual and audio roles without forcing them to compete continuously.

## Failure and Timeout Controls

The node has several important operational safeguards:

- bounded webhook retry logic
- timeout protection around Whisper transcription
- explicit heartbeat emissions
- graceful VRAM release on shutdown
- logging around empty or misconfigured webhook secrets

## Explainability Value

The Vision node is not only a feature extractor. It also helps answer human questions such as:

- what object categories were visible?
- did the match come from actual scene content or a repeated framing pattern?
- were there enough valid frames to trust the similarity signal?

That makes it a crucial bridge between raw ML output and operator confidence.

## Practical Engineering Tradeoff

This node is optimized for **reliability under limited GPU memory**, not maximum model complexity. CLIP + YOLOv8n is a deliberately practical pairing: strong enough to generate meaningful evidence, small enough to remain operational in a distributed demo-grade environment.
