"""Regression checks for transcript audio matching and per-asset fusion."""

import asyncio
import unittest

import faiss
import numpy as np

from ml_auditor import main as auditor


def unit_vector(dim: int, position: int) -> np.ndarray:
    vector = np.zeros(dim, dtype=np.float32)
    vector[position] = 1.0
    return vector


class AudioScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = (
            getattr(auditor, "index_visual", None),
            getattr(auditor, "index_text", None),
            getattr(auditor, "index_audio", None),
            auditor.visual_sequences,
            auditor.text_sequences,
            auditor.audio_sequences,
        )
        auditor.index_visual = faiss.IndexFlatL2(512)
        auditor.index_text = faiss.IndexFlatL2(384)
        auditor.index_audio = faiss.IndexFlatL2(384)
        auditor.visual_sequences = {}
        auditor.text_sequences = {}
        auditor.audio_sequences = {}

    def tearDown(self) -> None:
        (
            auditor.index_visual,
            auditor.index_text,
            auditor.index_audio,
            auditor.visual_sequences,
            auditor.text_sequences,
            auditor.audio_sequences,
        ) = self.original

    def test_modalities_match_one_golden_asset(self) -> None:
        visual_a, visual_b = unit_vector(512, 0), unit_vector(512, 1)
        audio_a, audio_b = unit_vector(384, 0), unit_vector(384, 1)
        auditor.index_visual.add(np.stack([visual_a, visual_b]))
        auditor.index_audio.add(np.stack([audio_b, audio_a]))
        auditor.visual_sequences = {"A": [visual_a], "B": [visual_b]}
        auditor.audio_sequences = {"A": [audio_b], "B": [audio_a]}

        result = asyncio.run(auditor.search_vectors(auditor.VectorPayload(
            asset_id="suspect",
            visual_vectors=[visual_a.tolist()],
            audio_vectors=[audio_a.tolist()],
        )))

        self.assertEqual(result.golden_asset_id, "A")
        self.assertAlmostEqual(result.visual_score, 100.0)
        self.assertLess(result.audio_score, 100.0)
        self.assertLess(result.fused_score, 100.0)

    def test_shortened_audio_still_matches(self) -> None:
        first, second = unit_vector(384, 0), unit_vector(384, 1)
        auditor.index_audio.add(np.stack([first, second, first]))
        auditor.audio_sequences = {"golden": [first, second, first]}

        result = asyncio.run(auditor.search_vectors(auditor.VectorPayload(
            asset_id="sped-up",
            audio_vectors=[first.tolist(), first.tolist()],
        )))

        self.assertEqual(result.golden_asset_id, "golden")
        self.assertGreater(result.audio_score, 50.0)
        self.assertEqual(result.audio_score, result.fused_score)


if __name__ == "__main__":
    unittest.main()
