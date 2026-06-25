"""Embeddings (KAN-4).

Defines an ``Embedder`` interface plus a dependency-free default
(``HashingEmbedder``) so the knowledge base can be built and queried locally with
no model download or API key. The interface lets a real provider (OpenAI,
sentence-transformers) be swapped in without changing the index or retriever.

The default uses deterministic feature hashing (hashlib, not Python's salted
``hash``) so an index built today reproduces exactly when rebuilt — satisfying
the "vector store can be rebuilt from source documents" requirement.
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "is", "are", "be",
    "for", "with", "as", "at", "by", "it", "this", "that", "from", "if", "not",
    "no", "so", "do", "does", "when", "while", "than", "then", "into", "its",
}


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords and 1-char tokens."""
    return [
        t for t in _TOKEN_RE.findall(text.lower())
        if len(t) > 1 and t not in _STOPWORDS
    ]


class Embedder(ABC):
    """Turns text into a fixed-length, L2-normalized vector."""

    dim: int

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return the embedding for a single text."""

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    @property
    def name(self) -> str:
        return type(self).__name__


class HashingEmbedder(Embedder):
    """Deterministic feature-hashing embedder (term-frequency, signed)."""

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def _bucket(self, token: str) -> tuple[int, float]:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % self.dim
        sign = 1.0 if digest[4] & 1 else -1.0
        return idx, sign

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in tokenize(text):
            idx, sign = self._bucket(token)
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]


class OpenAIEmbedder(Embedder):
    """Placeholder for a real embedding provider.

    Implement ``embed`` by calling the provider's embeddings API and returning the
    (L2-normalized) vector. Left unimplemented so the MVP has no network/API-key
    dependency; ``HashingEmbedder`` is the working default.
    """

    def __init__(self, model: str = "text-embedding-3-small", dim: int = 1536) -> None:
        self.model = model
        self.dim = dim

    def embed(self, text: str) -> list[float]:  # pragma: no cover - placeholder
        raise NotImplementedError(
            "OpenAIEmbedder is a placeholder. Use HashingEmbedder for local runs, "
            "or implement this against the provider's embeddings API."
        )


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors (0 if either is zero)."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
