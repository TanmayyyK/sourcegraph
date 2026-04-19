import os
# Component Safety Fix: Prevent DLL collisions that might crash the driver
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import sys
import time
import torch

# Add ml_context to path to import ocr
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ocr.text_extractor import TextExtractor

def check_gpu_safety():
    """ Verify CUDA is active to prevent CPU fallback and ensure structural limits. """
    if not torch.cuda.is_available():
        print("❌ CRITICAL ERROR: PyTorch cannot find the CUDA GPU! It is falling back to CPU.")
        print("Please ensure you installed the CUDA version of PyTorch: pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
        sys.exit(1)
        
    device = torch.cuda.get_device_name(0)
    print(f"✅ GPU DETECTED: {device}. Safe to proceed with Hardware Acceleration.")

def run_tests():
    check_gpu_safety()
    
    # Initialize TextExtractor with explicit GPU flag
    extractor = TextExtractor(use_gpu=True)
    
    test_dir = os.path.dirname(__file__)
    images = [f for f in os.listdir(test_dir) if f.endswith(('.webp', '.jpg', '.png'))]
    
    keywords = ["modi", "kohli", "virat", "ronaldo", "bellingham", "messi", "cr7", "flyemirates", "neymar", "twitter"]
    
    print("\n" + "="*50)
    print("OCR WILD MEME TESTING - [GPU ACCELERATED]")
    print("="*50 + "\n")
    
    for count, img in enumerate(images):
        img_path = os.path.join(test_dir, img)
        print(f"🖼️ [{count+1}/{len(images)}] Testing image: {img}")
        
        try:
            # Memory Governor logic to keep components safe during loops
            if torch.cuda.is_available():
                 torch.cuda.empty_cache()
            
            extracted_text, conf = extractor.extract(img_path)
            extracted_text_lower = extracted_text.lower()
            
            found_words = [kw for kw in keywords if kw in extracted_text_lower]
            
            print(f"   => Extracted Text: {extracted_text}")
            if found_words:
                print(f"   ✅ FOUND KEYWORDS: {', '.join(found_words)}")
            else:
                print(f"   ❌ MATCHING KEYWORDS NOT FOUND")
        except Exception as e:
            print(f"   ⚠️ Error during extraction: {e}")
            
        print("-" * 50)
        
        # Hardware Safety constraint: Cool town the RTX 2050 briefly to prevent thermal throttling
        time.sleep(0.5)

if __name__ == "__main__":
    run_tests()
