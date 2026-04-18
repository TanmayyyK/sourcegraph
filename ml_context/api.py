from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests

app = FastAPI(title="Context ML Node (Yug)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Your M4 IP - where the data eventually lands
TANMAY_URL = "http://100.69.253.89:8000/ingest"

@app.get("/")
async def health_check():
    return {
        "status": "online", 
        "node": "Yug-RTX2050", 
        "task": "OCR & NLP"
    }

@app.post("/embed/text")
async def process_context(image: UploadFile = File(...)):
    # 1. Read the incoming image from Yogesh (M2)
    contents = await image.read()
    print(f"📝 [Yug-2050] Received image from M2 ({len(contents)} bytes)")
    
    # --- SIMULATED ML LOGIC ---
    # In the real hackathon, this is where MiniLM/OCR runs.
    simulated_text = "Watermark: @SourceGraph_Found"
    simulated_vector = [0.01] * 384
    
    # 2. BOUNCE BACK: Send the result to Tanmay (M4)
    payload = {
        "video_name": "simulated_video_01",
        "timestamp": 10.5,
        "visual_vector": [0.0] * 512, # Placeholder (Rohit handles this)
        "text_vector": simulated_vector
    }

    try:
        print(f"🚀 [Yug-2050] Forwarding context vector to Tanmay (M4)...")
        requests.post(TANMAY_URL, json=payload)
    except Exception as e:
        print(f"🚨 [Yug-2050] Could not reach M4: {e}")
    
    return {
        "status": "success",
        "node": "Yug-Context",
        "sent_to_host": True
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)