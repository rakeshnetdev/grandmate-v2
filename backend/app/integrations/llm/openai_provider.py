"""OpenAI adapters: embeddings (Phase 7) and chat completion (Phase 9, ADR-0006).

Domain code depends on `EmbeddingProvider`/`LLMProvider`, never on the OpenAI SDK
directly; this module is the only place that import appears, same rule the engine and
storage adapters follow.
"""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.core.config import LLMSettings, RetrievalSettings
from app.core.devinsight import SpanKind, get_recorder
from app.integrations.llm.base import CompletionRequest, CompletionResponse, TokenUsage


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


class OpenAIChatProvider:
    """`LLMProvider` backed by OpenAI's chat completions API."""

    def __init__(self, llm_settings: LLMSettings) -> None:
        self._client = AsyncOpenAI(
            api_key=llm_settings.openai_api_key.get_secret_value(),
            timeout=llm_settings.llm_request_timeout_s,
        )
        self._settings = llm_settings

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        model = request.model or self._settings.llm_model

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": (
                request.temperature
                if request.temperature is not None
                else self._settings.llm_temperature
            ),
            "max_tokens": request.max_tokens or self._settings.llm_max_tokens,
        }
        if request.response_format:
            kwargs["response_format"] = {"type": request.response_format}

        with get_recorder().span(SpanKind.LLM, "complete", model=model) as span:
            response = await self._client.chat.completions.create(**kwargs)
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            if span:
                span.set_tokens(prompt_tokens, completion_tokens)

            return CompletionResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage=TokenUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
            )

    async def aclose(self) -> None:
        """See `OpenAIEmbeddingProvider.aclose` — same reasoning."""
        await self._client.close()


class UnconfiguredLLMProvider:
    """`LLMProvider` stand-in used when `OPENAI_API_KEY` is blank (Phase 9).

    Constructing `AsyncOpenAI` with no key raises immediately — the SDK treats an empty
    key as missing credentials, not as "not needed yet". That is too strict for this
    app's own stated posture (`app/main.py`'s lifespan docstring: "development is
    permissive... Phase 1 has nothing that requires... an LLM"): most routes never touch
    an LLM at all, and the app must still start and serve them. This stands in for the
    real provider so startup never depends on a key existing, and only fails — with a
    clear, actionable message instead of a raw SDK error — if something actually tries
    to generate a completion.
    """

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured — add it to backend/.env to enable "
            "LLM-backed features (persona reports, chat)."
        )

    async def aclose(self) -> None:
        """No-op: there is no underlying HTTP client to close."""
        return None


def build_llm_provider(llm_settings: LLMSettings) -> OpenAIChatProvider | UnconfiguredLLMProvider:
    """The real provider when configured, otherwise a stand-in that fails only on use."""
    if llm_settings.is_configured:
        return OpenAIChatProvider(llm_settings)
    return UnconfiguredLLMProvider()


__all__ = [
    "OpenAIChatProvider",
    "OpenAIEmbeddingProvider",
    "UnconfiguredLLMProvider",
    "build_llm_provider",
]
