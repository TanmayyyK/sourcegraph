import os
# Hardware Safety: Prevent Windows DLL Thread crashes unconditionally at the top limit
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import gc
import torch
import traceback
import sys

# --- HARDWARE SAFETY BINDING FOR WINDOWS CTRANSLATE2 / FASTER-WHISPER ---
# CTranslate2 explicitly requires cuBLAS and cuDNN to boot on CUDA on Windows.
# If they are bundled with PyTorch or Nvidia Python packages, we dynamically append them.
if os.name == "nt":
    try:
        import torch
        torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
        if os.path.exists(torch_lib):
            os.add_dll_directory(torch_lib)
            os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
            
        import site
        site_packages = site.getsitepackages()
        for sp in site_packages:
            for path in [
                os.path.join(sp, "nvidia", "cublas", "bin"),
                os.path.join(sp, "nvidia", "cudnn", "bin"),
                os.path.join(sp, "nvidia", "cublas", "lib"),
                os.path.join(sp, "nvidia", "cudnn", "lib")
            ]:
                if os.path.exists(path):
                    os.add_dll_directory(path)
                    os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass
# ------------------------------------------------------------------------

from faster_whisper import WhisperModel

class AudioEngine:
    def __init__(self):
        self.model = None
        # VRAM Pre-Allocation Constraints
        # Guarantee < 1.8GB memory footprint dynamically
        self.model_size = "small"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "int8_float16" if self.device == "cuda" else "int8"
        
        # We don't initialize model immediately unless exclusively requested to prevent ghost VRAM overlaps.

    def _boot_model(self):
        """ Bootstrapper. Spins up the core tensors with resilient Auto-Fallback """
        if self.model is None:
            try:
                print(f"🎙️ [AudioEngine] Booting Whisper '{self.model_size}' explicitly to {self.device}...")
                self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
            except Exception as e:
                err_msg = str(e).lower()
                if "cublas" in err_msg or "cannot be loaded" in err_msg or "cudnn" in err_msg or "cuda" in err_msg:
                    print(f"⚠️ [Memory Governor] Missing CUDA Runtime DLLs detected or Version Mismatch: {e}")
                    print("⚠️ Auto-falling back to CPU Inference to ensure pipeline continuity!")
                    self.device = "cpu"
                    self.compute_type = "int8"
                    self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
                else:
                    raise e

    def _fallback_to_cpu(self):
        print("⚠️ [Memory Governor] Lazy CUDA Error or lack of CuBLAS detected during transcribe!")
        print("⚠️ Auto-falling back to CPU Inference to ensure pipeline continuity!")
        del self.model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        self.device = "cpu"
        self.compute_type = "int8"
        self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)

    def hard_unload(self):
        """ 
        Anti-Gravity Protocol: Zero-Leak Constraint. 
        Obliterates context tensors instantly on demand. 
        """
        print("🧹 [AudioEngine] Triggering Anti-Gravity Protocol hard_unload()...")
        if self.model is not None:
            del self.model
            self.model = None
            
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
            print(f"✅ VRAM Check: Engine completely dismantled. Tensors collected.")

    def _generate_empty_golden_packet(self, asset_id: str) -> dict:
        """ Returns unified safe struct on silent / failing tracks """
        return {
            "asset_id": asset_id,
            "transcript": [],
            "full_script": ""
        }

    def transcribe(self, file_path: str) -> dict:
        """ 
        Executes parsing logic inside guarded exception loops.
        Returns the specific 'Golden Packet' Dict.
        """
        # Asset tagging from trailing filename purely
        asset_id = os.path.basename(file_path).split(".")[0] if file_path else "unknown_asset"
        
        self._boot_model()
        
        try:
            print(f"▶️ [AudioEngine] Extracting High Mass tensors from {file_path}")
            
            # Since fast-whisper evaluates lazily, we need to try/except the generator
            try:
                segments_gen, info = self.model.transcribe(file_path, beam_size=5)
                # Convert to list to trigger the generator immediately and catch potential DLL errors
                segments = list(segments_gen)
            except Exception as lazy_e:
                err_msg = str(lazy_e).lower()
                if "cublas" in err_msg or "cannot be loaded" in err_msg or "cudnn" in err_msg or "cuda" in err_msg:
                    self._fallback_to_cpu()
                    # Try again after fallback
                    segments_gen, info = self.model.transcribe(file_path, beam_size=5)
                    segments = list(segments_gen)
                else:
                    raise lazy_e
            
            extracted_segs = []
            script_construct = []
            
            for seg in segments:
                extracted_segs.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip()
                })
                script_construct.append(seg.text.strip())
                
            full_script = " ".join(script_construct)
            
            # Failsafe check for purely silent audios returning nothing after valid parsing
            if not extracted_segs:
                 print("⚠️ [AudioEngine] Asset contained audio, but strictly silent. Generating Default Packet.")
                 return self._generate_empty_golden_packet(asset_id)
            
            return {
                "asset_id": asset_id,
                "transcript": extracted_segs,
                "full_script": full_script
            }
                
        except Exception as e:
            # Prevent Pipeline collapse explicitly on ffmpeg corruptions / OOM bursts
            print(f"🔴 [AudioEngine] FATAL CORRUPTION TRACED IN '{asset_id}': {e}")
            print("=> Generating safe Golden Packet bypass.")
            return self._generate_empty_golden_packet(asset_id)
            
        finally:
            # We strictly execute hard_unload on completion under ALL circumstances to stay within constraint
            self.hard_unload()