# M4 Orchestrator: The Lead Part of the System (Tanmay)

The **M4 Orchestrator Asset Intelligence Network** is a highly distributed, multimodal forensic pipeline designed to perform real-time visual and audio analysis on ingested media files. Its primary goal is to detect piracy, deepfakes, and supply-chain anomalies (such as broadcaster cross-contamination) before assets are published.

## The Microservice Architecture

The system is built around strict contracts between distributed nodes, coordinated by the **M4 Orchestrator (Lead: Tanmay)**. 

1. **M2 Extractor Node (Yogesh)**
   - Responsible for ingesting the media (`video_url` + `packet_id`).
   - Uses `FFmpeg` to extract 1-FPS JPEG frames, optionally utilizing Apple Silicon VideoToolbox acceleration.
   - Extracts a `16kHz mono WAV` audio track for transcription.
   - Manages a thread-safe `BatchTracker` to guarantee accurate packet processing.

2. **Vision Node (Rohit)**
   - Receives individual frames and performs visual signature extraction (e.g., object detection, Deepfake artifacts).
   - Hosts the **Ghost Node**, an ephemeral microservice running the Whisper engine to transcribe the audio track.

3. **Context Node (Yug)**
   - Runs the `ContextNode` on strict hardware constraints (e.g., NVIDIA RTX 2050 4GB VRAM limit).
   - Extracts text from frames using `EasyOCR`.
   - Generates semantic embeddings using `SentenceTransformers` (`all-MiniLM-L6-v2`).
   - Dynamically loads and unloads models from VRAM using the "Anti-Gravity Protocol" to prevent `CUDA_OUT_OF_MEMORY` crashes.

## Hardware Constraints & Safety

A major feature of the M4 Orchestrator system is its ability to run parallel ML models on low-VRAM edge devices. 
- The VRAM memory governor ensures allocations never exceed the 3.5GB ceiling.
- Whisper transcription is strictly sequenced to run *only after* GPU visual nodes have confirmed they are idle, preventing `CLIP/YOLO` and `Whisper` from colliding in VRAM.
