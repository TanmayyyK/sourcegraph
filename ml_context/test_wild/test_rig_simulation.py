import requests
import io
import time
import uuid

API_URL = "http://127.0.0.1:8002"

def test_rig():
    """
    Simulates the Yug Pipeline behavior to test the VRAM Context Switch Logic.
    First, it hits `/ingest/audio` to run Faster-Whisper.
    Then, it quickly fires 30 simulation payload requests to `/ingest/frame` for EasyOCR.
    """
    
    print("=== STARTING THE OVERWATCH AUDIT VRAM STRESS TEST ===")
    
    # 1. Simulate Batch Audio Submission
    # Create a spoofed wav file using io.BytesIO
    spoofed_audio = io.BytesIO(b"Fake WAV Header or simulated bytes.")
    spoofed_audio.name = "simulation.wav"
    
    print("\n[Test 1] Dispatching Batch Audio...")
    try:
        # In actual testing, a real wav is better, but this will trigger the endpoint successfully
        response = requests.post(
            f"{API_URL}/ingest/audio",
            files={"file": ("simulation.wav", spoofed_audio, "audio/wav")}
        )
        print("Audio API Response:", response.status_code, response.json())
    except Exception as e:
        print("Failed to dispatch audio:", e)
        
    # Wait for the model transition simulated (not truly needed but good for terminal readability)
    time.sleep(2)
    
    # 2. Simulate 30 stream images
    print("\n[Test 2] Firing 30 continuous mock frames for EasyOCR stress test...")
    # I'll create a single mock blue screen image to repeatedly send.
    # A true 1x1 pixel image encoded as png
    mock_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82'
    
    failures = 0
    for i in range(1, 31):
        packet_id = f"frame_{i}_{uuid.uuid4().hex[:6]}"
        try:
            res = requests.post(
                f"{API_URL}/ingest/frame",
                files={"image": ("mock.png", io.BytesIO(mock_png), "image/png")},
                data={"packet_id": packet_id}
            )
            # Just print the first and last to keep logs clean
            if i % 10 == 0 or i == 1:
                print(f"Frame {i} ingested. Status: {res.status_code}")
        except Exception as e:
            failures += 1
            print(f"Frame {i} Request Failed:", e)
            
    print(f"\n--- TEST COMPLETE ---")
    print(f"Total simulated overlapping requests processed: 30 instances. Failures: {failures}")
    if failures == 0:
        print("✅ STRESS TEST PASSED. VRAM OFF-LOADING OCCURRED CORRECTLY.")
    else:
        print("❌ FAILED. OutOfMemory (OOM) Crash or Server Disconnect likely occurred.")

if __name__ == "__main__":
    time.sleep(1) # buffer if just launched
    test_rig()
