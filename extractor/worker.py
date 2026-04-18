from fastapi import FastAPI, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
import os
import time
import shutil

app = FastAPI(title="Extractor Node (Yogesh)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Team Endpoints
ROHIT_URL = "http://100.119.250.125:8001/embed/visual"
YUG_URL = "http://100.115.89.72:8002/embed/text"

@app.get("/")
async def health_check():
    return {"status": "online", "node": "Yogesh-M2", "hardware": "Apple Silicon"}

async def process_media_pipeline(file_path: str):
    """Handles the saved file and propagates to GPUs"""
    print(f"🎬 [M2] Starting pipeline for: {file_path}")
    
    # 1. Simulate FFmpeg extraction delay
    time.sleep(2) 
    
    # 2. For this simulation, we use a fixed 'test_frame.jpg' 
    # In the real version, FFmpeg would generate this from the saved file_path
    image_to_send = "test_frame.jpg" 
    
    if not os.path.exists(image_to_send):
        print(f"❌ Error: {image_to_send} not found on M2. Please place a JPG in the folder.")
        return

    # 3. Propagate to GPUs
    try:
        with open(image_to_send, "rb") as img_file:
            # We wrap the file in a dict for the POST request
            files = {"image": (image_to_send, img_file, "image/jpeg")}
            
            print(f"🚀 [M2] Broadcasting to Rohit (3050)...")
            requests.post(ROHIT_URL, files=files)
            
            img_file.seek(0) # Reset for the next request
            
            print(f"🚀 [M2] Broadcasting to Yug (2050)...")
            requests.post(YUG_URL, files=files)
            
        print(f"✅ [M2] Successfully forwarded data derived from {file_path}")
    except Exception as e:
        print(f"🚨 [M2] Propagation Error: {e}")

@app.post("/extract")
async def start_extraction(background_tasks: BackgroundTasks, video: UploadFile = File(...)):
    # 1. Save the file received from Tanmay's Dashboard
    local_filename = f"received_{video.filename}"
    
    # This physically saves the file in Yogesh's folder so he can see it
    with open(local_filename, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
        
    print(f"📥 [M2] Received and saved: {local_filename}")
    
    # 2. Kick off the background GPU propagation
    background_tasks.add_task(process_media_pipeline, local_filename)
    
    return {
        "status": "file_received", 
        "saved_as": local_filename,
        "message": "Propagation to GPUs started in background."
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)