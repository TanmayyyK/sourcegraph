"""
engine.py — Visual Cortex Inference Engine
RTX 3050 VRAM-optimized CLIP + YOLO pipeline.

Memory budget (RTX 3050 4 GB VRAM):
    CLIP  ViT-B/32  fp16  ≈  290 MB
    YOLOv8n         fp32  ≈    6 MB
    ─────────────────────────────────
    Total (rough)         ≈  300 MB  — well within the 4 GB budget
"""
from __future__ import annotations

import gc
import logging
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageOps
from transformers import CLIPModel, CLIPProcessor
from ultralytics import YOLO

logger = logging.getLogger("vision.engine")

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
CLIP_MODEL_ID  = "openai/clip-vit-base-patch32"
YOLO_WEIGHTS   = "yolov8n.pt"
EMBED_DIM      = 512   # CLIP ViT-B/32 visual output dimension
TOP_K_OBJECTS  = 3     # Maximum YOLO detections to surface
YOLO_CONF_THR  = 0.20  # Low threshold — we always want something if present
MAX_IMAGE_SIDE = 1024  # Downsample extreme resolutions before inference


# ─────────────────────────────────────────────────────────────────────────────
# Image pre-processing
# ─────────────────────────────────────────────────────────────────────────────

def _safe_to_rgb(image: Image.Image) -> Image.Image:
    """
    Convert *image* to plain RGB, handling palette / transparency / CMYK modes.
    Extreme resolutions are down-sampled to ``MAX_IMAGE_SIDE`` on the longest
    side using LANCZOS resampling to avoid OOM on the CUDA device.
    """
    # Normalise mode (handles P, RGBA, CMYK, L, etc.)
    image = ImageOps.exif_transpose(image)          # honour EXIF orientation
    image = image.convert("RGB")

    # Guard against gigantic images
    w, h = image.size
    if max(w, h) > MAX_IMAGE_SIDE:
        scale  = MAX_IMAGE_SIDE / max(w, h)
        image  = image.resize(
            (int(w * scale), int(h * scale)),
            resample=Image.LANCZOS,
        )
        logger.debug("Image down-sampled from (%d, %d) → %s", w, h, image.size)

    return image


# ─────────────────────────────────────────────────────────────────────────────
# Singleton engine
# ─────────────────────────────────────────────────────────────────────────────

class VisionEngine:
    """
    Singleton inference engine — loaded once at startup, shared across all
    FastAPI requests via dependency injection.

    Thread-safety
    -------------
    FastAPI runs request handlers in async event-loop workers (single OS thread
    for the event loop itself).  Both ``_clip_embed`` and ``_yolo_detect`` are
    decorated with ``@torch.inference_mode()`` which disables the Autograd
    engine entirely — safe for concurrent async access in this architecture.

    For true multi-threaded access, wrap each forward pass in a
    ``threading.Lock`` or use a model-server (TorchServe / Triton).
    """

    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("VisionEngine target device: %s", self.device)

        # ── CLIP ViT-B/32 (fp16) ──────────────────────────────────────────
        logger.info("Loading CLIP model [%s] …", CLIP_MODEL_ID)
        self._clip_processor: CLIPProcessor = CLIPProcessor.from_pretrained(
            CLIP_MODEL_ID
        )
        self._clip_model: CLIPModel = CLIPModel.from_pretrained(
            CLIP_MODEL_ID,
            torch_dtype=torch.float16,  # Half-precision → halves VRAM footprint
        ).to(self.device)
        self._clip_model.eval()
        logger.info("CLIP loaded on %s (fp16).", self.device)

        # ── YOLOv8-nano ───────────────────────────────────────────────────
        logger.info("Loading YOLOv8n [%s] …", YOLO_WEIGHTS)
        self._yolo: YOLO = YOLO(YOLO_WEIGHTS)
        self._yolo.to(self.device)
        logger.info("YOLOv8n loaded on %s.", self.device)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def embed_and_detect(
        self,
        image: Image.Image,
    ) -> tuple[list[float], dict[str, Any]]:
        """
        Run CLIP visual embedding + YOLO object detection on *image*.

        The image is sanitised (mode normalisation, resize cap) before
        inference.  Each sub-call has its own try/except so a YOLO crash
        cannot suppress the CLIP result, and vice-versa.

        Returns
        -------
        visual_vector : list[float]
            512-D L2-normalised fp32 embedding (zero-vector on failure).
        metadata : dict
            ``{"detected_objects": [{"class": str, "confidence": float}, …]}``
        """
        clean_image   = _safe_to_rgb(image)
        visual_vector = self._clip_embed(clean_image)
        metadata      = self._yolo_detect(clean_image)
        return visual_vector, metadata

    # ─────────────────────────────────────────────────────────────────────────
    # Private inference helpers
    # ─────────────────────────────────────────────────────────────────────────

    @torch.inference_mode()
    def _clip_embed(self, image: Image.Image) -> list[float]:
        """
        Extract a 512-D L2-normalised visual embedding from *image*.

        Failure modes handled
        ---------------------
        * Corrupt/empty image → zero-vector fallback.
        * CUDA OOM → VRAM is recovered via ``torch.cuda.empty_cache()``,
          then a zero-vector is returned so the server stays alive.
        * Any other exception → logged, zero-vector returned.

        The zero-vector convention signals "embedding unavailable" to the
        Orchestrator, which can choose to discard or flag the packet.
        """
        try:
            inputs = self._clip_processor(images=image, return_tensors="pt")
            pixel_values: torch.Tensor = inputs["pixel_values"].to(
                dtype=torch.float16, device=self.device
            )

            # Vision encoder only — no text branch needed
            vision_out = self._clip_model.vision_model(pixel_values=pixel_values)

            # visual_projection maps the CLS pooled output → 512-D embedding
            pooled: torch.Tensor = self._clip_model.visual_projection(
                vision_out.pooler_output
            )  # [1, 512] fp16

            # L2 normalise → unit vector (cosine-similarity compatible)
            normed: torch.Tensor = F.normalize(pooled, p=2, dim=-1)

            vector: list[float] = (
                normed.squeeze(0)            # [512]
                .to(dtype=torch.float32)     # fp32 for JSON safety
                .cpu()
                .numpy()
                .tolist()
            )

            if len(vector) != EMBED_DIM:
                raise AssertionError(
                    f"Expected {EMBED_DIM}-D vector, got {len(vector)}"
                )

            return vector

        except torch.cuda.OutOfMemoryError:
            logger.error(
                "CUDA OOM during CLIP embed — recovering VRAM, "
                "returning zero-vector fallback."
            )
            torch.cuda.empty_cache()
            gc.collect()
            return [0.0] * EMBED_DIM

        except Exception:
            logger.exception("CLIP embedding failed — returning zero-vector fallback.")
            return [0.0] * EMBED_DIM

    @torch.inference_mode()
    def _yolo_detect(self, image: Image.Image) -> dict[str, Any]:
        """
        Run YOLOv8n on *image* and return the top-K detections sorted by
        descending confidence.

        Return schema
        -------------
        ::

            {
                "detected_objects": [
                    {"class": "person",  "confidence": 0.91},
                    {"class": "bicycle", "confidence": 0.74},
                ]
            }

        Failure modes handled
        ---------------------
        * CUDA OOM → VRAM recovered, empty detections returned.
        * Any other exception → logged, empty detections returned.
        """
        try:
            results = self._yolo.predict(
                source=image,
                verbose=False,
                conf=YOLO_CONF_THR,
            )

            detections: list[dict[str, Any]] = []

            if results and results[0].boxes is not None:
                boxes = results[0].boxes
                cls_array:  np.ndarray = boxes.cls.cpu().numpy()
                conf_array: np.ndarray = boxes.conf.cpu().numpy()

                pairs: list[tuple[float, str]] = [
                    (float(conf), self._yolo.names[int(cls)])
                    for cls, conf in zip(cls_array, conf_array)
                ]

                # Sort descending by confidence, keep top-K
                pairs.sort(key=lambda x: x[0], reverse=True)

                detections = [
                    {"class": name, "confidence": round(conf, 4)}
                    for conf, name in pairs[:TOP_K_OBJECTS]
                ]

            return {"detected_objects": detections}

        except torch.cuda.OutOfMemoryError:
            logger.error(
                "CUDA OOM during YOLO detect — recovering VRAM, "
                "returning empty detections."
            )
            torch.cuda.empty_cache()
            gc.collect()
            return {"detected_objects": []}

        except Exception:
            logger.exception("YOLO detection failed — returning empty detections.")
            return {"detected_objects": []}