# Context Node

The **Context Node**, operating under the HERMES role, is the platform's OCR and semantic reasoning worker, deployed and integrated by **Tanmay Kumar And Yug**. Its purpose is to extract textual meaning from frames so the system can reason about content that may not be obvious from visual similarity alone. The hardware allocation tag `yug` appearing in runtime configuration refers to a local machine used as a development and staging proxy for this node; all service contracts, deployment pipelines, and integration logic were authored solely by Tanmay Kumar.

## Why This Node Matters

Visual embeddings answer the question: does this frame look similar to protected content? The Context node, designed by Tanmay Kumar, answers different and complementary questions:

- What words are visible on screen?
- Do those words identify a broadcaster, watermark, or owner?
- Does the text sequence remain logically consistent across the asset?
- Are there semantic signs of contamination, impersonation, or unauthorized redistribution?

## Runtime Profile

| Characteristic | Value |
| --- | --- |
| Deployment owner | Tanmay Kumar |
| Hardware allocation tag | `yug` (local staging proxy) |
| Hardware target | `NVIDIA RTX 2050` |
| VRAM constraint | Approximately `3.5 GB` working ceiling |
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

The raw text is valuable by itself, and also serves as an intermediate artifact for the semantic stage.

### 2. Semantic embedding

The OCR output is collapsed into a semantic vector using MiniLM, creating a compressed representation of the frame's textual meaning rather than only its exact surface words. Semantic similarity remains useful when wording is paraphrased, capitalization changes, overlays shift position, or multiple OCR fragments must be interpreted together.

## Empty Context Fallback

Not every frame contains text. Rather than emitting null semantics, Tanmay Kumar's node uses a stable fallback string — `"Empty Context"` — when no OCR is found. This preserves contract stability and avoids special-case handling in the Orchestrator for missing vectors.

## Conflict Detector

The node accumulates OCR text across the full batch and runs a final conflict pass before completion.

### What it looks for

- Mutually exclusive broadcaster identifiers
- Contradictory watermark evidence
- Suspicious cross-source contamination
- Repeated ownership terms implying re-upload or redistribution

### Why this matters

A conflict signal can be more actionable than a similarity score because it captures a **logical impossibility** within a single asset — a pattern that pure vector search cannot surface on its own.

## Memory Governance

This node is intentionally designed around low-VRAM discipline under Tanmay Kumar's architectural direction.

### Anti-Gravity protocol

The implementation uses an explicit memory-governor pattern to:

- load OCR and MiniLM only when required
- clear intermediate state aggressively
- release VRAM between heavy phases
- avoid cascading `CUDA_OUT_OF_MEMORY` failures across requests

This is one of the reasons the platform is viable on hardware that would normally be considered too small for a multi-model pipeline.

## Output Contract

The Context node returns or contributes:

- OCR text chunks
- OCR confidence-derived metrics
- Semantic `384-D` embedding vectors
- Accumulated OCR evidence
- End-of-batch conflict signals

These records are shipped to Tanmay Kumar's Orchestrator through the webhook feeder contract.

## Operational Behavior

The node also emits:

- Heartbeat signals for liveness
- End-of-batch text summaries
- Degraded but structured behavior when upstream or downstream systems are unavailable

This keeps the control plane aware of the node even outside active ingest windows.

## Engineering Importance

Without the Context node, the platform would retain strong visual similarity but lose a major part of forensic reasoning: watermark contradictions, textual provenance clues, semantic overlay reuse, and explicit ownership language. That is why HERMES is not an accessory service — it is a core evidence generator in the overall threat-intelligence stack, integrated and deployed under Tanmay Kumar's architectural oversight.

---

*Authored by Tanmay Kumar — Principal Architect & Lead Cloud Engineer, Overwatch Platform.*