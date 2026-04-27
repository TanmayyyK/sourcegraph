# Forensic Pipeline & Threat Intelligence

The M4 Orchestrator multimodal pipeline executes a precise sequence of operations to determine an asset's threat risk. 

## 1. Frame Extraction
The Extractor Node downloads the asset and runs a blocking `FFmpeg` extraction at `1 FPS`, scaling images to `224x224` px (Quality `qscale:v=2`). It immediately begins broadcasting these frames to the GPU nodes.

## 2. Distributed Inference
For each frame, the **Context Node** activates the Visual Phase:
- **Optical Character Recognition (OCR):** `EasyOCR` extracts on-screen text.
- **Semantic Embeddings:** The text is encoded into a `384-D` vector via `MiniLM`.
- **Watermark Extraction:** Accumulates text over the duration of the video.

## 3. Audio Phase (Contract v1.1)
Because audio processing is memory-intensive, it runs sequentially:
1. `FFmpeg` extracts a `16 kHz mono WAV` file.
2. The Extractor waits until the Vision and Context nodes report an `idle` health status.
3. The WAV file is dispatched to the **Ghost Node** (`VISION_AUDIO_URL`) for Whisper transcription.

## 4. Conflict Detection
At the end of the batch, the `generate_master_packet` method runs the `ConflictDetector`.
It analyzes the accumulated OCR list for cross-contamination.

```python
# Example: Identifying stolen broadcasts
if "sky sports" in ocr_combined and "bein sports" in ocr_combined:
    conflict = True
    reason = "Watermark Conflict: Both Sky Sports and beIN Sports watermarks detected."
```

### Risk Scoring
Assets begin with a baseline security score of `100`.
- **-80 penalty**: If a logical conflict (like conflicting broadcaster watermarks) is detected.
- **-15 penalty**: If ownership burn-ins (e.g., "user_", "copyright") are found.

Scores below `30` flag the asset as **Piracy / Threat Detected**.
