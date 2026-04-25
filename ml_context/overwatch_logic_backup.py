import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import gc
import torch
import numpy as np
import cv2
from contextlib import contextmanager

from faster_whisper import WhisperModel
import easyocr
from sentence_transformers import SentenceTransformer

class ConflictDetector:
    """
    Look for broadcaster/leaker mismatches between the extracted Audio context
    and the OCR watermarks found sequentially.
    """
    @staticmethod
    def check_conflict(ocr_list: list, audio_transcript: str) -> dict:
        conflict = False
        reason = None
        ocr_combined = " ".join(ocr_list).lower()
        audio_transcript = audio_transcript.lower()
        
        # Mismatches (Ex: Ghost Audio attack)
        if "sky sports" in audio_transcript and "bein sports" in ocr_combined:
            conflict = True
            reason = "Ghost Audio Match: Broadcaster watermark contradicts spoken audio context."
        elif "bein sports" in audio_transcript and "sky sports" in ocr_combined:
            conflict = True
            reason = "Ghost Audio Match: Broadcaster watermark contradicts spoken audio context."
        elif "cinema x" in audio_transcript and "cinema y" in ocr_combined:
            conflict = True
            reason = "Ghost Match: Conflicting logical locations found between Audio and Text."
            
        return {
            "has_conflict": conflict,
            "conflict_reason": reason
        }


class OverwatchNode:
    """
    Core hardware constraint architect for NVIDIA RTX 2050 (4GB VRAM).
    Utilizes Anti-Gravity protocol context managers to ensure memory stability.
    """
    def __init__(self):
        # We hold state locally on the instance, but models remain None out-of-context
        self.audio_state_transcript = ""
        self.audio_segments = []
        self.ocr_list = []
        # State tracking flags
        self.is_visual_phase_active = False
        
        # Cached lazy instances during visual phase
        self._easy_ocr = None
        self._minilm = None

    def _assert_memory(self):
        """
        Enforce Hard GPU threshold constraint. (4GB max -> 3.5e9 safe ceiling)
        """
        if torch.cuda.is_available():
            mem_alloc = torch.cuda.memory_allocated()
            assert mem_alloc < 3.5e9, f"CUDA_OUT_OF_MEMORY Prevention: Currently at {mem_alloc/1e9:.2f}GB"

    @contextmanager
    def _audio_engine_context(self):
        """ Context manager that exclusively loads and aggressively deletes faster-whisper """
        self._assert_memory()
        print("🎙️ [Overwatch Node] Booting Audio Phase. Loading faster-whisper (Base, int8)")
        try:
            model = WhisperModel("base", device="cuda", compute_type="int8")
            yield model
        finally:
            print("🧹 [Overwatch Node] Unloading Audio Phase engines... cleaning VRAM")
            del model
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def run_audio_phase(self, wav_path: str):
        """
        High Mass execution. Parses complete AV track and explicitly dismounts context when complete.
        """
        with self._audio_engine_context() as whisper:
            segments, _ = whisper.transcribe(wav_path, beam_size=5)
            full_text = ""
            for seg in segments:
                self.audio_segments.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text.strip()
                })
                full_text += seg.text.strip() + " "
                
            self.audio_state_transcript = full_text
            
        return self.audio_state_transcript

    def prepare_visual_phase(self):
        """
        Low Mass Initialization. Once Audio is verified clear, loads visual components.
        We hold these in memory for the streaming duration of images.
        """
        if self._easy_ocr is None or self._minilm is None:
            self._assert_memory()
            print("🔍 [Overwatch Node] Loading Visual & Embedding Phase engines...")
            self._easy_ocr = easyocr.Reader(['en'], gpu=True)
            # Utilizing mini-lm for embedding context
            self._minilm = SentenceTransformer('all-MiniLM-L6-v2', device='cuda')
            self.is_visual_phase_active = True

    def unload_visual_phase(self):
        """ Explicit cleanup if we complete a video lifecycle completely """
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

    def run_visual_phase(self, image_bytes: bytes) -> dict:
        """
        Extracts OCR continuously across streamed images, generating vector embedding metrics
        so both components share the lightweight visual envelope payload.
        """
        if not self.is_visual_phase_active:
            self.prepare_visual_phase()
            
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # 1. OCR Extraction (getting full details for confidence calculation)
        ocr_results = self._easy_ocr.readtext(img)
        
        if ocr_results:
            ocr_texts = [res[1] for res in ocr_results]
            ocr_block = " ".join(ocr_texts)
            self.ocr_list.extend(ocr_texts) # Track in bulk list
            confidence = sum(res[2] for res in ocr_results) / len(ocr_results)
        else:
            ocr_block = ""
            confidence = 0.0
        
        # 2. Embedding creation (as an example of unified processing)
        # If no OCR was found, we just vector embed "Empty Context" as fallback context
        embed_context = ocr_block if ocr_block.strip() else "Empty Context"
        embedding_vec = self._minilm.encode(embed_context, convert_to_tensor=False).tolist()

        return {
            "ocr_text": ocr_block,
            "vector": embedding_vec,
            "confidence": float(confidence)
        }

    def generate_master_packet(self, current_ocr_output: str, packet_id: str) -> dict:
        """
        Creates the Master Packet unified final payload structure 
        comparing holistic audio states vs current extracted visual logic.
        """
        # Run independent Detector class matching
        detector_results = ConflictDetector.check_conflict(self.ocr_list, self.audio_state_transcript)
        
        # Standard pseudo security score logic natively
        security_score = 100
        if detector_results["has_conflict"]:
            security_score -= 80  # high penalty
            
        # Add basic burn-in penalty
        if any(burn in current_ocr_output.lower() for burn in ["user_", "copyright", "property of"]):
            security_score -= 15

        return {
            "packet_id": packet_id,
            "audio_transcript": self.audio_state_transcript,
            "current_frame_ocr": current_ocr_output,
            "total_ocr_accumulated": self.ocr_list,
            "security_score": max(0, security_score),
            "conflict_flags": detector_results
        }