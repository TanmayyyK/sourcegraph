from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests

app = FastAPI(title="Vision ML Node (Rohit)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Your M4 Host IP
TANMAY_URL = "http://100.69.253.89:8000/ingest"

@app.get("/")
async def health_check():
    return {
        "status": "online", 
        "node": "Rohit-RTX3050", 
        "gpu": "Active",
        "model": "CLIP-ViT-B/32"
    }

@app.post("/embed/visual")
async def process_frame(image: UploadFile = File(...)):
    # 1. Read the binary image data from Yogesh (M2)
    contents = await image.read()
    print(f"📸 [Rohit-3050] Received image from M2 ({len(contents)} bytes)")
    
    # --- SIMULATED ML LOGIC ---
    # This is where his YOLO and CLIP models will eventually sit
    simulated_vector = [0.05] * 512
    
    # 2. BOUNCE BACK: Send the result to Tanmay (M4)
    payload = {
        "video_name": "simulated_video_01",
        "timestamp": 10.5,
        "visual_vector": simulated_vector,
        "text_vector": [0.0] * 384 # Placeholder (Yug handles this)
    }

    try:
        print(f"🚀 [Rohit-3050] Forwarding visual vector to Tanmay (M4)...")
        requests.post(TANMAY_URL, json=payload)
    except Exception as e:
        print(f"🚨 [Rohit-3050] Failed to reach M4: {e}")
    
    return {
        "status": "success",
        "node": "Rohit-Vision",
        "sent_to_host": True
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)