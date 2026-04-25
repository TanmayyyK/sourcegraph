import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# faster_whisper / WhisperModel removed — audio phase disabled.
# Only OCR + MiniLM visual pipeline is active.

import gc
import torch
import numpy as np
import cv2

import easyocr
from sentence_transformers import SentenceTransformer


class ConflictDetector:
    """
    Look for broadcaster/leaker mismatches between extracted OCR watermarks.
    Audio comparison removed — OCR-only mode.
    """
    @staticmethod
    def check_conflict(ocr_list: list) -> dict:
        conflict = False
        reason   = None
        ocr_combined = " ".join(ocr_list).lower()

        # Watermark cross-contamination checks (visual only)
        if "sky sports" in ocr_combined and "bein sports" in ocr_combined:
            conflict = True
            reason   = "Watermark Conflict: Both Sky Sports and beIN Sports watermarks detected in same stream."
        elif "cinema x" in ocr_combined and "cinema y" in ocr_combined:
            conflict = True
            reason   = "Watermark Conflict: Conflicting logical locations found in OCR text."

        return {
            "has_conflict":    conflict,
            "conflict_reason": reason,
        }


class OverwatchNode:
    """
    Core hardware constraint architect for NVIDIA RTX 2050 (4 GB VRAM).
    Utilises Anti-Gravity protocol context managers to ensure memory stability.

    Audio phase removed. Visual phase (EasyOCR + MiniLM) only.
    """

    def __init__(self):
        self.ocr_list: list[str] = []

        # State tracking flag
        self.is_visual_phase_active = False

        # Lazy instances — None until prepare_visual_phase() is called
        self._easy_ocr = None
        self._minilm   = None

    # ──────────────────────────────────────────────────────────────────
    # Memory Governor
    # ──────────────────────────────────────────────────────────────────

    def _assert_memory(self):
        """
        Enforce hard GPU threshold constraint.
        RTX 2050 4 GB  →  3.5 GB safe ceiling.
        """
        if torch.cuda.is_available():
            mem_alloc = torch.cuda.memory_allocated()
            assert mem_alloc < 3.5e9, (
                f"CUDA_OUT_OF_MEMORY Prevention: currently at {mem_alloc / 1e9:.2f} GB"
            )

    # ──────────────────────────────────────────────────────────────────
    # Visual Phase Lifecycle
    # ──────────────────────────────────────────────────────────────────

    def prepare_visual_phase(self):
        """
        Load EasyOCR + MiniLM into VRAM.
        Safe to call multiple times — skips reload if already active.
        """
        if self._easy_ocr is None or self._minilm is None:
            self._assert_memory()
            print("🔍 [Overwatch Node] Loading Visual & Embedding Phase engines...")
            self._easy_ocr = easyocr.Reader(['en'], gpu=True)
            self._minilm   = SentenceTransformer('all-MiniLM-L6-v2', device='cuda')
            self.is_visual_phase_active = True
            print("✅ [Overwatch Node] Visual Phase ready.")

    def unload_visual_phase(self):
        """
        Explicit VRAM cleanup after a batch completes.
        Frees ~2–3 GB between jobs.
        """
        print("🧹 [Overwatch Node] Unloading Visual Phase engines...")
        if self._easy_ocr is not None:
            del self._easy_ocr
            self._easy_ocr = None
        if self._minilm is not None:
            del self._minilm
            self._minilm = None

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        self.is_visual_phase_active = False
        print("✅ [Overwatch Node] VRAM released.")

    # ──────────────────────────────────────────────────────────────────
    # Per-Frame Inference
    # ──────────────────────────────────────────────────────────────────

    def run_visual_phase(self, image_bytes: bytes) -> dict:
        """
        OCR + MiniLM embedding for a single frame.

        Returns
        -------
        dict with keys:
            ocr_text   : str        – joined OCR regions (empty string if none)
            vector     : list[float]– 384-D MiniLM embedding
            confidence : float      – mean EasyOCR confidence (0.0 if none)
        """
        if not self.is_visual_phase_active:
            self.prepare_visual_phase()

        nparr = np.frombuffer(image_bytes, np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # ── OCR ───────────────────────────────────────────────────────
        ocr_results = self._easy_ocr.readtext(img)   # detail=1 default

        if ocr_results:
            ocr_texts  = [res[1] for res in ocr_results]
            ocr_block  = " ".join(ocr_texts)
            self.ocr_list.extend(ocr_texts)           # accumulate for ConflictDetector
            confidence = sum(res[2] for res in ocr_results) / len(ocr_results)
        else:
            ocr_block  = ""
            confidence = 0.0

        # ── Embedding ─────────────────────────────────────────────────
        # "Empty Context" fallback keeps the vector space meaningful for
        # blank frames rather than storing a zero vector.
        embed_context  = ocr_block if ocr_block.strip() else "Empty Context"
        embedding_vec  = self._minilm.encode(embed_context, convert_to_tensor=False).tolist()

        return {
            "ocr_text":   ocr_block,
            "vector":     embedding_vec,
            "confidence": float(confidence),
        }

    # ──────────────────────────────────────────────────────────────────
    # Batch Summary
    # ──────────────────────────────────────────────────────────────────

    def generate_master_packet(self, current_ocr_output: str, packet_id: str) -> dict:
        """
        Runs ConflictDetector across all accumulated OCR for this batch
        and returns a security-scored summary packet.
        """
        detector_results = ConflictDetector.check_conflict(self.ocr_list)

        security_score = 100
        if detector_results["has_conflict"]:
            security_score -= 80

        # Burn-in / ownership watermark penalty
        if any(
            burn in current_ocr_output.lower()
            for burn in ["user_", "copyright", "property of"]
        ):
            security_score -= 15

        return {
            "packet_id":             packet_id,
            "current_frame_ocr":     current_ocr_output,
            "total_ocr_accumulated": self.ocr_list,
            "security_score":        max(0, security_score),
            "conflict_flags":        detector_results,
        }