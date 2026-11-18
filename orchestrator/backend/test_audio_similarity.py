"""Regression checks for native sequence scoring and fusion."""

from collections import defaultdict
from uuid import UUID

from app.services.similarity_service import SimilarityService

PROTECTED = UUID(int=1)
OTHER = UUID(int=2)


def sequence(*vectors):
    return list(enumerate(vectors))


def test_embedding_alignment_tolerates_repeated_segments():
    short = sequence([1, 0], [0, 1])
    long = sequence([1, 0], [1, 0], [0, 1], [0, 1])
    comparisons = {PROTECTED: {"audio_score": (short, long)}}

    result, matched, _ = SimilarityService._rank({PROTECTED}, comparisons, {})

    assert matched == PROTECTED
    assert result["audio_score"] == result["fused_score"] == 1.0


def test_fusion_does_not_combine_different_references():
    query = sequence([1, 0])
    other = sequence([0, 1])
    comparisons = {
        PROTECTED: {"visual_score": (query, query), "audio_score": (query, other)},
        OTHER: {"visual_score": (query, other), "audio_score": (query, query)},
    }

    result, matched, _ = SimilarityService._rank({PROTECTED, OTHER}, comparisons, {})

    assert matched == PROTECTED
    assert result["visual_score"] == 1.0
    assert result["audio_score"] == 0.0
    assert 0.60 < result["fused_score"] < 0.70


def test_transcripts_support_references_without_speech_vectors():
    words = ["how", "a", "hole", "becomes", "a", "trench"]
    transcripts = [(PROTECTED, "How a hole becomes a trench")]
    legacy = SimilarityService._transcript_scores(words, transcripts)

    result, matched, timestamp = SimilarityService._rank({PROTECTED}, defaultdict(dict), legacy)

    assert matched == PROTECTED
    assert timestamp is None
    assert result["audio_score"] == result["fused_score"] == 1.0
