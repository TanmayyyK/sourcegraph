from fastapi import FastAPI, UploadFile, File
import uvicorn
# Yug will import his ML functions here later
# from ocr.text_extractor import extract_text
# from embedding.text_model import get_text_embedding

app = FastAPI(title="Context ML Node")

@app.post("/embed/text")
async def process_context(image: UploadFile = File(...)):
    # 1. Read the incoming image from Yogesh
    contents = await image.read()
    
    # --- YUG'S ML PIPELINE WILL GO HERE ---
    # extracted_text = extract_text(contents)
    # if extracted_text:
    #     vector_384 = get_text_embedding(extracted_text)
    # else:
    #     vector_384 = [0.0] * 384
    
    # Dummy response for now to prove the API works
    return {
        "status": "success",
        "extracted_text": "Dummy meme text",
        "text_vector": [0.0] * 384  # MiniLM uses 384 dimensions
    }

if __name__ == "__main__":
    # 0.0.0.0 ensures it listens to the Tailscale network
    uvicorn.run(app, host="0.0.0.0", port=8002)