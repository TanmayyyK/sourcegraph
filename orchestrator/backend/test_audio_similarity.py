"""PostgreSQL fallback must score matching speech even without frame vectors."""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from app.services.similarity_service import SimilarityService


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)


class _Session:
    def __init__(self, suspect_id, golden_id):
        transcript = ["How a hole becomes a trench", "Digging begins here"]
        self.results = [
            _Rows([]),
            _Rows([SimpleNamespace(asset_id=suspect_id, segment_text=text) for text in transcript]),
            _Rows([SimpleNamespace(asset_id=golden_id, segment_text=text) for text in transcript]),
        ]
        self.saved = None

    async def execute(self, _statement):
        return self.results.pop(0)

    def add(self, row):
        self.saved = row

    async def commit(self):
        pass

    async def refresh(self, _row):
        pass


class AudioFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_audio_only_match(self):
        suspect_id, golden_id = uuid4(), uuid4()
        db = _Session(suspect_id, golden_id)

        result = await SimilarityService().run_for_asset(suspect_id, db)

        self.assertIs(result, db.saved)
        self.assertEqual(result.golden_asset_id, golden_id)
        self.assertEqual(result.audio_score, 1.0)
        self.assertEqual(result.fused_score, 1.0)
        self.assertEqual(result.verdict, "PIRACY_DETECTED")


if __name__ == "__main__":
    unittest.main()
