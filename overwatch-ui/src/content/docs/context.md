# Context Node

The **Context Node** (managed by Yug) is responsible for extracting explicit logical context from frames via text analysis.

## Hardware & Constraints

- **Hardware Target**: Strictly constrained for low-memory edge devices like the `NVIDIA RTX 2050 (4 GB VRAM)`.
- **Memory Governor**: Enforces a hard `3.5 GB` allocation ceiling. It utilizes the "Anti-Gravity Protocol" context managers to aggressively clear `gc` and `torch.cuda.empty_cache()` between batches.

## Multi-Stage Visual Phase

When a frame is received, the Context Node executes two specialized operations:

1. **Optical Character Recognition (OCR)**
   - Leverages `EasyOCR` (GPU-accelerated) to scan the frame for on-screen text.
   - Ideal for finding broadcaster watermarks, subtitles, or burn-in ownership tags.

2. **Semantic Embedding**
   - The combined text is fed into `SentenceTransformers` (`all-MiniLM-L6-v2`).
   - Produces a dense `384-D` vector that perfectly captures the "semantic meaning" of the frame's text.

## Conflict Detection

The node tracks the accumulated text across the entire video. The `ConflictDetector` actively looks for logical mismatches (e.g., seeing both "Sky Sports" and "beIN Sports" in the same broadcast), returning severe security penalties in the final payload back to the Orchestrator.
