"""OpenAI embedding adapter (Phase 7, ADR-0006/ADR-0008).

Implements only the `EmbeddingProvider` half of the provider protocol
(`app/integrations/llm/base.py`) — chat completion (`LLMProvider`) lands at Phase 9/10
once personas and chat need it. Domain code depends on `EmbeddingProvider`, never on
the OpenAI SDK directly; this module is the only place that import appears for
embeddings, same rule the engine and storage adapters follow.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import LLMSettings, RetrievalSettings


class OpenAIEmbeddingProvider:
    """`EmbeddingProvider` backed by OpenAI's embeddings API."""

    def __init__(self, llm_settings: LLMSettings, retrieval_settings: RetrievalSettings) -> None:
        self._client = AsyncOpenAI(
            api_key=llm_settings.openai_api_key.get_secret_value(),
            timeout=llm_settings.llm_request_timeout_s,
        )
        self._model = retrieval_settings.embed_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Order of results matches order of inputs."""
        if not texts:
            return []
        response = await self._client.embeddings.create(model=self._model, input=texts)
        # Defensive, not paranoid: nothing guarantees the SDK's `response.data` list is
        # already in input order across every client version, but every item carries
        # its own `.index` back to the input batch, so sorting on it is free insurance.
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]

    async def aclose(self) -> None:
        """Close the underlying HTTP client.

        Not load-bearing for a long-lived FastAPI process (the client lives for the
        app's lifetime), but short-lived callers — scripts, the eval harness — leave an
        unclosed transport behind without it, which `pytest`'s `filterwarnings =
        ["error"]` turns into a real test failure (`ResourceWarning`), not just noise.
        """
        await self._client.close()


__all__ = ["OpenAIEmbeddingProvider"]
