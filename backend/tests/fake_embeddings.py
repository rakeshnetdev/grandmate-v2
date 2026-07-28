"""A deterministic, hash-based fake `EmbeddingProvider` for tests.

No real network call, and no real semantic understanding — but texts sharing
vocabulary land closer together in cosine-similarity space than texts that share
nothing, which is exactly the property retrieval unit tests need to make meaningful
assertions ("the pin chunk ranks above the fork chunk for a pin-related query")
without depending on a live embedding API. Genuine paraphrase/semantic-generalisation
behaviour is what the real RAGAS harness (`evals/`) measures against real embeddings —
this fake is deliberately not trying to substitute for that.
"""

from __future__ import annotations

import hashlib
import math
import re

from app.db.models.knowledge import EMBEDDING_DIMENSIONS

_WORD_RE = re.compile(r"[a-z0-9]+")


class FakeEmbeddingProvider:
    """`EmbeddingProvider`: a bag-of-hashed-words vector, L2-normalised."""

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self._dimensions = dimensions

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for word in _WORD_RE.findall(text.lower()):
            index = int(hashlib.sha256(word.encode()).hexdigest(), 16) % self._dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(component * component for component in vector)) or 1.0
        return [component / norm for component in vector]

    async def aclose(self) -> None:
        """No-op — mirrors `OpenAIEmbeddingProvider.aclose()` so this fake is a
        drop-in double wherever a caller (e.g. `GET /dev/search`) closes its provider."""


__all__ = ["FakeEmbeddingProvider"]
