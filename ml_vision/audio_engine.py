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
    """
    Ephemeral Whisper transcription engine.

    Lifecycle contract (enforced by vision_main.py)
    ------------------------------------------------
    This class is designed to be instantiated ONCE per transcription job and
    destroyed immediately after. It must NEVER be stored in application global
    state alongside VisionEngine (CLIP/YOLO) to prevent VRAM collisions.

    Intended usage pattern in an async BackgroundTask:

        engine = AudioEngine()
        try:
            result = await asyncio.to_thread(engine.transcribe, file_path)
            # ... dispatch result ...
        finally:
            engine.hard_unload()   # Idempotent outer guard

    transcribe() calls hard_unload() in its own finally block — the outer
    guard in the BackgroundTask is a redundant safety net that costs nothing
    (hard_unload is idempotent when self.model is already None).

    Thread Safety
    -------------
    This class is NOT thread-safe. Each concurrent transcription job must use
    its own AudioEngine instance. The recommended pattern (one instance per
    BackgroundTask) naturally satisfies this constraint.
    """

    def __init__(self):
        self.model = None
        # VRAM Pre-Allocation Constraints
        # Guarantee < 1.8GB memory footprint dynamically
        self.model_size = "small"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "int8_float16" if self.device == "cuda" else "int8"
        
        # We don't initialize model immediately unless exclusively requested to prevent ghost VRAM overlaps.

    # ── [PATCH] Context manager protocol ─────────────────────────────────────
    # Enables safe usage with `with AudioEngine() as engine:` in future
    # call sites, guaranteeing hard_unload() even if the caller forgets.
    def __enter__(self) -> "AudioEngine":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Always hard_unload on context exit, regardless of exception."""
        self.hard_unload()
        return False  # Do not suppress exceptions

    # ── [PATCH] __del__ safety net ────────────────────────────────────────────
    # Last-resort VRAM release if the caller drops the reference without
    # calling hard_unload() (e.g., an unhandled exception in the BackgroundTask
    # before the finally block runs). __del__ is not guaranteed to fire
    # immediately — it is a best-effort backstop, NOT the primary cleanup path.
    def __del__(self):
        try:
            if self.model is not None:
                self.hard_unload()
        except Exception:
            # __del__ must never raise — silently absorb all errors
            pass

    @property
    def is_loaded(self) -> bool:
        """True if the Whisper model tensors are currently resident in memory."""
        return self.model is not None

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

        Idempotent — safe to call multiple times. If self.model is already
        None (e.g., because transcribe()'s internal finally already ran),
        this is a fast no-op with no CUDA calls.
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
        else:
            # Model was already unloaded (e.g., by transcribe()'s own finally).
            # This branch is the expected path when called from the outer
            # BackgroundTask guard in vision_main._run_audio_transcription().
            print("✅ [AudioEngine] hard_unload() called — model already None (idempotent no-op).")

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

        Blocking call — must be run via asyncio.to_thread() when called from
        an async context (e.g., vision_main._run_audio_transcription) to
        prevent event-loop starvation.

        Return schema
        -------------
        {
            "asset_id":    str,           # Filename stem (no extension)
            "transcript":  list[dict],    # [{start: float, end: float, text: str}, ...]
            "full_script": str,           # All segment texts joined by spaces
        }

        This schema is always returned — even on silent audio or errors.
        The Golden Packet guarantee means callers never need to None-check.
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
            # We strictly execute hard_unload on completion under ALL circumstances to stay within constraint.
            # [PATCH] This is the PRIMARY cleanup path. The BackgroundTask's outer finally
            # will call hard_unload() again — that second call is an expected idempotent no-op.
            self.hard_unload()