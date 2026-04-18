from fastapi import FastAPI, BackgroundTasks
import uvicorn
import requests
import os

# Yogesh will import his FFmpeg logic here later
# from pipelines.demuxer import split_video
# from audio_math.constellation import generate_audio_hash

app = FastAPI(title="Extractor Node")

# These will be updated with the team's actual Tailscale IPs
ROHIT_IP = "http://100.x.x.x:8001/embed/visual"
YUG_IP = "http://100.y.y.y:8002/embed/text"
TANMAY_IP = "http://100.69.253.89:8000/ingest"

@app.post("/extract")
async def start_extraction(video_url: str, background_tasks: BackgroundTasks):
    # In a real run, Tanmay sends the location of the video file.
    # Yogesh kicks off the heavy FFmpeg processing in the background
    # so he doesn't block the API request.
    
    # background_tasks.add_task(process_pipeline, video_url)
    
    return {"status": "extraction_started", "message": "M2 is demuxing video..."}

if __name__ == "__main__":
    # 0.0.0.0 ensures it listens to the Tailscale network
    uvicorn.run(app, host="0.0.0.0", port=8003)