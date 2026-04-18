from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Context ML Node (Yug)")

# --- CORS SETUP: Essential for Tanmay's Dashboard ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    """Endpoint for the M4 Dashboard to verify connectivity"""
    return {
        "status": "online", 
        "node": "Yug-RTX2050", 
        "task": "OCR & NLP",
        "model": "MiniLM-L6-v2"
    }

@app.post("/embed/text")
async def process_context(image: UploadFile = File(...)):
    # 1. Read the incoming image
    contents = await image.read()
    
    # --- YUG'S ML PIPELINE WILL GO HERE ---
    print(f"📝 Received frame for OCR/Text embedding on RTX 2050")
    
    return {
        "status": "success",
        "node": "Yug-Context",
        "extracted_text": "Sample text from frame",
        "text_vector": [0.0] * 384
    }

if __name__ == "__main__":
    # Listen on port 8002 for Tailscale traffic
    uvicorn.run(app, host="0.0.0.0", port=8002)