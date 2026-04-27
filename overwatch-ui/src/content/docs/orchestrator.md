# M4 Orchestrator Node

The **M4 Orchestrator** is the Central Intelligence Backend (v3.0.0) of the SourceGraph network. It serves as the primary coordinator, database manager, and UI gateway for all forensic operations.

## Architecture & Responsibilities

- **Framework**: Built on FastAPI with a PostgreSQL database equipped with `pgvector`.
- **Primary Function**: It manages the lifecycle of ingested assets (both "Golden Source" protected media and "Auditor" scraped media).
- **Asynchronous Syncing**: Due to the distributed nature of the worker nodes, visual (CLIP) vectors and text (MiniLM) vectors often arrive out of sync. The Orchestrator handles asynchronous dual-vector upserts seamlessly.

## Webhook Buffer Service

The Orchestrator implements a sophisticated Webhook Buffer Service:
- **Temporal Slop**: Accounts for `±2s` of drift between nodes.
- **TTL & Max Size**: Ensures memory safety by clearing stale packets.

## Fusion & Threat Detection

Once both vectors for a frame are aggregated, the Orchestrator calculates a **Fusion Score** by comparing the frame against the known "Golden Source" database.
- Uses dynamic weighting: `fusion_weight_visual` and `fusion_weight_text`.
- If the score crosses the `piracy_threshold` or `suspicious_threshold`, the asset is immediately flagged on the Command Centre.
