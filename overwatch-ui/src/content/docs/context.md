# Context Node

The **Context Node**, operating under the HERMES role, is the platform's OCR and semantic reasoning worker. Its purpose is to extract textual meaning from frames so the system can reason about content that may not be obvious from visual similarity alone.

## Why This Node Matters

Visual embeddings answer questions like "does this frame look similar to protected content?" The Context node answers different questions:

- what words are visible on screen?
- do those words identify a broadcaster, watermark, or owner?
- does the text sequence remain logically consistent across the asset?
- are there semantic signs of contamination, impersonation, or unauthorized redistribution?

## Runtime Profile

| Characteristic | Value |
| --- | --- |
| Node owner | Yug |
| Hardware target | `NVIDIA RTX 2050` |
| VRAM constraint | approximately `3.5 GB` working ceiling |
| OCR engine | `EasyOCR` |
| Semantic encoder | `all-MiniLM-L6-v2` |
| Output dimension | `384-D` |

## Multi-Stage Frame Processing

Every frame passes through two main operations.

### 1. OCR extraction

The OCR stage scans for:

- channel bugs and broadcast watermarks
- subtitles and captions
- creator handles
- copyright overlays
- scoreboard or lower-third text

The raw text is valuable by itself, but it is also an intermediate artifact for the semantic stage.

### 2. Semantic embedding

The OCR output is collapsed into a semantic vector using MiniLM. This creates a compressed representation of the frame's textual meaning rather than only its exact surface words.

That matters because semantic similarity can still remain useful when:

- the wording is paraphrased
- capitalization changes
- overlays shift position
- multiple OCR fragments must be interpreted together

## Empty Context Fallback

Not every frame contains text. Rather than emitting null semantics, the node uses a stable fallback string such as `"Empty Context"` when no OCR is found.

This design has two advantages:

- it preserves contract stability
- it avoids special-case handling in the Orchestrator for missing vectors

## Conflict Detector

The node accumulates OCR text across the full batch and runs a final conflict pass before completion.

### What it looks for

- mutually exclusive broadcaster identifiers
- contradictory watermark evidence
- suspicious cross-source contamination
- repeated ownership terms that imply re-upload or redistribution

### Why this matters

A conflict signal can be more actionable than a similarity score because it captures a **logical impossibility** within a single asset.

## Memory Governance

This node is intentionally designed around low-VRAM discipline.

### Anti-Gravity protocol

The implementation uses an explicit memory-governor pattern to:

- load OCR and MiniLM only when required
- clear intermediate state aggressively
- release VRAM between heavy phases
- avoid cascading `CUDA_OUT_OF_MEMORY` failures across requests

This is one of the reasons the platform is viable on hardware that would normally be considered too small for a multi-model pipeline.

## Output Contract

The Context node typically returns or contributes:

- OCR text chunks
- OCR confidence-derived metrics
- semantic `384-D` embedding vectors
- accumulated OCR evidence
- end-of-batch conflict signals

These records are then shipped to the Orchestrator through the webhook feeder contract.

## Operational Behavior

The node also emits:

- heartbeat signals for liveness
- end-of-batch text summaries
- degraded but structured behavior when upstream or downstream systems are unavailable

This keeps the control plane aware of the node even outside active ingest windows.

## Engineering Importance

Without the Context node, the platform would still have strong visual similarity. But it would lose a major part of forensic reasoning:

- watermark contradictions
- textual provenance clues
- semantic overlay reuse
- explicit ownership language

That is why HERMES is not an accessory service. It is a core evidence generator in the overall threat-intelligence stack.
