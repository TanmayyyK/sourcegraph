import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import torch
from sentence_transformers import SentenceTransformer

class TextEmbedder:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = SentenceTransformer(model_name, device=self.device)
        print(f"--- [Model] Loaded {model_name} on {self.device} ---")

    def get_vector(self, text):
        if not text.strip():
            return [0.0] * 384 # Return null vector if no text
        return self.model.encode(text).tolist()