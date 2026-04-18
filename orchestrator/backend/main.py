from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import datetime

app = FastAPI(title="SourceGraph Master (M4)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temporary in-memory log to show on your Frontend dashboard
incoming_feed = []

class ExtractionPayload(BaseModel):
    video_name: str
    timestamp: float
    visual_vector: List[float]
    text_vector: Optional[List[float]] = None

@app.get("/")
def host_health():
    return {
        "status": "online",
        "machine": "Tanmay-M4",
        "role": "Orchestrator",
        "active_logs": len(incoming_feed)
    }

@app.get("/feed")
def get_feed():
    """Returns the last 10 pieces of data received from the GPUs"""
    return incoming_feed[-10:]

@app.post("/ingest")
async def ingest(payload: ExtractionPayload):
    # Log the arrival
    log_entry = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "video": payload.video_name,
        "ts": payload.timestamp,
        "has_visual": any(x != 0 for x in payload.visual_vector),
        "has_text": payload.text_vector is not None and any(x != 0 for x in payload.text_vector)
    }
    
    incoming_feed.append(log_entry)
    
    print(f"📥 [M4] Data Ingested: {payload.video_name} | Visual: {log_entry['has_visual']} | Text: {log_entry['has_text']}")
    return {"status": "success", "received": True}

if __name__ == "__main__":
    # 0.0.0.0 is crucial so Tailscale can find your M4
    uvicorn.run(app, host="0.0.0.0", port=8000)