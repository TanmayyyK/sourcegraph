import asyncio
import uuid
import httpx
from fastapi import FastAPI, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional

"""
MOCK HARNESS - IMPERSONATING EXTRACTOR, VISION, AND CONTEXT NODES
(Auditor mock has been removed for Hybrid Testing)

Instructions for the Orchestrator .env file:
Change the following to route traffic to this mock server:
EXTRACTOR_URL="http://localhost:9000"
VISION_NODE_URL="http://localhost:9000"
CONTEXT_NODE_URL="http://localhost:9000"
"""

app = FastAPI(title="Mock GPU Worker Nodes (Hybrid Mode)")

ORCHESTRATOR_URL = "http://localhost:8000"
WEBHOOK_SECRET = "change-me-in-production"

def get_headers():
    return {
        "X-Webhook-Secret": WEBHOOK_SECRET,
        "Content-Type": "application/json"
    }

# =====================================================================
# TASK 1: Extractor Mock
# =====================================================================

async def simulate_extraction_process(asset_id: str):
    """Background task to simulate extraction and fire vectors/summary."""
    print(f"[Extractor] Starting extraction for {asset_id}. Sleeping 2s...")
    await asyncio.sleep(2)

    # Fire 3 visual and 3 text vectors
    async with httpx.AsyncClient() as client:
        for i in range(3):
            # TASK 2: Strict Dimensionality (512 for visual)
            visual_payload = {
                "packet_id": asset_id,
                "timestamp": float(i * 5),
                "visual_vector": [0.1] * 512,
                "source_node": "M2-Extractor"
            }
            try:
                res = await client.post(
                    f"{ORCHESTRATOR_URL}/api/v1/webhooks/vector",
                    json=visual_payload,
                    headers=get_headers(),
                    timeout=5.0
                )
                print(f"[Extractor] Fired visual vector ts={i*5}. Status: {res.status_code}")
            except Exception as e:
                print(f"[Extractor] Failed to fire visual vector: {e}")

            # TASK 2: Strict Dimensionality (384 for text)
            text_payload = {
                "packet_id": asset_id,
                "timestamp": float(i * 5),
                "text_vector": [0.1] * 384,
                "source_node": "M2-Extractor"
            }
            try:
                res = await client.post(
                    f"{ORCHESTRATOR_URL}/api/v1/webhooks/vector",
                    json=text_payload,
                    headers=get_headers(),
                    timeout=5.0
                )
                print(f"[Extractor] Fired text vector ts={i*5}. Status: {res.status_code}")
            except Exception as e:
                print(f"[Extractor] Failed to fire text vector: {e}")

    print(f"[Extractor] Sleeping 1s before pipeline summary...")
    await asyncio.sleep(1)

    # Fire pipeline_final_summary
    summary_payload = {
        "type": "pipeline_final_summary",
        "source_node": "M2-Extractor",
        "packet_id": asset_id,
        "metrics": {
            "total_frames_extracted": 3,
            "successful_broadcasts": 3,
            "failed_broadcasts": 0,
            "total_pipeline_time_s": 3.0
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(
                f"{ORCHESTRATOR_URL}/api/v1/webhooks/feeder",
                json=summary_payload,
                headers=get_headers(),
                timeout=5.0
            )
            print(f"[Extractor] Fired pipeline_final_summary. Status: {res.status_code}")
        except Exception as e:
            print(f"[Extractor] Failed to fire summary: {e}")


@app.post("/api/v1/extract")
@app.post("/ingest")
async def mock_extract(req: Request, background_tasks: BackgroundTasks):
    try:
        form = await req.form()
        asset_id = form.get("packet_id", form.get("asset_id", str(uuid.uuid4())))
    except Exception:
        try:
            data = await req.json()
            asset_id = data.get("packet_id", data.get("asset_id", str(uuid.uuid4())))
        except Exception:
            asset_id = str(uuid.uuid4())
            
    # Trigger both the extraction and the audio generation in the background
    background_tasks.add_task(simulate_extraction_process, str(asset_id))
    
    # Internal trigger for the audio node mock
    async def trigger_audio():
        async with httpx.AsyncClient() as client:
            try:
                await client.post("http://localhost:9000/embed/audio", json={"asset_id": str(asset_id)})
            except Exception as e:
                print(f"[Mock] Failed to trigger internal audio node: {e}")
                
    background_tasks.add_task(trigger_audio)
    
    return {"status": "processing", "asset_id": str(asset_id), "mock": True}


# =====================================================================
# TASK 2: Vision Node (Audio) Mock
# =====================================================================

@app.post("/embed/audio")
async def mock_embed_audio(req: Request):
    data = await req.json()
    asset_id = data.get("asset_id", str(uuid.uuid4()))
    
    # TASK 3: Maintain Synchronization Locks (Blocking for 4s)
    print(f"[Vision] Received audio embed request for {asset_id}. BLOCKING for 4s...")
    await asyncio.sleep(4)

    # TASK 2: Strict Dimensionality (384 for audio_vectors)
    summary_payload = {
        "type": "audio_final_summary",
        "source_node": "Vision-Node",
        "packet_id": asset_id,
        "full_script": "This is a mock audio transcript from the test harness.",
        "transcript": [
            {"start": 0.0, "end": 2.5, "text": "This is a mock"},
            {"start": 2.5, "end": 5.0, "text": "audio transcript"}
        ],
        "audio_vectors": [[0.1] * 384] # Including the requested audio vector
    }
    
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(
                f"{ORCHESTRATOR_URL}/api/v1/webhooks/feeder",
                json=summary_payload,
                headers=get_headers(),
                timeout=5.0
            )
            print(f"[Vision] Fired audio_final_summary. Status: {res.status_code}")
        except Exception as e:
            print(f"[Vision] Failed to fire audio summary: {e}")

    return {"status": "audio_processed", "mock": True}


if __name__ == "__main__":
    import uvicorn
    # Run with: python mock_harness.py
    uvicorn.run(app, host="0.0.0.0", port=9000)
