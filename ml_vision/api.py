from fastapi import FastAPI, UploadFile, File
import uvicorn
# Rohit will import his ML functions here later
# from segmentation.cropper import crop_broadcast
# from embedding.clip_model import get_embedding

app = FastAPI(title="Vision ML Node")

@app.post("/embed/visual")
async def process_frame(image: UploadFile = File(...)):
    # 1. Read the incoming image from Yogesh
    contents = await image.read()
    
    # --- ROHIT'S ML PIPELINE WILL GO HERE ---
    # cropped_image = crop_broadcast(contents)
    # vector_512 = get_embedding(cropped_image)
    
    # Dummy response for now to prove the API works
    return {
        "status": "success",
        "visual_vector": [0.0] * 512  # Placeholder until Rohit writes the model
    }

if __name__ == "__main__":
    # 0.0.0.0 ensures it listens to the Tailscale network, not just localhost
    uvicorn.run(app, host="0.0.0.0", port=8001)