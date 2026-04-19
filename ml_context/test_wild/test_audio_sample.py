import os
import sys

# Add ml_context to path to import audio_engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from audio_engine import AudioEngine

def test_sample_audio():
    print("\n" + "="*60)
    print("🎙️ AUDIO ENGINE 'SAMPLE-SPEECH-1M.WAV' KEYWORD TEST")
    print("="*60 + "\n")

    # Define the target keywords to scan for
    keywords = ["sample", "software", "developer", "files"]
    
    # Path to the actual test asset
    test_dir = os.path.dirname(__file__)
    target_file = os.path.join(test_dir, "sample-speech-1m.wav")
    
    if not os.path.exists(target_file):
        print(f"❌ Could not find {target_file}. Please ensure the file is placed correctly.")
        return

    print("Status: Booting AudioEngine...")
    engine = AudioEngine()
    
    print(f"\nStatus: Transcribing '{os.path.basename(target_file)}'. Watch nvidia-smi if desired!")
    try:
        # Run standard inference payload execution
        packet = engine.transcribe(target_file)
        
        script = packet.get("full_script", "").lower()
        
        print("\n" + "-"*60)
        print("📝 EXACT EXTRACTED SCRIPT COPY:")
        print("-" * 60)
        print(packet.get("full_script", "No text detected."))
        print("-" * 60 + "\n")
        
        # Analyze the extracted payload against constraints
        found_keywords = [kw for kw in keywords if kw in script]
        
        if found_keywords:
            print(f"✅ KEYWORDS FOUND: {', '.join(found_keywords).upper()}")
        else:
            print("❌ NO MATCHING KEYWORDS FOUND IN TRANSCRIPT.")
            
    except Exception as e:
        print(f"\n⚠️ Encountered an error during processing: {e}")

if __name__ == "__main__":
    test_sample_audio()
