# M2 Extractor Node

The **M2 Extractor Node** (managed by Yogesh) is the entry point for all media entering the M4 Orchestrator pipeline. It is responsible for parsing video streams and executing the heavy lifting of frame and audio extraction.

## Core Operations

1. **Video Download**: Safely streams video from source URLs or CDN links directly to local storage.
2. **Visual Frame Extraction**: 
   - Utilizes `FFmpeg` to extract JPEG frames at exactly `1 FPS`.
   - Hard-scaled to `224x224 px` with `qscale:v=2` compression to normalize data before it hits the GPU models.
   - Attempts Apple Silicon `VideoToolbox` hardware acceleration natively before falling back to software decoding.
3. **Audio Extraction**:
   - Extracts a `16 kHz mono PCM WAV` file optimized for Whisper transcription.
   
## Distributed Handshake

The Extractor is responsible for pushing the data to the downstream inference nodes.
- Frames are broadcast concurrently to both the **Vision Node** and the **Context Node**.
- Uses an asynchronous HTTP client pool and implements strict retry strategies (Exponential Backoff, handling `409 Conflict` abort signals).
- Manages a thread-safe `BatchTracker` to keep a precise count of successful frame broadcasts.
