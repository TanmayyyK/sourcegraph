from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
import os

app = FastAPI(title="Extractor Node (Yogesh)")

# --- CORS SETUP: Allows your M4 Dashboard to ping the M2 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Update these with the team's actual Tailscale IPs as you get them
ROHIT_URL = "http://100.119.250.125:8001/embed/visual"
YUG_URL = "http://100.115.89.72:8002/embed/text"
TANMAY_URL = "http://100.69.253.89:8000/ingest"

@app.get("/")
async def health_check():
    """Status check for Tanmay's Dashboard"""
    return {
        "status": "online",
        "node": "Yogesh-M2",
        "task": "FFmpeg Demuxing & Audio Hashing",
        "hardware": "Apple Silicon M2"
    }

@app.post("/extract")
async def start_extraction(video_url: str, background_tasks: BackgroundTasks):
    # This runs in the background so the API stays responsive
    print(f"🎬 M2 starting background processing for: {video_url}")
    
    # background_tasks.add_task(your_processing_function, video_url)
    
    return {
        "status": "extraction_started", 
        "message": "M2 is demuxing video in background..."
    }

if __name__ == "__main__":
    # Listen on port 8003 for Tailscale traffic
    uvicorn.run(app, host="0.0.0.0", port=8003)