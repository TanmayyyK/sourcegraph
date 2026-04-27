# Vision Node

The **Vision Node** (managed by Rohit) is dedicated entirely to visual embedding generation and object detection. It strictly adheres to the SourceGraph Distributed Worker Contract v1.0.

## Hardware & Models

- **Hardware Target**: Engineered for an `NVIDIA RTX 3050`.
- **Primary Model**: `CLIP fp16` which generates dense `512-D` L2-normalized vectors.
- **Secondary Model**: `YOLOv8n` runs in parallel to extract explicit bounding boxes and classes for named objects inside the frame.

## The Ghost Node (Audio Phase)

Because ML models compete for VRAM, the Vision Node utilizes a specialized ephemeral service known as the **Ghost Node**.
- Once the pipeline completes visual extraction and all GPUs report an `idle` state, the Vision Node receives the `16 kHz WAV` track from the Extractor.
- It dynamically loads the `Whisper` model into VRAM.
- Once transcription is complete, it triggers a `hard_unload` to scrub the VRAM, ensuring a pristine environment for the next visual batch.

## Error Prevention

The node actively prevents `CUDA_OUT_OF_MEMORY` or corrupt frame crashes by passing a "zero-vector passthrough guard." If an image is totally corrupt or crashes the engine, it returns an empty vector, preventing poison data from polluting the Orchestrator's `pgvector` database.
