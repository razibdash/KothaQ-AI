"""Unit tests for semantic search helpers.

These tests cover the pure-Python functions that have no external dependencies
(cosine_similarity) and the embedding availability guard (is_semantic_available).
The full semantic_search() integration is covered by the existing
test_knowledge_search.py tests which exercise the fuzzy fallback path — the
same contract holds for both paths.
"""

import math

import pytest

from app.services.ai.embeddings import cosine_similarity, is_semantic_available


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self) -> None:
        v = [0.1, 0.5, 0.3, 0.8]
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors_score_zero(self) -> None:
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors_score_negative_one(self) -> None:
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0, abs=1e-6)

    def test_zero_vector_returns_zero(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
        assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0
        assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    def test_symmetric(self) -> None:
        a = [0.3, 0.7, 0.1]
        b = [0.9, 0.2, 0.5]
        assert cosine_similarity(a, b) == pytest.approx(cosine_similarity(b, a), abs=1e-9)

    def test_score_is_bounded(self) -> None:
        import random

        rng = random.Random(42)
        for _ in range(50):
            a = [rng.uniform(-1, 1) for _ in range(16)]
            b = [rng.uniform(-1, 1) for _ in range(16)]
            score = cosine_similarity(a, b)
            assert -1.0 - 1e-9 <= score <= 1.0 + 1e-9

    def test_high_dimensional_vectors(self) -> None:
        dims = 384
        a = [1.0 / math.sqrt(dims)] * dims
        b = [1.0 / math.sqrt(dims)] * dims
        assert cosine_similarity(a, b) == pytest.approx(1.0, abs=1e-5)


class TestIsSemanticAvailable:
    def test_returns_bool(self) -> None:
        result = is_semantic_available()
        assert isinstance(result, bool)

    def test_false_without_embedding_packages(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import app.services.ai.embeddings as emb_mod

        monkeypatch.setattr(emb_mod, "_HUGGINGFACE_AVAILABLE", False)
        assert emb_mod.is_semantic_available() is False

    def test_false_when_provider_is_fake(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import app.services.ai.embeddings as emb_mod
        from app.core.config import Settings

        monkeypatch.setattr(emb_mod, "_HUGGINGFACE_AVAILABLE", True)
        monkeypatch.setattr(
            emb_mod,
            "get_settings",
            lambda: Settings(EMBEDDING_PROVIDER="fake"),
        )
        assert emb_mod.is_semantic_available() is False
