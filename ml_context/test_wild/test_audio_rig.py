import os
import sys
import time
import wave
import json

# Add parent path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from audio_engine import AudioEngine

def create_dummy_wav(path: str, duration_sec: int = 2):
    """ Synthesizes a rapid empty valid WAV file for High Mass engine testing. """
    with wave.open(path, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        # Write flat zeroes representing pure silence natively
        wav.writeframes(b'\x00' * (16000 * duration_sec * 2))
    return path

def create_corrupted_file(path: str):
    """ Creates a purely corrupted random text file masked as an AV asset """
    with open(path, "wb") as f:
        f.write(os.urandom(1024))
    return path

def run_rigorous_audio_tests():
    print("\n" + "="*60)
    print("🚀 THE 'PRE-FLIGHT' AUDIO RIGOROUS TEST SUITE (PHASE 2)")
    print("="*60 + "\n")
    
    engine = AudioEngine()
    test_dir = os.path.dirname(__file__)
    
    # --- TEST 1 & 2 DUAL SIMULATION ---
    print("\n[TEST 1] The 'Clean Release' & 'Handshake' Payload Test")
    print("Action: Synthesizing a valid AV file and booting Whisper (Watch nvidia-smi window locally!)")
    
    valid_path = os.path.join(test_dir, "synthetic_test_valid.wav")
    create_dummy_wav(valid_path, duration_sec=5)
    
    # Pause artificially to let User read 600MB idle load cleanly
    print("⏳ Idle state hold (3 seconds)...")
    time.sleep(3)
    
    packet = engine.transcribe(valid_path)
    
    # Handshake Validation
    assert isinstance(packet, dict), "❌ Payload is not a Dictionary!"
    assert "full_script" in packet, "❌ Missing required Golden Packet key: 'full_script'"
    assert "asset_id" in packet, "❌ Missing required Golden Packet key: 'asset_id'"
    assert isinstance(packet["segments"], list), "❌ Sequences are incorrectly formatted!"
    
    print("\n✅ [Pass] Handshake Packet Verified! Golden Structure extracted successfully:")
    print(json.dumps(packet, indent=2))
    
    # Idle cooldown for Clean Release monitor
    print("\n⏳ [Monitor VRAM] The engine has fired hard_unload(). Check nvidia-smi now.")
    print("VRAM should drop back to base idle levels instantly within the next 5 seconds.")
    time.sleep(5)
    print("VRAM Drop window elapsed.\n")
    
    # --- TEST 3 NO-AUDIO CRASH VALIDATION ---
    print("\n[TEST 3] The 'No-Audio / Corruption' Crash Test")
    print("Action: Injecting a maliciously corrupted mock TikTok file into the pipeline.")
    
    corrupt_path = os.path.join(test_dir, "malicious_corrupt.wav")
    create_corrupted_file(corrupt_path)
    
    packet_corrupt = engine.transcribe(corrupt_path)
    
    assert packet_corrupt["full_script"] == '', "❌ Corrupt script did not evaluate to empty default string."
    assert len(packet_corrupt["segments"]) == 0, "❌ Corrupt segment array populated falsely."
    print("✅ [Pass] Engine trapped ffmpeg parsing corruption natively. Golden Default Object returned instead of Traceback!")
    
    # Cleanup
    os.remove(valid_path)
    os.remove(corrupt_path)
    print("\n=== ALL AUDIO RIG TESTS PASSED ===")

if __name__ == "__main__":
    run_rigorous_audio_tests()
