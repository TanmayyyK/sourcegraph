import os
import gc
import traceback
import torch

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# --- HARDWARE SAFETY BINDING FOR WINDOWS CTRANSLATE2 / FASTER-WHISPER ---
if os.name == "nt":
    try:
        import torch as _torch
        _torch_lib = os.path.join(os.path.dirname(_torch.__file__), "lib")
        if os.path.exists(_torch_lib):
            os.add_dll_directory(_torch_lib)
            os.environ["PATH"] = _torch_lib + os.pathsep + os.environ.get("PATH", "")

        import site
        for sp in site.getsitepackages():
            for subpath in [
                os.path.join(sp, "nvidia", "cublas", "bin"),
                os.path.join(sp, "nvidia", "cudnn", "bin"),
                os.path.join(sp, "nvidia", "cublas", "lib"),
                os.path.join(sp, "nvidia", "cudnn", "lib"),
            ]:
                if os.path.exists(subpath):
                    os.add_dll_directory(subpath)
                    os.environ["PATH"] = subpath + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass
# -------------------------------------------------------------------------

from faster_whisper import WhisperModel


_CUDA_ERROR_KEYWORDS = ("cublas", "cannot be loaded", "cudnn", "cuda")

# ── Inference parameters ──────────────────────────────────────────────────────
# These are the core settings that determine whether you get real transcriptions
# or silent/empty results.
_INFERENCE_KWARGS = dict(
    beam_size=5,

    # ✅ FIX 1 — VAD filter: skips truly silent regions so Whisper focuses
    # only on frames that actually contain speech. Without this, the model
    # either returns nothing or hallucinates filler tokens that get stripped.
    vad_filter=True,
    vad_parameters=dict(
        min_silence_duration_ms=500,   # merge gaps shorter than 500 ms
        speech_pad_ms=400,             # pad each speech chunk by 400 ms
        threshold=0.35,                # lower = more sensitive (catches quiet speech)
    ),

    # ✅ FIX 2 — Disable conditioning on previous text. Without this, the model
    # can enter hallucination loops on noisy or low-bitrate audio, producing
    # repeated tokens that get collapsed to whitespace and stripped.
    condition_on_previous_text=False,

    # ✅ FIX 3 — Temperature fallback. Whisper retries with increasing
    # randomness when it's uncertain, instead of giving up and returning blank.
    temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],

    # ✅ FIX 4 — Compression ratio and log-prob thresholds guard against
    # hallucinated repetition (e.g. "..." or the same word looped forever).
    compression_ratio_threshold=2.4,
    log_prob_threshold=-1.0,

    # ✅ FIX 5 — No-speech threshold. Segments below this probability are
    # treated as silence. Lowering it catches quiet or accented speech that
    # the default (0.6) would discard.
    no_speech_threshold=0.45,
)


def _is_cuda_error(e: Exception) -> bool:
    return any(kw in str(e).lower() for kw in _CUDA_ERROR_KEYWORDS)


class AudioEngineError(RuntimeError):
    """
    Raised when AudioEngine encounters a non-recoverable failure.
    Callers that want a guaranteed safe return should catch this
    and call _generate_empty_golden_packet() themselves, OR pass
    safe_mode=True to transcribe().
    """


class AudioEngine:
    """
    Ephemeral Whisper transcription engine.

    Lifecycle contract
    ------------------
    Instantiate once per job, destroy immediately after. Never store alongside
    VisionEngine (CLIP/YOLO) to avoid VRAM collisions.

    Recommended pattern:

        engine = AudioEngine(device_override="cpu")
        with engine:
            result = await asyncio.to_thread(engine.transcribe, file_path)

    transcribe() hard_unloads in its own finally block.
    The context manager is a redundant idempotent safety net.

    safe_mode parameter
    -------------------
    transcribe(path, safe_mode=True)  → always returns a golden packet (old behaviour)
    transcribe(path, safe_mode=False) → raises AudioEngineError on failure (new default)

    Use safe_mode=True only when the caller truly cannot handle exceptions
    (e.g., a fire-and-forget background queue). Prefer safe_mode=False so
    failures surface and can be logged/retried properly.

    model_size parameter
    --------------------
    "tiny", "base", "small" (default), "medium", "large-v3"
    Bump to "medium" or "large-v3" for accented/quiet/noisy audio.
    """

    def __init__(self, model_size: str = "small", device_override: str = None):
        self.model: WhisperModel | None = None
        self.model_size   = model_size
        
        if device_override:
            self.device = device_override
            self.compute_type = "int8" if device_override == "cpu" else "int8_float16"
        else:
            self.device       = "cuda" if torch.cuda.is_available() else "cpu"
            self.compute_type = "int8_float16" if self.device == "cuda" else "int8"

    # ── Context manager ───────────────────────────────────────────────────────
    def __enter__(self) -> "AudioEngine":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.hard_unload()
        return False

    def __del__(self):
        try:
            if self.model is not None:
                self.hard_unload()
        except Exception:
            pass

    # ── Properties ────────────────────────────────────────────────────────────
    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _boot_model(self):
        """
        Spin up Whisper tensors with CUDA → CPU auto-fallback.
        Raises AudioEngineError on unrecoverable failure.
        """
        if self.model is not None:
            return  # Already loaded; nothing to do.

        print(f"🎙️  [AudioEngine] Booting Whisper '{self.model_size}' on {self.device} ({self.compute_type})...")
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        except Exception as e:
            if _is_cuda_error(e):
                print(f"⚠️  [AudioEngine] CUDA boot failure: {e}")
                print("⚠️  Falling back to CPU...")
                self._switch_to_cpu()
                try:
                    self.model = WhisperModel(
                        self.model_size,
                        device=self.device,
                        compute_type=self.compute_type,
                    )
                except Exception as cpu_e:
                    raise AudioEngineError(
                        f"CPU fallback also failed: {cpu_e}"
                    ) from cpu_e
            else:
                raise AudioEngineError(
                    f"Model boot failed (non-CUDA): {e}"
                ) from e

    def _switch_to_cpu(self):
        """Tear down any partial CUDA state and reconfigure for CPU."""
        if self.model is not None:
            del self.model
            self.model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.device       = "cpu"
        self.compute_type = "int8"

    def _run_inference(self, file_path: str) -> list:
        """
        Run faster-whisper inference and materialise the lazy generator.
        Returns a list of segment objects.
        Falls back to CPU on lazy CUDA errors; raises AudioEngineError otherwise.
        """
        try:
            segments_gen, info = self.model.transcribe(file_path, **_INFERENCE_KWARGS)
            print(
                f"🔍 [AudioEngine] Detected language '{info.language}' "
                f"(probability {info.language_probability:.2f}), "
                f"duration {info.duration:.1f}s"
            )

            # ✅ FIX 6 — Warn early if the model is very uncertain about language.
            # This often predicts a silent or non-speech file before we even
            # materialise the segments.
            if info.language_probability < 0.5:
                print(
                    f"⚠️  [AudioEngine] Low language confidence ({info.language_probability:.2f}). "
                    "Audio may be silent, non-speech, or heavily distorted."
                )

            return list(segments_gen)   # Forces the lazy generator NOW
        except Exception as e:
            if _is_cuda_error(e):
                print(f"⚠️  [AudioEngine] Lazy CUDA error during inference: {e}")
                print("⚠️  Falling back to CPU and retrying...")
                self._switch_to_cpu()
                # Re-boot on CPU then retry
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                segments_gen, _ = self.model.transcribe(file_path, **_INFERENCE_KWARGS)
                return list(segments_gen)
            raise AudioEngineError(
                f"Inference failed for '{file_path}': {e}"
            ) from e

    # ── Public API ────────────────────────────────────────────────────────────
    def hard_unload(self):
        """
        Idempotent VRAM/RAM teardown.
        Primary cleanup path is transcribe()'s own finally block.
        This is a safe no-op when called a second time.
        """
        print("🧹 [AudioEngine] hard_unload()...")
        if self.model is not None:
            del self.model
            self.model = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
            print("✅ [AudioEngine] VRAM cleared.")
        else:
            print("✅ [AudioEngine] hard_unload() — model already None (no-op).")

    def _generate_empty_golden_packet(self, asset_id: str, reason: str = "") -> dict:
        """Returns a safe, typed empty packet with an optional reason tag."""
        if reason:
            print(f"📭 [AudioEngine] Empty packet for '{asset_id}': {reason}")
        return {
            "asset_id":    asset_id,
            "transcript":  [],
            "full_script": "",
            "empty_reason": reason,
        }

    def transcribe(self, file_path: str, *, safe_mode: bool = False) -> dict:
        """
        Transcribe an audio file and return a Golden Packet dict.

        Parameters
        ----------
        file_path : str
            Absolute or relative path to the audio file.
        safe_mode : bool  (keyword-only, default False)
            False → raises AudioEngineError on failure (recommended).
            True  → swallows all errors and returns an empty golden packet.
                    Use only when the caller truly cannot handle exceptions.

        Return schema
        -------------
        {
            "asset_id":     str,
            "transcript":   list[{"start": float, "end": float, "text": str}],
            "full_script":  str,
            "empty_reason": str,   # Non-empty only on silent/failed audio
        }

        Tips if you keep getting empty results
        ---------------------------------------
        1. Bump model_size to "medium" or "large-v3" — small can miss quiet speech.
        2. Pre-process audio to 16 kHz mono WAV before passing in (ffmpeg -ar 16000 -ac 1).
        3. Check that file has actual speech with: ffprobe -i <file>.
        """
        asset_id = (
            os.path.basename(file_path).split(".")[0]
            if file_path
            else "unknown_asset"
        )

        # ── Guard: file must exist and be non-empty ───────────────────────────
        if not file_path or not os.path.isfile(file_path):
            msg = f"File does not exist or path is invalid: '{file_path}'"
            if safe_mode:
                return self._generate_empty_golden_packet(asset_id, reason=msg)
            raise AudioEngineError(msg)

        if os.path.getsize(file_path) == 0:
            msg = "File is zero bytes."
            if safe_mode:
                return self._generate_empty_golden_packet(asset_id, reason=msg)
            raise AudioEngineError(f"[{asset_id}] {msg}")

        # ✅ FIX 7 — Warn about very small files (< 1 KB) which are almost
        # always corrupt, truncated, or pure silence.
        file_size = os.path.getsize(file_path)
        if file_size < 1024:
            print(
                f"⚠️  [AudioEngine] '{asset_id}' is only {file_size} bytes — "
                "likely corrupt, truncated, or a near-silent clip."
            )

        try:
            self._boot_model()

            print(f"▶️  [AudioEngine] Transcribing '{file_path}'...")
            segments = self._run_inference(file_path)

            if not segments:
                reason = (
                    "Audio contained no speech (silent track or VAD found no speech frames). "
                    "Try a larger model or pre-process to 16 kHz mono WAV."
                )
                print(f"⚠️  [AudioEngine] {reason}")
                return self._generate_empty_golden_packet(asset_id, reason=reason)

            extracted, texts = [], []
            for seg in segments:
                text = seg.text.strip()
                if text:
                    extracted.append({
                        "start": round(seg.start, 2),
                        "end":   round(seg.end,   2),
                        "text":  text,
                    })
                    texts.append(text)

            if not extracted:
                reason = (
                    "All segments were blank after stripping whitespace. "
                    "The audio may contain only music, noise, or non-speech sounds."
                )
                return self._generate_empty_golden_packet(asset_id, reason=reason)

            print(f"✅ [AudioEngine] Transcribed {len(extracted)} segment(s) from '{asset_id}'.")
            return {
                "asset_id":     asset_id,
                "transcript":   extracted,
                "full_script":  " ".join(texts),
                "empty_reason": "",
            }

        except AudioEngineError:
            if safe_mode:
                reason = traceback.format_exc()
                print(f"🔴 [AudioEngine] Suppressed AudioEngineError (safe_mode=True):\n{reason}")
                return self._generate_empty_golden_packet(asset_id, reason=reason)
            raise

        except Exception as e:
            full_trace = traceback.format_exc()
            print(f"🔴 [AudioEngine] Unexpected error for '{asset_id}':\n{full_trace}")
            if safe_mode:
                return self._generate_empty_golden_packet(asset_id, reason=str(e))
            raise AudioEngineError(
                f"Unexpected failure transcribing '{asset_id}': {e}"
            ) from e

        finally:
            self.hard_unload()