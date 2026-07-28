"""A scriptable fake `LLMProvider` for tests — no real network call.

Returns pre-programmed responses in order, one per `complete()` call, so a test can
script exactly what "the model" says: a well-grounded response, an ungrounded one (to
exercise the critic), a sequence exercising the one-retry-then-fallback path, or (Phase
10) a list of `ToolCall`s to exercise the chat agent's tool-calling loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.integrations.llm.base import CompletionRequest, CompletionResponse, TokenUsage, ToolCall


@dataclass
class FakeLLMProvider:
    # Each entry is either plain text content, or a list of tool calls the "model"
    # requests instead of answering directly — mirrors the real provider's two response
    # shapes (`CompletionResponse.content` vs `.tool_calls`).
    responses: list[str | list[ToolCall]] = field(default_factory=list)
    model_name: str = "fake-model"
    prompt_tokens_per_call: int = 10
    completion_tokens_per_call: int = 10
    calls: list[CompletionRequest] = field(default_factory=list)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.calls.append(request)
        if not self.responses:
            raise AssertionError("FakeLLMProvider ran out of scripted responses")
        next_response = self.responses.pop(0)
        usage = TokenUsage(
            prompt_tokens=self.prompt_tokens_per_call,
            completion_tokens=self.completion_tokens_per_call,
        )
        if isinstance(next_response, list):
            return CompletionResponse(
                content="", model=self.model_name, usage=usage, tool_calls=next_response
            )
        return CompletionResponse(content=next_response, model=self.model_name, usage=usage)


__all__ = ["FakeLLMProvider"]
