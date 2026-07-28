"""LLM provider interface (ADR-0006).

Domain code depends on this Protocol, never on a vendor SDK. The interface exists from
Phase 1 — before any provider is implemented — because retrofitting it at Phase 13,
across agents, personas, reports, and evaluation judges, would be expensive. Adding it
now costs almost nothing.

Guardrails (timeout, max tokens, retry, token accounting, daily ceiling) belong in the
adapter implementations so they cannot be forgotten at a call site.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """One function-call request the model made in response to an offered tool.

    ``arguments`` is the raw JSON string exactly as the provider returned it, not a
    parsed dict — a malformed-arguments response is something the caller (the agent
    loop) needs to detect and handle, not something this layer should silently paper
    over by returning `{}` on a parse failure.
    """

    id: str
    name: str
    arguments: str


class ToolSpec(BaseModel):
    """A tool definition offered to the model. ``parameters`` is a JSON Schema object,
    the same shape every mainstream provider's function-calling API expects."""

    name: str
    description: str
    parameters: dict[str, Any]


class Message(BaseModel):
    """A single chat message.

    ``content`` is optional because an assistant message that only calls tools
    (``tool_calls`` set) carries no text. ``tool_calls`` and ``tool_call_id`` exist for
    Phase 10's tool-calling agent loop: an assistant message requesting tools sets
    ``tool_calls``; the corresponding result message sets ``role="tool"`` and
    ``tool_call_id`` back to the call it answers.
    """

    role: str
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class CompletionRequest(BaseModel):
    """A request to the provider.

    ``model`` is optional so callers normally inherit the configured default and only
    override deliberately — for example, the evaluation harness pointing a judge at a
    different model than the one being judged.

    ``response_format`` is optional and provider-interpreted (OpenAI's adapter maps
    ``"json_object"`` to its own ``response_format`` parameter). Added for Phase 9's
    report generation, which needs syntactically-guaranteed JSON so the grounding critic
    has something structured to validate rather than free text to pattern-match.

    ``tools`` is optional and added for Phase 10: when set, the provider offers these as
    callable functions and the response may carry ``tool_calls`` instead of (or beside)
    text content.
    """

    messages: list[Message]
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: str | None = None
    tools: list[ToolSpec] | None = None


class TokenUsage(BaseModel):
    """Token accounting for cost tracking and budget enforcement."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class CompletionResponse(BaseModel):
    """A provider response.

    ``content`` stays a plain ``str`` (never ``None``, defaulting to ``""``) so every
    existing caller that only reads text keeps working unchanged — a tool-calling
    response with no text content is the one case that produces ``""``, distinguishable
    from a real answer by checking ``tool_calls`` instead.
    """

    content: str
    model: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    tool_calls: list[ToolCall] | None = None


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
    "ToolCall",
    "ToolSpec",
]
