"""
╔══════════════════════════════════════════════════════════════════════╗
║  SourceGraph — Extractor Module (Phase 1: Local Sandbox)           ║
║  Owner : Yogesh (M2 Node)                                         ║
║  File  : extractor_test.py                                        ║
║                                                                    ║
║  PURPOSE:                                                          ║
║    1. Demux an .mp4 → 1-fps JPEG frames + 16 kHz mono WAV         ║
║    2. Generate Shazam-style constellation audio hashes             ║
║    3. Print the first N hashes for verification                    ║
║                                                                    ║
║  USAGE:                                                            ║
║    python extractor_test.py                                        ║
║    (expects test_video.mp4 in the same directory)                  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import shutil
import hashlib
import subprocess
from pathlib import Path
from typing import List, Tuple

import numpy as np
from scipy.io import wavfile
from scipy.ndimage import maximum_filter
from scipy.signal import spectrogram as scipy_spectrogram

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────

# Input / Output paths (all relative to this script's directory)
SCRIPT_DIR      = Path(__file__).resolve().parent
INPUT_VIDEO     = SCRIPT_DIR / "test_video.mp4"
OUTPUT_DIR      = SCRIPT_DIR / "_sandbox_output"       # temp working dir
FRAMES_DIR      = OUTPUT_DIR / "frames"
AUDIO_PATH      = OUTPUT_DIR / "audio_16k_mono.wav"

# FFmpeg tuning
FRAME_RATE      = 1               # Extract 1 frame per second
AUDIO_SAMPLE_HZ = 16_000          # 16 kHz — standard for fingerprinting
JPEG_QUALITY    = 2               # FFmpeg qscale:v  (2 = high quality)

# Spectrogram / Constellation tuning  (Shazam paper defaults)
NPERSEG         = 1024            # FFT window size  (~64 ms at 16 kHz)
NOVERLAP        = 512             # 50 % overlap
PEAK_NEIGHBORHOOD = 20            # Local-max filter size (freq × time)

# Target-zone pairing (anchor → target fan-out)
FAN_OUT         = 5               # Pair each anchor with up to 5 targets
TARGET_T_MIN    = 1               # Minimum time-delta (spectrogram bins)
TARGET_T_MAX    = 50              # Maximum time-delta
TARGET_F_RANGE  = 100             # Max freq-delta (spectrogram bins)

# How many hashes to print for sanity-check
PRINT_N_HASHES  = 5


# ─────────────────────────────────────────────────────────────────────
# 1.  DEMUXER  —  FFmpeg Pipeline (Apple Silicon optimised)
# ─────────────────────────────────────────────────────────────────────

def demux_video(video_path: Path = INPUT_VIDEO) -> Tuple[Path, Path]:
    """
    Split an .mp4 into:
        • JPEG frames at 1 fps  →  FRAMES_DIR/frame_00001.jpg …
        • 16 kHz mono WAV       →  AUDIO_PATH

    On Apple Silicon we request VideoToolbox HW-accelerated decoding
    via `-hwaccel videotoolbox`.  If the flag is unsupported (e.g. CI
    runner), FFmpeg silently falls back to software decode — no crash.

    Returns
    -------
    (frames_dir, audio_path) : Tuple[Path, Path]
    """

    if not video_path.exists():
        raise RuntimeError(f"Input video not found: {video_path}")

    # Wipe & recreate output dirs so every run is idempotent
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"🎬  Demuxing: {video_path.name}")
    t0 = time.perf_counter()

    # ── 1-A  Extract frames at 1 fps ──────────────────────────────
    #
    #   -hwaccel videotoolbox     → Apple Silicon HW decode
    #   -vf "fps=1"               → output exactly 1 frame / second
    #   -qscale:v 2               → JPEG quality (2 = high)
    #   -frame_pts 1              → embed PTS in filename for sorting
    #
    frame_pattern = str(FRAMES_DIR / "frame_%05d.jpg")

    frame_cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "videotoolbox",        # M2 hardware decode
        "-i", str(video_path),
        "-vf", f"fps={FRAME_RATE}",
        "-fps_mode", "cfr",
        "-qscale:v", str(JPEG_QUALITY),
        frame_pattern,
    ]

    result = subprocess.run(frame_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print("⚠️  VideoToolbox unavailable — falling back to software decode")
        frame_cmd_sw = [c for c in frame_cmd if c not in ("-hwaccel", "videotoolbox")]
        result = subprocess.run(frame_cmd_sw, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg frame extraction failed:\n{result.stderr.decode()}")


    n_frames = len(list(FRAMES_DIR.glob("*.jpg")))

    # ── 1-B  Extract audio as 16 kHz mono WAV ────────────────────
    #
    #   -vn                       → discard video stream
    #   -acodec pcm_s16le         → 16-bit PCM (lossless for hashing)
    #   -ar 16000 -ac 1           → 16 kHz, mono
    #
    audio_cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(AUDIO_SAMPLE_HZ),
        "-ac", "1",
        str(AUDIO_PATH),
    ]

    result = subprocess.run(
        audio_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed:\n{result.stderr.decode()}")

    elapsed = time.perf_counter() - t0
    print(f"✅  Demux complete in {elapsed:.2f}s  →  {n_frames} frames, WAV @ {AUDIO_SAMPLE_HZ} Hz")
    return FRAMES_DIR, AUDIO_PATH


# ─────────────────────────────────────────────────────────────────────
# 2.  AUDIO ENGINE  —  Shazam Constellation Hashing
# ─────────────────────────────────────────────────────────────────────
#
# Algorithm (per the 2003 Wang / Shazam patent):
#
#   Step 1 — Compute the spectrogram (STFT magnitude).
#   Step 2 — Find local peaks ("stars" in the constellation map).
#   Step 3 — For each peak (the "anchor"), fan out to nearby future
#            peaks (the "targets") and produce a hash:
#
#              hash = SHA-256( anchor_freq | target_freq | Δt )
#
#            Each hash is stored with its absolute anchor time so we
#            can align matches later.
#
# The result is a list of (hash_hex, anchor_time_bin) tuples.
# ─────────────────────────────────────────────────────────────────────

def _compute_spectrogram(samples: np.ndarray, sr: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute a power spectrogram using scipy.signal.spectrogram.

    Parameters
    ----------
    samples : 1-D int16 or float array (mono audio)
    sr      : sample rate in Hz

    Returns
    -------
    freqs, times, Sxx  (frequency axis, time axis, power matrix)
    """
    # Normalise int16 → float32 [-1, 1]
    if samples.dtype == np.int16:
        samples = samples.astype(np.float32) / 32768.0

    freqs, times, Sxx = scipy_spectrogram(
        samples,
        fs=sr,
        nperseg=NPERSEG,
        noverlap=NOVERLAP,
        window="hann",
    )

    # Convert to log-power (dB scale) — makes peaks more prominent
    Sxx = 10 * np.log10(Sxx + 1e-10)

    return freqs, times, Sxx


def _find_peaks(Sxx: np.ndarray) -> List[Tuple[int, int]]:
    """
    Detect local maxima in the spectrogram.

    A cell is a peak iff it equals the maximum within a
    (PEAK_NEIGHBORHOOD × PEAK_NEIGHBORHOOD) window around it.

    Returns
    -------
    List of (freq_bin, time_bin) tuples, sorted by time.
    """
    # Apply a maximum filter — each cell becomes the max of its
    # neighbourhood.  Peaks are cells where the original value
    # survived the filter unchanged.
    local_max = maximum_filter(Sxx, size=PEAK_NEIGHBORHOOD)
    peaks_mask = (Sxx == local_max)

    # Suppress low-energy noise: only keep peaks above the median
    # power level.  This dramatically reduces false positives on
    # silence / background hiss.
    threshold = np.median(Sxx) + (np.std(Sxx) * 0.5)
    peaks_mask &= (Sxx > threshold)

    # Extract (freq_bin, time_bin) coordinates
    freq_indices, time_indices = np.where(peaks_mask)
    peaks = list(zip(freq_indices.tolist(), time_indices.tolist()))

    # Sort by time (primary) then frequency (secondary) so the
    # fan-out pairing below is deterministic.
    peaks.sort(key=lambda p: (p[1], p[0]))

    return peaks


def _pair_hashes(
    peaks: List[Tuple[int, int]],
) -> List[Tuple[str, int]]:
    """
    Generate anchor → target hashes (Shazam fan-out).

    For every anchor peak, we look ahead within a "target zone"
    defined by time and frequency deltas.  Each valid pair produces
    a deterministic hash.

    Returns
    -------
    List of (hash_hex_string, anchor_time_bin)
    """
    if not peaks:
        raise RuntimeError("No peaks found — audio may be silent or corrupt")
    hashes: List[Tuple[str, int]] = []

    for i, (f_anchor, t_anchor) in enumerate(peaks):
        targets_found = 0

        for j in range(i + 1, len(peaks)):
            f_target, t_target = peaks[j]
            dt = t_target - t_anchor
            df = abs(f_target - f_anchor)

            # Outside the time window → stop scanning (list is sorted)
            if dt > TARGET_T_MAX:
                break

            # Inside the target zone?
            if dt < TARGET_T_MIN:
                continue
            if df > TARGET_F_RANGE:
                continue

            # ── Build the hash ───────────────────────────────────
            # Payload:  anchor_freq | target_freq | time_delta
            # We use SHA-256 truncated to 16 hex chars (64 bits)
            # for compact storage while keeping collision rate
            # astronomically low.
            raw = f"{f_anchor}|{f_target}|{dt}".encode("utf-8")
            h   = hashlib.sha256(raw).hexdigest()[:16]

            hashes.append((h, t_anchor))

            targets_found += 1
            if targets_found >= FAN_OUT:
                break

    return hashes


def generate_constellation_hashes(
    wav_path: Path = AUDIO_PATH,
) -> List[Tuple[str, int]]:
    """
    Full pipeline: WAV → spectrogram → peaks → hashes.

    Returns
    -------
    List of (hash_hex, anchor_time_bin) — the audio fingerprint.
    """

    if not wav_path.exists():
        raise RuntimeError(f"WAV file not found: {wav_path}")

    print(f"🎵  Loading audio: {wav_path.name}")
    sr, samples = wavfile.read(str(wav_path))
    if samples.ndim > 1:
        samples = samples[:, 0]
    duration_s = len(samples) / sr
    print(f"    → {sr} Hz, {len(samples)} samples, {duration_s:.1f}s")

    # Step 1 — Spectrogram
    print("📊  Computing spectrogram …")
    freqs, times, Sxx = _compute_spectrogram(samples, sr)
    print(f"    → Shape: {Sxx.shape}  (freq_bins × time_bins)")

    # Step 2 — Constellation peaks
    print("⭐  Finding constellation peaks …")
    peaks = _find_peaks(Sxx)
    print(f"    → {len(peaks)} peaks detected")

    # Step 3 — Anchor-target fan-out hashes
    print("🔗  Generating target-zone hashes …")
    hashes = _pair_hashes(peaks)
    print(f"    → {len(hashes)} hashes generated")

    return hashes


# ─────────────────────────────────────────────────────────────────────
# 3.  MAIN  —  Run the full Phase-1 pipeline
# ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 66)
    print("  SourceGraph — Extractor  ·  Phase 1 Local Sandbox")
    print("=" * 66)

    # ── STEP A:  Demux ────────────────────────────────────────────
    frames_dir, audio_path = demux_video()

    # Quick report: list extracted frames
    frames = sorted(frames_dir.glob("*.jpg"))
    print(f"\n📁  Frames directory: {frames_dir}")
    for f in frames[:5]:
        print(f"    • {f.name}  ({f.stat().st_size / 1024:.0f} KB)")
    if len(frames) > 5:
        print(f"    … and {len(frames) - 5} more")

    # ── STEP B:  Audio hashing ────────────────────────────────────
    print()
    hashes = generate_constellation_hashes(audio_path)

    # Print the first N hashes
    print(f"\n🔑  First {PRINT_N_HASHES} constellation hashes:")
    print("-" * 50)
    print(f"  {'HASH (64-bit)':<20} {'ANCHOR TIME BIN':>15}")
    print("-" * 50)
    for h, t in hashes[:PRINT_N_HASHES]:
        print(f"  {h:<20} {t:>15}")
    print("-" * 50)

    print(f"\n✅  Phase 1 complete.  Total hashes: {len(hashes)}")
    print(f"    Output stored in: {OUTPUT_DIR}")
    print("=" * 66)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"❌  {e}")
        sys.exit(1)
