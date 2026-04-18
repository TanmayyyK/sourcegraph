from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Vision ML Node (Rohit)")

# --- CORS SETUP: This allows Tanmay's Frontend to read the data ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all IPs (Tailscale safe)
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, etc.
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    """Simple endpoint for Tanmay's frontend to ping"""
    return {"status": "online", "node": "Rohit-RTX3050", "gpu": "Detected"}

@app.post("/embed/visual")
async def process_frame(image: UploadFile = File(...)):
    # 1. Read the incoming image from Yogesh
    contents = await image.read()
    
    # --- ROHIT'S ML PIPELINE WILL GO HERE ---
    # Dummy processing simulation
    print(f"📸 Received frame for processing on RTX 3050")
    
    return {
        "status": "success",
        "node": "Rohit-Vision",
        "visual_vector": [0.0] * 512 
    }

if __name__ == "__main__":
    # 0.0.0.0 is required to listen over Tailscale
    uvicorn.run(app, host="0.0.0.0", port=8001)