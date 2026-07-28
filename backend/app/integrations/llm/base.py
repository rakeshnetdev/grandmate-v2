"""LLM provider interface (ADR-0006).

Domain code depends on this Protocol, never on a vendor SDK. The interface exists from
Phase 1 — before any provider is implemented — because retrofitting it at Phase 13,
across agents, personas, reports, and evaluation judges, would be expensive. Adding it
now costs almost nothing.

Guardrails (timeout, max tokens, retry, token accounting, daily ceiling) belong in the
adapter implementations so they cannot be forgotten at a call site.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single chat message."""

    role: str
    content: str


class CompletionRequest(BaseModel):
    """A request to the provider.

    ``model`` is optional so callers normally inherit the configured default and only
    override deliberately — for example, the evaluation harness pointing a judge at a
    different model than the one being judged.

    ``response_format`` is optional and provider-interpreted (OpenAI's adapter maps
    ``"json_object"`` to its own ``response_format`` parameter). Added for Phase 9's
    report generation, which needs syntactically-guaranteed JSON so the grounding critic
    has something structured to validate rather than free text to pattern-match.
    """

    messages: list[Message]
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: str | None = None


class TokenUsage(BaseModel):
    """Token accounting for cost tracking and budget enforcement."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class CompletionResponse(BaseModel):
    """A provider response."""

    content: str
    model: str
    usage: TokenUsage = Field(default_factory=TokenUsage)


@runtime_checkable
class LLMProvider(Protocol):
    """What the rest of the application may assume about an LLM."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate a completion."""
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Embedding generation, used by the retrieval layer from Phase 7."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Order of results matches order of inputs."""
        ...


__all__ = [
    "CompletionRequest",
    "CompletionResponse",
    "EmbeddingProvider",
    "LLMProvider",
    "Message",
    "TokenUsage",
]
