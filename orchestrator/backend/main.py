from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os

app = FastAPI(title="SourceGraph Host (M4)")

# Allow the frontend to talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        "database": "Ready"
    }

@app.post("/ingest")
async def ingest(payload: ExtractionPayload):
    # This is where Rohit/Yug/Yogesh will send data later
    print(f"📥 Received data for {payload.video_name} at {payload.timestamp}")
    return {"status": "success", "received": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)