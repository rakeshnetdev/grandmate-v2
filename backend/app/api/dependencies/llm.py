"""LLM provider injection for routes (Phase 9).

Same rationale as `dependencies/patterns.py`'s opening index: the provider is
constructed once in the application lifespan (`app/main.py`) and reused for every
request rather than opening a new HTTP client per call.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.integrations.llm.base import LLMProvider


def get_llm_provider(request: Request) -> LLMProvider:
    provider: LLMProvider = request.app.state.llm_provider
    return provider


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]

__all__ = ["LLMProviderDep", "get_llm_provider"]
