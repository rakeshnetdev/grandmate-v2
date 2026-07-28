"""LLM and embedding provider injection for routes (Phase 9, Phase 10).

Same rationale as `dependencies/patterns.py`'s opening index: both providers are
constructed once in the application lifespan (`app/main.py`) and reused for every
request rather than opening a new HTTP client per call.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.integrations.llm.base import EmbeddingProvider, LLMProvider


def get_llm_provider(request: Request) -> LLMProvider:
    provider: LLMProvider = request.app.state.llm_provider
    return provider


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    provider: EmbeddingProvider = request.app.state.embedding_provider
    return provider


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
EmbeddingProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]

__all__ = ["EmbeddingProviderDep", "LLMProviderDep", "get_embedding_provider", "get_llm_provider"]
