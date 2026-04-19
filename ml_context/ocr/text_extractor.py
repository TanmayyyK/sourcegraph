
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import easyocr
import cv2
import numpy as np

class TextExtractor:
    def __init__(self, use_gpu: bool = True):
        # Memory Governor: Optionally disable GPU if VRAM is fully constrained
        self.reader = easyocr.Reader(['en'], gpu=use_gpu)

    def extract(self, image_path):
        # Optional: Add pre-processing here if 'wild' images are too dark
        results = self.reader.readtext(image_path)
        # Join all detected text pieces into one context string
        full_text = " ".join([res[1] for res in results])
        avg_conf = sum([res[2] for res in results]) / len(results) if results else 0
        return full_text, avg_conf

    def extract_from_image_bytes(self, image_bytes: bytes) -> str:
        """
        Takes raw image bytes from the stream, decodes them via OpenCV, and extracts text.
        """
        # Decode image securely for OpenCV
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Extract text (using detail=0 to directly return list of strings for speed)
        results = self.reader.readtext(img, detail=0)
        ocr_text = " ".join(results).lower()
        
        return ocr_text