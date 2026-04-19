"""
engine.py — Visual Cortex Inference Engine
RTX 3050 VRAM-optimized CLIP + YOLO pipeline.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor
from ultralytics import YOLO

logger = logging.getLogger("vision.engine")

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
CLIP_MODEL_ID = "openai/clip-vit-base-patch32"
YOLO_WEIGHTS  = "yolov8n.pt"
EMBED_DIM     = 512          # CLIP ViT-B/32 visual output dimension
TOP_K_OBJECTS = 3            # How many YOLO detections to surface


class VisionEngine:
    """
    Singleton inference engine.  Loaded once at startup, shared across
    all FastAPI requests via dependency injection.

    Memory budget (RTX 3050 4 GB):
        CLIP  ViT-B/32  fp16  ≈  290 MB
        YOLOv8n         fp32  ≈  ~6 MB   (ultralytics handles its own device)
        ─────────────────────────────────
        Total (rough)         ≈  300 MB  ← well within 4 GB headroom
    """

    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("VisionEngine target device: %s", self.device)

        # ── CLIP (fp16) ────────────────────────────────────────────────────
        logger.info("Loading CLIP model [%s] …", CLIP_MODEL_ID)
        self._clip_processor: CLIPProcessor = CLIPProcessor.from_pretrained(
            CLIP_MODEL_ID
        )
        self._clip_model: CLIPModel = CLIPModel.from_pretrained(
            CLIP_MODEL_ID,
            torch_dtype=torch.float16,   # Half-precision → halves VRAM footprint
        ).to(self.device)
        self._clip_model.eval()
        logger.info("CLIP loaded on %s in fp16.", self.device)

        # ── YOLOv8-nano ────────────────────────────────────────────────────
        logger.info("Loading YOLOv8n …")
        self._yolo: YOLO = YOLO(YOLO_WEIGHTS)
        # Move YOLO's underlying torch model to the same device so both models
        # share the same CUDA context and avoid PCIe round-trips.
        self._yolo.to(self.device)
        logger.info("YOLOv8n loaded on %s.", self.device)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def embed_and_detect(self, image: Image.Image) -> tuple[list[float], dict[str, Any]]:
        """
        Run CLIP visual embedding + YOLO object detection on *image*.

        Returns
        -------
        visual_vector : list[float]  — 512-D L2-normalised fp32 vector
        metadata      : dict         — top-K YOLO detections with confidence
        """
        visual_vector = self._clip_embed(image)
        metadata      = self._yolo_detect(image)
        return visual_vector, metadata

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    @torch.inference_mode()  # Stronger than no_grad: disables Autograd entirely
    def _clip_embed(self, image: Image.Image) -> list[float]:
        """
        Extract a 512-D L2-normalised visual embedding from *image*.

        Falls back to a 512-D zero vector if the image is corrupt or if a
        CUDA/model error occurs — the server must never crash on bad input.
        """
        try:
            # Pre-process: returns pixel_values as fp32 tensors on CPU
            inputs = self._clip_processor(
                images=image,
                return_tensors="pt",
            )
            # Cast to fp16 and move to the model's device in a single call
            pixel_values: torch.Tensor = inputs["pixel_values"].to(
                dtype=torch.float16, device=self.device
            )

            # Forward pass through the vision encoder only (no text branch needed)
            vision_outputs = self._clip_model.vision_model(
                pixel_values=pixel_values
            )
            # pooler_output: [1, 512]  — CLS-token pooled representation
            pooled: torch.Tensor = self._clip_model.visual_projection(
                vision_outputs.pooler_output
            )  # shape: [1, 512], dtype: float16

            # L2 normalise → cosine-similarity compatible unit vector
            normed: torch.Tensor = torch.nn.functional.normalize(
                pooled, p=2, dim=-1
            )  # [1, 512]

            # Detach, move to CPU, cast to fp32, flatten → plain Python list
            vector: list[float] = (
                normed.squeeze(0)          # [512]
                .to(dtype=torch.float32)   # fp32 for JSON serialisation safety
                .cpu()
                .numpy()
                .tolist()
            )

            assert len(vector) == EMBED_DIM, (
                f"Expected {EMBED_DIM}-D vector, got {len(vector)}"
            )
            return vector

        except Exception:
            logger.exception(
                "CLIP embedding failed — returning zero-vector fallback."
            )
            return [0.0] * EMBED_DIM

    @torch.inference_mode()
    def _yolo_detect(self, image: Image.Image) -> dict[str, Any]:
        """
        Run YOLOv8n on *image* and return the top-K detections.

        Return schema
        -------------
        {
            "detected_objects": [
                {"class": "person",  "confidence": 0.91},
                {"class": "bicycle", "confidence": 0.74},
                ...
            ]
        }
        """
        try:
            # ultralytics accepts PIL images directly
            results = self._yolo.predict(
                source=image,
                verbose=False,
                conf=0.20,    # Low threshold so we always surface something
            )

            detections: list[dict[str, Any]] = []
            if results and results[0].boxes is not None:
                boxes = results[0].boxes

                # Build (confidence, class_name) pairs
                pairs: list[tuple[float, str]] = []
                for cls_idx, conf in zip(
                    boxes.cls.cpu().numpy(), boxes.conf.cpu().numpy()
                ):
                    class_name: str = self._yolo.names[int(cls_idx)]
                    pairs.append((float(conf), class_name))

                # Sort descending by confidence, take top-K
                pairs.sort(key=lambda x: x[0], reverse=True)
                for conf, name in pairs[:TOP_K_OBJECTS]:
                    detections.append({"class": name, "confidence": round(conf, 4)})

            return {"detected_objects": detections}

        except Exception:
            logger.exception("YOLO detection failed — returning empty metadata.")
            return {"detected_objects": []}