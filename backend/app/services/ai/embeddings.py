"""Embedding provider factory.

Two providers are supported:
  huggingface  — local sentence-transformers model, free, multilingual (default).
                 Model: paraphrase-multilingual-MiniLM-L12-v2 (384 dims, supports Bengali).
  fake         — deterministic stub used in tests and CI; always falls back to
                 fuzzy search so no real embedding work happens.

When langchain-huggingface / sentence-transformers are not installed (e.g. on
Python 3.14 before wheels land) the module silently degrades to fake mode so
the rest of the codebase can still import and run under fuzzy search.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Protocol, runtime_checkable

from app.core.config import get_settings

try:
    from langchain_huggingface import HuggingFaceEmbeddings

    _HUGGINGFACE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _HUGGINGFACE_AVAILABLE = False


@runtime_checkable
class EmbeddingProvider(Protocol):
    def embed_query(self, text: str) -> list[float]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class _FakeEmbeddingProvider:
    """Stub that satisfies EmbeddingProvider but always signals unavailability.

    Never used for actual similarity — is_semantic_available() returns False
    when this provider is active, so search falls back to fuzzy.
    """

    def embed_query(self, text: str) -> list[float]:  # pragma: no cover
        return [0.0] * 384

    def embed_documents(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover
        return [[0.0] * 384 for _ in texts]


@lru_cache(maxsize=1)
def _get_provider() -> EmbeddingProvider:
    settings = get_settings()
    if not _HUGGINGFACE_AVAILABLE or settings.EMBEDDING_PROVIDER == "fake":
        return _FakeEmbeddingProvider()
    return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)  # type: ignore[return-value]


def is_semantic_available() -> bool:
    """True only when a real (non-fake) embedding model is loaded and ready."""
    return _HUGGINGFACE_AVAILABLE and get_settings().EMBEDDING_PROVIDER != "fake"


def embed_text(text: str) -> list[float]:
    return _get_provider().embed_query(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    return _get_provider().embed_documents(texts)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity. Returns 0.0 for zero-norm vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
