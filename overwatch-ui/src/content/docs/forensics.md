# Forensic Pipeline and Threat Intelligence

This document describes the runtime sequence used to transform a raw media asset into a scored forensic record. The goal of the pipeline is not only to detect a likely violation, but also to preserve **why** the system reached that conclusion.

## Processing Contract

Every ingest is treated as a bounded forensic transaction keyed by a packet-level identifier. The pipeline maintains temporal, structural, and semantic alignment across three modalities:

- **visual frames**
- **text evidence derived from OCR**
- **audio transcript evidence**

Those streams do not always arrive in lockstep, so the Orchestrator is designed to reconcile them after the fact rather than assuming strict synchronous delivery.

## Stage 1: Intake and Asset Registration

The ingest lifecycle begins when a producer or auditor submits an asset reference. At this point, the system captures:

- asset identity
- source type
- whether the asset is a golden reference or a suspect input
- an end-to-end `trace_id`
- packet-level correlation metadata for all downstream nodes

This is the point at which the control plane becomes the authoritative owner of state, while worker nodes remain evidence producers.

## Stage 2: Frame and Audio Extraction

The Extractor node performs the first irreversible normalization step.

### Visual normalization

- `FFmpeg` extracts frames at exactly `1 FPS`
- frames are scaled to `224x224`
- JPEG quality is normalized with `qscale:v=2`
- hardware acceleration is attempted when the host supports it

### Audio normalization

- audio is extracted to `16 kHz`
- output is mono WAV
- silent or audio-less assets degrade gracefully instead of failing the full ingest

This normalization step is intentionally conservative: downstream models should receive stable, comparable inputs rather than source-specific encoding noise.

## Stage 3: Parallel Inference Fan-Out

Each extracted frame is dispatched concurrently to two GPU services:

| Target | Purpose | Output |
| --- | --- | --- |
| Vision Node | visual similarity + detection | `512-D` CLIP vector, object detections |
| Context Node | OCR + text semantics | `384-D` MiniLM vector, OCR evidence |

The Extractor does not wait for one node before dispatching to the other. This preserves throughput while allowing each node to optimize for its own model stack.

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

The OCR output is condensed into a semantic representation through `SentenceTransformers` with `all-MiniLM-L6-v2`.

This gives the system a second, text-derived signal that can catch issues visual embeddings alone may miss, such as:

- broadcaster name inconsistencies
- reused lower-third overlays
- subtitle sequence reuse
- text-only ownership leaks

## Stage 5: Visual Feature Extraction

The Vision node emits two forms of visual evidence:

1. **CLIP embedding**
   - `512-D`
   - L2-normalized
   - designed for nearest-neighbor comparison against protected assets

2. **YOLO detections**
   - top-K object detections
   - spatially localized objects
   - useful for explainability, not only score generation

These detections help operators understand whether a match came from actual content overlap, repeated framing, or a contextual visual cue.

## Stage 6: Asynchronous Reconciliation in the Orchestrator

The Orchestrator is responsible for joining partial evidence from independent workers.

This is a non-trivial step because:

- visual vectors may arrive before text vectors
- one modality may fail while the other succeeds
- webhook delivery may drift by small amounts under load

To solve this, the backend uses:

- `packet_id`
- frame timestamps
- bounded temporal slop
- a buffer service with TTL and cleanup behavior

The resulting record is persisted even when the two modalities are not perfectly synchronized at first arrival time.

## Stage 7: Audio Phase and Whisper Sequencing

Audio work is intentionally delayed until the visual phase is safe to drain.

The sequence is:

1. Extractor completes frame fan-out.
2. Extractor waits for Vision and Context nodes to report an idle condition.
3. The WAV file is posted to the Vision-hosted Ghost audio endpoint.
4. Whisper transcribes the clip and returns structured transcript evidence.

This is primarily a **VRAM protection strategy**. Running CLIP, YOLO, OCR, MiniLM, and Whisper at the same time would create unnecessary collision risk on the current deployment profile.

## Stage 8: Conflict Detection

The Context node accumulates OCR evidence across the entire batch. At finalization time, the `ConflictDetector` searches for incompatible evidence combinations.

Example categories:

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

After modality evidence is persisted, the Orchestrator evaluates how closely the suspect content aligns with known protected media.

### Core scoring inputs

- visual similarity score
- text similarity score
- fused similarity score
- watermark conflict evidence
- transcript support signals
- metadata penalties or severity cues

### Current fusion policy

The active backend configuration uses:

- `fusion_weight_visual = 0.65`
- `fusion_weight_text = 0.35`
- `piracy_threshold = 0.85`
- `suspicious_threshold = 0.60`

This weighting reflects the platform's current preference for visual evidence while still giving semantic text enough influence to surface subtle conflicts.

## Stage 10: Threat Classification

The final verdict model is intentionally interpretable.

| Verdict band | Typical meaning |
| --- | --- |
| `PIRACY_DETECTED` | high-confidence overlap or severe conflict pattern |
| `SUSPICIOUS` | materially concerning evidence but below final certainty |
| `LOW_CONFIDENCE` | weak or partial indicators worth observation |
| `CLEAN` / `SAFE` | no meaningful overlap or policy violation detected |

## Risk Penalties and Heuristics

In addition to vector similarity, rule-based penalties shape the final risk posture.

- **-80 security score penalty** for severe logical conflict, such as incompatible watermarks
- **-15 penalty** for ownership burn-ins or suspicious identifier patterns
- additional contextual evidence may be surfaced to operators even if the final verdict remains below the threshold

This hybrid model is deliberate. Pure vector search is fast, but operational trust improves when rule-based logic can explain why a result escalated.

## Evidence Preserved for Operators

The pipeline aims to leave behind an actionable record, not just a label.

Typical retained evidence includes:

- matched asset identifier
- matched timestamp
- OCR excerpts
- transcript segments
- object detections
- frame counts
- node latencies
- lifecycle status flags

## Failure Handling Philosophy

The forensic pipeline is designed to degrade without losing control of state.

- one corrupt frame should not invalidate the entire asset
- one late webhook should not silently erase a partial result
- one worker timeout should surface as an observable degraded condition
- terminal asset states must stop additional writes cleanly

## Operational Outcome

When the pipeline completes, the operator sees more than a match percentage. They see a **reconstructed technical narrative**: what the asset contained, which node saw what, how the evidence aligned, and why the verdict crossed or failed to cross the relevant risk thresholds.
