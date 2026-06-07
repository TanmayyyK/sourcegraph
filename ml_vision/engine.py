"""
engine.py — Visual Cortex Inference Engine
CPU-only CLIP + YOLO pipeline for Hugging Face Spaces.
"""
from __future__ import annotations

import gc
import logging
import os
from pathlib import Path
from typing import Any

# Hugging Face Spaces runs the container as UID 1000. Keep every model/config
# cache in writable storage and hide accelerators before importing torch.
_CACHE_ROOT = Path(os.environ.setdefault("ML_VISION_CACHE_DIR", "/tmp/cache"))
_CACHE_ENV = {
    "HF_HOME": _CACHE_ROOT / "huggingface",
    "HF_HUB_CACHE": _CACHE_ROOT / "huggingface" / "hub",
    "TRANSFORMERS_CACHE": _CACHE_ROOT / "huggingface" / "transformers",
    "TORCH_HOME": _CACHE_ROOT / "torch",
    "XDG_CACHE_HOME": _CACHE_ROOT / "xdg",
    "YOLO_CONFIG_DIR": _CACHE_ROOT / "ultralytics",
    "MPLCONFIGDIR": _CACHE_ROOT / "matplotlib",
}
for _name, _path in _CACHE_ENV.items():
    os.environ.setdefault(_name, str(_path))
    Path(os.environ[_name]).mkdir(parents=True, exist_ok=True)

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "2")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

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
SERVICE_ROOT   = Path(__file__).resolve().parent
HF_CACHE_DIR   = Path(os.environ["HF_HOME"])
YOLO_FALLBACK  = "yolov8n.pt"
YOLO_LOCAL_CANDIDATES = (
    SERVICE_ROOT / "models" / "yolo8vn.pt",
    SERVICE_ROOT / "models" / "yolov8n.pt",
)
EMBED_DIM      = 512   # CLIP ViT-B/32 visual output dimension
TOP_K_OBJECTS  = 3     # Maximum YOLO detections to surface
YOLO_CONF_THR  = 0.20  # Low threshold — we always want something if present
MAX_IMAGE_SIDE = 1024  # Downsample extreme resolutions before inference


def _configure_torch_cpu_runtime() -> None:
    """Constrain PyTorch CPU work to the small 2-vCPU Spaces tier."""
    num_threads = max(1, int(os.environ.get("VISION_TORCH_THREADS", "2")))
    interop_threads = max(1, int(os.environ.get("VISION_TORCH_INTEROP_THREADS", "1")))

    torch.set_num_threads(num_threads)
    try:
        torch.set_num_interop_threads(interop_threads)
    except RuntimeError:
        # PyTorch raises if interop threads were already configured by an import.
        logger.debug("PyTorch interop thread count was already configured.")


def _resolve_yolo_weights() -> str:
    """
    Prefer a usable local YOLO file, otherwise fall back to Ultralytics'
    managed yolov8n.pt download/cache path.
    """
    candidates: list[Path] = []
    if os.environ.get("YOLO_WEIGHTS_PATH"):
        candidates.append(Path(os.environ["YOLO_WEIGHTS_PATH"]).expanduser())
    candidates.extend(YOLO_LOCAL_CANDIDATES)

    for path in candidates:
        if path.is_file():
            if path.stat().st_size > 0:
                logger.info("Using local YOLO weights: %s", path)
                return str(path)
            logger.warning("Ignoring empty YOLO weights file: %s", path)

    logger.warning(
        "No usable local YOLO weights found under %s; falling back to %s "
        "download/cache via Ultralytics.",
        SERVICE_ROOT / "models",
        YOLO_FALLBACK,
    )
    return YOLO_FALLBACK


# ─────────────────────────────────────────────────────────────────────────────
# Image pre-processing
# ─────────────────────────────────────────────────────────────────────────────

def _safe_to_rgb(image: Image.Image) -> Image.Image:
    """
    Convert *image* to plain RGB, handling palette / transparency / CMYK modes.
    Extreme resolutions are down-sampled to ``MAX_IMAGE_SIDE`` on the longest
    side using LANCZOS resampling to keep CPU inference latency bounded.
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
        _configure_torch_cpu_runtime()
        self.device = torch.device("cpu")
        logger.info("VisionEngine target device: %s", self.device)

        # ── CLIP ViT-B/32 (fp32 CPU) ───────────────────────────────────────
        logger.info("Loading CLIP model [%s] …", CLIP_MODEL_ID)
        self._clip_processor: CLIPProcessor = CLIPProcessor.from_pretrained(
            CLIP_MODEL_ID,
            cache_dir=str(HF_CACHE_DIR),
        )
        self._clip_model: CLIPModel = CLIPModel.from_pretrained(
            CLIP_MODEL_ID,
            cache_dir=str(HF_CACHE_DIR),
            torch_dtype=torch.float32,
        ).to(self.device)
        self._clip_model.eval()
        logger.info("CLIP loaded on %s (fp32).", self.device)

        # ── YOLOv8-nano ───────────────────────────────────────────────────
        self._yolo: YOLO | None = None
        yolo_weights = _resolve_yolo_weights()
        logger.info("Loading YOLOv8n [%s] …", yolo_weights)
        try:
            self._yolo = YOLO(yolo_weights)
            self._yolo.to(self.device)
            logger.info("YOLOv8n loaded on %s.", self.device)
        except Exception:
            logger.exception(
                "YOLOv8n failed to load from %s. Service will stay up and "
                "return empty object detections until weights are fixed.",
                yolo_weights,
            )

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
        * CPU/model failure → zero-vector is returned so the server stays alive.
        * Any other exception → logged, zero-vector returned.

        The zero-vector convention signals "embedding unavailable" to the
        Orchestrator, which can choose to discard or flag the packet.
        """
        try:
            inputs = self._clip_processor(images=image, return_tensors="pt")
            pixel_values: torch.Tensor = inputs["pixel_values"].to(
                dtype=torch.float32, device=self.device
            )

            # Vision encoder only — no text branch needed
            vision_out = self._clip_model.vision_model(pixel_values=pixel_values)

            # visual_projection maps the CLS pooled output → 512-D embedding
            pooled: torch.Tensor = self._clip_model.visual_projection(
                vision_out.pooler_output
            )  # [1, 512] fp32

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

        except Exception:
            logger.exception("CLIP embedding failed — returning zero-vector fallback.")
            gc.collect()
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
        * CPU/model failure → empty detections returned.
        * Any other exception → logged, empty detections returned.
        """
        if self._yolo is None:
            return {"detected_objects": []}

        try:
            results = self._yolo.predict(
                source=image,
                device="cpu",
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

        except Exception:
            logger.exception("YOLO detection failed — returning empty detections.")
            gc.collect()
            return {"detected_objects": []}
