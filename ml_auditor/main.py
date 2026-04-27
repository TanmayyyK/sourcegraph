"""
ml_auditor/main.py — Enterprise-Grade Similarity & Piracy Detection Engine
Version: 2.0.0

Upgrades over v1.0.0:
  • Task 1 — Persistent FAISS indices (startup load / post-index flush)
  • Task 2 — DTW sequence alignment for time-warp-robust video matching
  • Task 3 — Audio vector modality (Whisper/MiniLM, 384-D) + 3-way fusion
  • Task 4 — Statistically sound RBF-kernel L2 → similarity mapping
"""

# ──────────────────────────────────────────────────────────────────────────────
# Standard library
# ──────────────────────────────────────────────────────────────────────────────
import math
import os
import pickle
import warnings
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Third-party
# ──────────────────────────────────────────────────────────────────────────────
import faiss
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# fastdtw is preferred (O(N) approximate DTW).  If not installed, the engine
# falls back to a fully-vectorised exact DTW written in NumPy.
try:
    from fastdtw import fastdtw  # pip install fastdtw
    from scipy.spatial.distance import euclidean

    _FASTDTW_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTDTW_AVAILABLE = False
    warnings.warn(
        "fastdtw not found — falling back to vectorised exact DTW. "
        "Install with:  pip install fastdtw scipy",
        stacklevel=1,
    )

# ──────────────────────────────────────────────────────────────────────────────
# Application
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="ML Auditor - Similarity & Piracy Engine", version="2.0.0")

# ──────────────────────────────────────────────────────────────────────────────
# Dimensionality constants
# ──────────────────────────────────────────────────────────────────────────────
VISUAL_DIM: int = 512   # CLIP ViT-B/32
TEXT_DIM:   int = 384   # MiniLM-L6-v2  (OCR embeddings)
AUDIO_DIM:  int = 384   # MiniLM-L6-v2  (Whisper transcript embeddings)

# ──────────────────────────────────────────────────────────────────────────────
# Fusion weights  (must sum to 1.0)
# ──────────────────────────────────────────────────────────────────────────────
_W_VISUAL: float = 0.60
_W_AUDIO:  float = 0.30
_W_TEXT:   float = 0.10

# ──────────────────────────────────────────────────────────────────────────────
# Persistence paths
# ──────────────────────────────────────────────────────────────────────────────
_DATA_DIR = "./data"

_PATHS: Dict[str, str] = {
    "idx_visual":   os.path.join(_DATA_DIR, "index_visual.faiss"),
    "idx_text":     os.path.join(_DATA_DIR, "index_text.faiss"),
    "idx_audio":    os.path.join(_DATA_DIR, "index_audio.faiss"),
    "meta_visual":  os.path.join(_DATA_DIR, "meta_visual.pkl"),
    "meta_text":    os.path.join(_DATA_DIR, "meta_text.pkl"),
    "meta_audio":   os.path.join(_DATA_DIR, "meta_audio.pkl"),
    "seq_visual":   os.path.join(_DATA_DIR, "seq_visual.pkl"),
    "seq_text":     os.path.join(_DATA_DIR, "seq_text.pkl"),
    "seq_audio":    os.path.join(_DATA_DIR, "seq_audio.pkl"),
}

# ──────────────────────────────────────────────────────────────────────────────
# Global mutable state  (populated by _load_state on startup)
# ──────────────────────────────────────────────────────────────────────────────

# FAISS flat-L2 indices
index_visual: faiss.IndexFlatL2
index_text:   faiss.IndexFlatL2
index_audio:  faiss.IndexFlatL2

# Flat reverse-maps:  faiss_row_id → asset_id
visual_metadata: Dict[int, str] = {}
text_metadata:   Dict[int, str] = {}
audio_metadata:  Dict[int, str] = {}

# Sequence stores for DTW:  asset_id → ordered list of np.ndarray vectors
# Each list preserves the temporal order in which frames were indexed.
visual_sequences: Dict[str, List[np.ndarray]] = defaultdict(list)
text_sequences:   Dict[str, List[np.ndarray]] = defaultdict(list)
audio_sequences:  Dict[str, List[np.ndarray]] = defaultdict(list)

# Running counters (= index.ntotal; kept separately so they survive reload)
visual_count: int = 0
text_count:   int = 0
audio_count:  int = 0


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic schemas  — backward-compatible with v1 Orchestrator
# ──────────────────────────────────────────────────────────────────────────────
class VectorPayload(BaseModel):
    asset_id: str
    visual_vectors: List[List[float]] = []   # (N, 512)
    text_vectors:   List[List[float]] = []   # (N, 384)  — OCR / MiniLM
    audio_vectors:  List[List[float]] = []   # (N, 384)  — Whisper / MiniLM  ← NEW


class SearchResult(BaseModel):
    verdict:      str
    visual_score: float
    text_score:   float
    audio_score:  float   # ← NEW
    fused_score:  float


# ──────────────────────────────────────────────────────────────────────────────
# Task 1 — Persistence helpers
# ──────────────────────────────────────────────────────────────────────────────
def _ensure_data_dir() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)


def _save_state() -> None:
    """Flush all indices and metadata to disk atomically-ish."""
    _ensure_data_dir()

    faiss.write_index(index_visual, _PATHS["idx_visual"])
    faiss.write_index(index_text,   _PATHS["idx_text"])
    faiss.write_index(index_audio,  _PATHS["idx_audio"])

    for key, obj in (
        ("meta_visual", (visual_metadata, visual_count)),
        ("meta_text",   (text_metadata,   text_count)),
        ("meta_audio",  (audio_metadata,  audio_count)),
        ("seq_visual",  dict(visual_sequences)),
        ("seq_text",    dict(text_sequences)),
        ("seq_audio",   dict(audio_sequences)),
    ):
        with open(_PATHS[key], "wb") as fh:
            pickle.dump(obj, fh, protocol=pickle.HIGHEST_PROTOCOL)


def _load_state() -> None:
    """
    Load persisted indices and metadata from disk.
    Creates fresh in-memory structures when no snapshot exists.
    """
    global index_visual, index_text, index_audio
    global visual_metadata, text_metadata, audio_metadata
    global visual_count, text_count, audio_count
    global visual_sequences, text_sequences, audio_sequences

    _ensure_data_dir()

    # ── FAISS indices ────────────────────────────────────────────────────────
    def _load_or_create_index(path: str, dim: int) -> faiss.IndexFlatL2:
        if os.path.exists(path):
            idx = faiss.read_index(path)
            print(f"  [persistence] Loaded index from {path}  ({idx.ntotal} vectors)")
            return idx
        print(f"  [persistence] No snapshot found at {path} — creating fresh index")
        return faiss.IndexFlatL2(dim)

    index_visual = _load_or_create_index(_PATHS["idx_visual"], VISUAL_DIM)
    index_text   = _load_or_create_index(_PATHS["idx_text"],   TEXT_DIM)
    index_audio  = _load_or_create_index(_PATHS["idx_audio"],  AUDIO_DIM)

    # ── Flat metadata ────────────────────────────────────────────────────────
    def _load_meta(path: str) -> Tuple[Dict, int]:
        if os.path.exists(path):
            with open(path, "rb") as fh:
                return pickle.load(fh)
        return {}, 0

    visual_metadata, visual_count = _load_meta(_PATHS["meta_visual"])
    text_metadata,   text_count   = _load_meta(_PATHS["meta_text"])
    audio_metadata,  audio_count  = _load_meta(_PATHS["meta_audio"])

    # ── Sequence stores ──────────────────────────────────────────────────────
    def _load_sequences(path: str) -> Dict[str, List[np.ndarray]]:
        if os.path.exists(path):
            with open(path, "rb") as fh:
                return defaultdict(list, pickle.load(fh))
        return defaultdict(list)

    visual_sequences = _load_sequences(_PATHS["seq_visual"])
    text_sequences   = _load_sequences(_PATHS["seq_text"])
    audio_sequences  = _load_sequences(_PATHS["seq_audio"])


# ──────────────────────────────────────────────────────────────────────────────
# Task 4 — Statistical distance → similarity mapping
# ──────────────────────────────────────────────────────────────────────────────
def _l2_to_similarity(distances_1d: np.ndarray) -> float:
    """
    Convert a 1-D array of raw L2 distances (one per query vector) into a
    single [0 … 100] similarity percentage using an RBF (Gaussian) kernel:

        sim(d) = exp( −d² / (2·σ²) )

    Theoretical basis
    ─────────────────
    For two random unit vectors in ℝ^d, the expected squared L2 distance is
    E[‖a − b‖²] = 2 (derived from E[cos θ] = 0 for orthogonal random vectors).
    We therefore set σ² = 2 so that:

        L2² = 0  →  sim = exp(0)  = 1.00   (identical vectors)
        L2² = 2  →  sim = exp(−1) ≈ 0.368  (random / orthogonal)
        L2² = 4  →  sim = exp(−2) ≈ 0.135  (opposite hemispheres)

    We re-normalise the output so that the "random baseline" maps to 0 and a
    perfect match maps to 100, giving an intuitive confidence percentage:

        score = (sim − baseline) / (1 − baseline) × 100
               where baseline = exp(−1) ≈ 0.368

    This is strictly monotone, approaches 100 only for near-identical vectors,
    and never produces negative values for plausible L2 distances.
    """
    if len(distances_1d) == 0:
        return 0.0

    sigma_sq  = 2.0
    baseline  = math.exp(-1.0)   # sim at L2²=2 (random pair of unit vectors)

    mean_sq_dist = float(np.mean(distances_1d ** 2))
    raw_sim      = math.exp(-mean_sq_dist / (2.0 * sigma_sq))

    if raw_sim <= baseline:
        return 0.0

    return min(100.0, ((raw_sim - baseline) / (1.0 - baseline)) * 100.0)


# ──────────────────────────────────────────────────────────────────────────────
# Task 2 — Dynamic Time Warping (DTW) sequence alignment
# ──────────────────────────────────────────────────────────────────────────────
def _exact_dtw(seq_a: np.ndarray, seq_b: np.ndarray) -> float:
    """
    Vectorised exact DTW using NumPy broadcasting.

    Complexity: O(N × M) time, O(N × M) space.
    Used as the fallback when fastdtw is not installed.

    Parameters
    ----------
    seq_a : (N, D)  suspect sequence
    seq_b : (M, D)  golden sequence

    Returns
    -------
    float  Accumulated DTW distance normalised by warping-path length (N + M).
    """
    n, m = len(seq_a), len(seq_b)
    if n == 0 or m == 0:
        return math.inf

    # Pairwise L2 cost matrix  (N, M)
    # ‖a − b‖ = sqrt(‖a‖² + ‖b‖² − 2·aᵀb)
    sq_a = np.sum(seq_a ** 2, axis=1, keepdims=True)   # (N, 1)
    sq_b = np.sum(seq_b ** 2, axis=1, keepdims=True)   # (M, 1)
    cost = np.sqrt(np.maximum(sq_a + sq_b.T - 2.0 * (seq_a @ seq_b.T), 0.0))

    # DP accumulation — inner loop is unavoidable for exact DTW in Python;
    # for very long sequences prefer fastdtw (O(N) approximate).
    D = np.full((n + 1, m + 1), np.inf, dtype=np.float64)
    D[0, 0] = 0.0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = cost[i - 1, j - 1] + min(
                D[i - 1, j],        # vertical   (insertion)
                D[i, j - 1],        # horizontal (deletion)
                D[i - 1, j - 1],    # diagonal   (match)
            )

    path_len = n + m
    return float(D[n, m]) / path_len if path_len > 0 else 0.0


def _approx_dtw(seq_a: np.ndarray, seq_b: np.ndarray) -> float:
    """
    Approximate DTW via the fastdtw library (O(N) time and space).

    Returns
    -------
    float  Normalised DTW distance (divided by warping-path length).
    """
    distance, _ = fastdtw(seq_a, seq_b, dist=euclidean)
    path_len = len(seq_a) + len(seq_b)
    return float(distance) / path_len if path_len > 0 else 0.0


def _dtw_distance(seq_a: np.ndarray, seq_b: np.ndarray) -> float:
    """
    Dispatch to fastdtw (preferred) or exact DTW fallback.
    The approximate variant is chosen whenever both sequences are longer than
    50 frames AND fastdtw is installed, to keep latency acceptable.
    """
    if _FASTDTW_AVAILABLE and len(seq_a) > 50 and len(seq_b) > 50:
        return _approx_dtw(seq_a, seq_b)
    return _exact_dtw(seq_a, seq_b)


def _dtw_score_to_similarity(normalised_dtw_dist: float) -> float:
    """
    Map a normalised DTW distance → [0, 100] similarity score using the same
    RBF kernel principle as _l2_to_similarity.

    A normalised DTW distance of 0 → 100% (identical sequences).
    The "random baseline" (σ = 1.0 in normalised-distance space) → 0%.
    """
    raw_sim  = math.exp(-normalised_dtw_dist)
    baseline = math.exp(-1.0)
    if raw_sim <= baseline:
        return 0.0
    return min(100.0, ((raw_sim - baseline) / (1.0 - baseline)) * 100.0)


def _compute_dtw_score(
    suspect_seq: np.ndarray,
    golden_sequences: Dict[str, List[np.ndarray]],
) -> float:
    """
    Compare a suspect frame sequence against every indexed golden sequence
    using DTW alignment and return the best (highest) similarity score.

    A video that is sped up, slowed down, or has dropped/duplicated frames
    will still be aligned correctly by DTW's non-linear warping path.

    Parameters
    ----------
    suspect_seq     : (N, D)  ordered suspect vectors
    golden_sequences: mapping asset_id → list of (D,) golden vectors

    Returns
    -------
    float  Best similarity score in [0, 100].
    """
    if not golden_sequences or len(suspect_seq) == 0:
        return 0.0

    best = 0.0
    for vecs in golden_sequences.values():
        if not vecs:
            continue
        golden_arr   = np.array(vecs, dtype=np.float32)
        dist         = _dtw_distance(suspect_seq, golden_arr)
        sim          = _dtw_score_to_similarity(dist)
        best         = max(best, sim)

    return best


# ──────────────────────────────────────────────────────────────────────────────
# Task 3 — Score fusion with graceful degradation
# ──────────────────────────────────────────────────────────────────────────────
def _fuse_scores(
    visual_score: float,
    text_score:   float,
    audio_score:  float,
    has_visual:   bool,
    has_text:     bool,
    has_audio:    bool,
) -> float:
    """
    Weighted average fusion: Visual 60 %, Audio 30 %, Text 10 %.

    When a modality is absent the remaining weights are renormalised so they
    always sum to exactly 1.0.  Examples:

        Visual + Audio only  → Visual 66.7%, Audio 33.3%
        Visual only          → Visual 100%
        Audio + Text only    → Audio 75%,   Text 25%
    """
    weights = {
        "visual": _W_VISUAL if has_visual else 0.0,
        "audio":  _W_AUDIO  if has_audio  else 0.0,
        "text":   _W_TEXT   if has_text   else 0.0,
    }
    total = sum(weights.values())
    if total == 0.0:
        return 0.0

    fused = (
        weights["visual"] * visual_score
        + weights["audio"]  * audio_score
        + weights["text"]   * text_score
    ) / total

    return min(100.0, max(0.0, fused))


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI lifecycle
# ──────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def _startup() -> None:
    """
    Load persisted FAISS indices and metadata from ./data on server start.
    If no snapshot exists, fresh in-memory structures are initialised so the
    service can start clean without manual setup.
    """
    print("[ML Auditor v2] Loading state from disk …")
    _load_state()
    print(
        f"[ML Auditor v2] Ready. "
        f"Visual: {index_visual.ntotal} vecs | "
        f"Text: {index_text.ntotal} vecs | "
        f"Audio: {index_audio.ntotal} vecs"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints  — routing & schema preserved from v1.0.0
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/api/v1/auditor/index")
async def index_vectors(payload: VectorPayload) -> dict:
    """
    Accept visual, text, and audio embedding vectors for a golden (reference)
    asset, add them to the corresponding FAISS indices, and persist state to
    disk so the knowledge base survives server restarts.

    Vectors are appended in the order received; this temporal order is stored
    in the sequence dictionaries so DTW alignment works correctly.
    """
    global visual_count, text_count, audio_count

    n_visual = n_text = n_audio = 0

    # ── Visual ───────────────────────────────────────────────────────────────
    if payload.visual_vectors:
        vis_arr = np.array(payload.visual_vectors, dtype=np.float32)
        if vis_arr.ndim != 2 or vis_arr.shape[1] != VISUAL_DIM:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Each visual vector must be {VISUAL_DIM}-D; "
                    f"received shape {vis_arr.shape}"
                ),
            )
        index_visual.add(vis_arr)
        for row in vis_arr:
            visual_metadata[visual_count] = payload.asset_id
            visual_sequences[payload.asset_id].append(row)
            visual_count += 1
        n_visual = len(payload.visual_vectors)

    # ── Text (OCR / MiniLM) ──────────────────────────────────────────────────
    if payload.text_vectors:
        txt_arr = np.array(payload.text_vectors, dtype=np.float32)
        if txt_arr.ndim != 2 or txt_arr.shape[1] != TEXT_DIM:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Each text vector must be {TEXT_DIM}-D; "
                    f"received shape {txt_arr.shape}"
                ),
            )
        index_text.add(txt_arr)
        for row in txt_arr:
            text_metadata[text_count] = payload.asset_id
            text_sequences[payload.asset_id].append(row)
            text_count += 1
        n_text = len(payload.text_vectors)

    # ── Audio (Whisper → MiniLM) ─────────────────────────────────────────────
    if payload.audio_vectors:
        aud_arr = np.array(payload.audio_vectors, dtype=np.float32)
        if aud_arr.ndim != 2 or aud_arr.shape[1] != AUDIO_DIM:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Each audio vector must be {AUDIO_DIM}-D; "
                    f"received shape {aud_arr.shape}"
                ),
            )
        index_audio.add(aud_arr)
        for row in aud_arr:
            audio_metadata[audio_count] = payload.asset_id
            audio_sequences[payload.asset_id].append(row)
            audio_count += 1
        n_audio = len(payload.audio_vectors)

    # ── Persist to disk after every indexing call ────────────────────────────
    _save_state()

    return {
        "status":          "success",
        "asset_id":        payload.asset_id,
        "indexed_visual":  n_visual,
        "indexed_text":    n_text,
        "indexed_audio":   n_audio,
    }


@app.post("/api/v1/auditor/search", response_model=SearchResult)
async def search_vectors(payload: VectorPayload) -> SearchResult:
    """
    Multimodal similarity search against the golden asset database.

    Pipeline per modality
    ─────────────────────
    1.  FAISS flat search  — fast per-frame nearest-neighbour baseline.
    2.  DTW sequence alignment — time-warp-robust sequence comparison.
    3.  Blend:  score = 0.65 × DTW + 0.35 × FAISS-flat
        (DTW dominates because it handles temporal distortions; the flat
        component gives a quick early-exit signal for exact copies.)

    Fusion
    ──────
    fused = W_visual × visual + W_audio × audio + W_text × text

    with weights renormalised to 1.0 when a modality is absent.

    Verdict thresholds (unchanged from v1 for Orchestrator compatibility)
    ─────────────────────────────────────────────────────────────────────
    fused ≥ 85  →  PIRACY_DETECTED
    fused ≥ 60  →  SUSPICIOUS
    fused  < 60 →  CLEAN
    """
    nothing_indexed = (
        index_visual.ntotal == 0
        and index_text.ntotal == 0
        and index_audio.ntotal == 0
    )
    if nothing_indexed:
        return SearchResult(
            verdict="CLEAN",
            visual_score=0.0,
            text_score=0.0,
            audio_score=0.0,
            fused_score=0.0,
        )

    # Determine which modalities are actually usable for this query
    has_visual = bool(payload.visual_vectors) and index_visual.ntotal > 0
    has_text   = bool(payload.text_vectors)   and index_text.ntotal   > 0
    has_audio  = bool(payload.audio_vectors)  and index_audio.ntotal  > 0

    visual_score = text_score = audio_score = 0.0

    # ── Visual ───────────────────────────────────────────────────────────────
    if has_visual:
        vis_arr = np.array(payload.visual_vectors, dtype=np.float32)

        # FAISS flat — per-frame nearest-neighbour
        distances, _ = index_visual.search(vis_arr, 1)
        flat_sim      = _l2_to_similarity(distances[:, 0])

        # DTW — sequence-level temporal alignment
        dtw_sim       = _compute_dtw_score(vis_arr, dict(visual_sequences))

        visual_score  = 0.65 * dtw_sim + 0.35 * flat_sim

    # ── Text (OCR) ───────────────────────────────────────────────────────────
    if has_text:
        txt_arr = np.array(payload.text_vectors, dtype=np.float32)

        distances, _ = index_text.search(txt_arr, 1)
        flat_sim      = _l2_to_similarity(distances[:, 0])

        dtw_sim       = _compute_dtw_score(txt_arr, dict(text_sequences))

        text_score    = 0.65 * dtw_sim + 0.35 * flat_sim

    # ── Audio ────────────────────────────────────────────────────────────────
    if has_audio:
        aud_arr = np.array(payload.audio_vectors, dtype=np.float32)

        distances, _ = index_audio.search(aud_arr, 1)
        flat_sim      = _l2_to_similarity(distances[:, 0])

        dtw_sim       = _compute_dtw_score(aud_arr, dict(audio_sequences))

        audio_score   = 0.65 * dtw_sim + 0.35 * flat_sim

    # ── Fusion ───────────────────────────────────────────────────────────────
    fused_score = _fuse_scores(
        visual_score, text_score, audio_score,
        has_visual, has_text, has_audio,
    )

    # ── Verdict ──────────────────────────────────────────────────────────────
    if fused_score >= 85.0:
        verdict = "PIRACY_DETECTED"
        verdict_color = "\033[91m🔴 PIRACY_DETECTED\033[0m"
    elif fused_score >= 60.0:
        verdict = "SUSPICIOUS"
        verdict_color = "\033[93m🟡 SUSPICIOUS\033[0m"
    else:
        verdict = "CLEAN"
        verdict_color = "\033[92m🟢 CLEAN\033[0m"

    print("\n" + "═"*55)
    print(" 🔎 ========== AUDITOR FORENSIC REPORT ========== 🔎 ")
    print("═"*55)
    print(f" Asset ID: {payload.asset_id}")
    print(f" Received: {len(payload.visual_vectors)} Visual, {len(payload.text_vectors)} Text, {len(payload.audio_vectors)} Audio vectors")
    print("-" * 55)
    print(f" Visual Score : {visual_score:5.2f}%")
    print(f" Text Score   : {text_score:5.2f}%")
    print(f" Audio Score  : {audio_score:5.2f}%")
    print("-" * 55)
    print(f" Fused Score  : \033[1m{fused_score:5.2f}%\033[0m")
    print(f" Verdict      : {verdict_color}")
    print("═"*55 + "\n")

    return SearchResult(
        verdict      = verdict,
        visual_score = round(visual_score, 4),
        text_score   = round(text_score,   4),
        audio_score  = round(audio_score,  4),
        fused_score  = round(fused_score,  4),
    )


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)