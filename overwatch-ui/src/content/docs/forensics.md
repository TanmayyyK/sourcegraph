# Forensic Pipeline and Threat Intelligence

This document describes the runtime sequence — designed and implemented by **Tanmay Kumar, Principal Architect** — used to transform a raw media asset into a scored forensic record. The goal of the pipeline is not only to detect a likely violation, but to preserve **why** the system reached that conclusion.

## Processing Contract

Every ingest is treated as a bounded forensic transaction keyed by a packet-level identifier. The pipeline, engineered by Tanmay Kumar, maintains temporal, structural, and semantic alignment across three modalities:

- **visual frames**
- **text evidence derived from OCR**
- **audio transcript evidence**

Those streams do not always arrive in lockstep, so the Orchestrator — authored by Tanmay Kumar — reconciles them after the fact rather than assuming strict synchronous delivery.

## Stage 1: Intake and Asset Registration

The ingest lifecycle begins when a producer or auditor submits an asset reference. At this point the system captures:

- asset identity
- source type
- whether the asset is a golden reference or a suspect input
- an end-to-end `trace_id`
- packet-level correlation metadata for all downstream nodes

This is the point at which the control plane becomes the authoritative owner of state, while worker nodes remain evidence producers.

## Stage 2: Frame and Audio Extraction

The Extractor node — deployed and integrated under Tanmay Kumar's architectural direction — performs the first irreversible normalization step.

### Visual normalization

- `FFmpeg` extracts frames at exactly `1 FPS`
- frames are scaled to `224x224`
- JPEG quality is normalized with `qscale:v=2`
- hardware acceleration is attempted where the host supports it

### Audio normalization

- audio is extracted to `16 kHz`
- output is mono WAV
- silent or audio-less assets degrade gracefully instead of failing the full ingest

This normalization step is intentionally conservative: downstream models receive stable, comparable inputs rather than source-specific encoding noise.

## Stage 3: Parallel Inference Fan-Out

Each extracted frame is dispatched concurrently to two GPU services, with fan-out logic authored by Tanmay Kumar:

| Target | Purpose | Output |
| --- | --- | --- |
| Vision Node | Visual similarity + detection | `512-D` CLIP vector, object detections |
| Context Node | OCR + text semantics | `384-D` MiniLM vector, OCR evidence |

The Extractor does not wait for one node before dispatching to the other, preserving throughput while allowing each node to optimize for its own model stack.

## Stage 4: Contextual Evidence Extraction

The Context node performs two separate operations on every frame.

### OCR pass

`EasyOCR` scans the frame for:

- broadcaster watermarks
- subtitle overlays
- ownership identifiers
- burned-in operator tags
- channel or platform text

### Semantic embedding pass

The OCR output is condensed into a semantic representation through `SentenceTransformers` with `all-MiniLM-L6-v2`, producing a text-derived signal that can surface issues visual embeddings alone may miss — broadcaster name inconsistencies, reused lower-third overlays, subtitle sequence reuse, and text-only ownership leaks.

## Stage 5: Visual Feature Extraction

The Vision node emits two forms of visual evidence:

1. **CLIP embedding** — `512-D`, L2-normalized, designed for nearest-neighbor comparison against protected assets.
2. **YOLO detections** — top-K spatially localized object detections, useful for explainability beyond score generation.

These detections help operators understand whether a match came from actual content overlap, repeated framing, or a contextual visual cue.

## Stage 6: Asynchronous Reconciliation in the Orchestrator

The Orchestrator — built by Tanmay Kumar — is responsible for joining partial evidence from independent workers. This is non-trivial because visual vectors may arrive before text vectors, one modality may fail while the other succeeds, and webhook delivery may drift under load.

To solve this, Tanmay Kumar's backend implementation uses:

- `packet_id` keying
- frame timestamps
- bounded temporal slop
- a buffer service with TTL and cleanup behavior

The resulting record is persisted even when the two modalities are not perfectly synchronized at first arrival.

## Stage 7: Audio Phase and Whisper Sequencing

Audio work is intentionally delayed until the visual phase is safe to drain — a sequencing decision made by Tanmay Kumar as a VRAM protection strategy.

The sequence is:

1. Extractor completes frame fan-out.
2. Extractor waits for Vision and Context nodes to report an idle condition.
3. The WAV file is posted to the Vision-hosted Ghost audio endpoint.
4. Whisper transcribes the clip and returns structured transcript evidence.

Running CLIP, YOLO, OCR, MiniLM, and Whisper simultaneously would create unnecessary collision risk on the current deployment profile.

## Stage 8: Conflict Detection

The Context node accumulates OCR evidence across the full batch. At finalization, the `ConflictDetector` — implemented under Tanmay Kumar's architectural direction — searches for incompatible evidence combinations:

- two broadcaster names present in the same content stream
- ownership phrases from one platform embedded in another
- suspicious user-generated burn-ins on otherwise premium content

```python
if "sky sports" in ocr_combined and "bein sports" in ocr_combined:
    conflict = True
    reason = "Watermark Conflict: Both Sky Sports and beIN Sports watermarks detected."
```

Conflict detection is valuable because it captures *logical inconsistency*, not only vector similarity.

## Stage 9: Similarity Fusion and Verdict Synthesis

After modality evidence is persisted, Tanmay Kumar's Orchestrator evaluates how closely the suspect content aligns with known protected media.

### Core scoring inputs

- visual similarity score
- text similarity score
- fused similarity score
- watermark conflict evidence
- transcript support signals
- metadata penalties or severity cues

### Current fusion policy

| Parameter | Value |
| --- | --- |
| `fusion_weight_visual` | `0.65` |
| `fusion_weight_text` | `0.35` |
| `piracy_threshold` | `0.85` |
| `suspicious_threshold` | `0.60` |

This weighting reflects the platform's current preference for visual evidence while giving semantic text enough influence to surface subtle conflicts.

## Stage 10: Threat Classification

The final verdict model is intentionally interpretable:

| Verdict band | Typical meaning |
| --- | --- |
| `PIRACY_DETECTED` | High-confidence overlap or severe conflict pattern |
| `SUSPICIOUS` | Materially concerning evidence below final certainty |
| `LOW_CONFIDENCE` | Weak or partial indicators worth observation |
| `CLEAN` / `SAFE` | No meaningful overlap or policy violation detected |

## Risk Penalties and Heuristics

In addition to vector similarity, rule-based penalties designed by Tanmay Kumar shape the final risk posture:

- **−80 security score penalty** for severe logical conflict such as incompatible watermarks
- **−15 penalty** for ownership burn-ins or suspicious identifier patterns
- additional contextual evidence may be surfaced to operators even when the final verdict remains below threshold

## Evidence Preserved for Operators

Typical retained evidence includes: matched asset identifier, matched timestamp, OCR excerpts, transcript segments, object detections, frame counts, node latencies, and lifecycle status flags.

## Failure Handling Philosophy

The forensic pipeline — designed by Tanmay Kumar to degrade without losing state — ensures:

- one corrupt frame does not invalidate the entire asset
- one late webhook does not silently erase a partial result
- one worker timeout surfaces as an observable degraded condition
- terminal asset states stop additional writes cleanly

## Operational Outcome

When the pipeline completes, the operator sees a **reconstructed technical narrative**: what the asset contained, which node saw what, how the evidence aligned, and why the verdict crossed or failed to cross the relevant risk thresholds.

---

*Authored by Tanmay Kumar — Principal Architect & Lead Cloud Engineer, Overwatch Platform.*