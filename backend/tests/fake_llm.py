"""A scriptable fake `LLMProvider` for tests — no real network call.

Returns pre-programmed responses in order, one per `complete()` call, so a test can
script exactly what "the model" says: a well-grounded response, an ungrounded one (to
exercise the critic), or a sequence exercising the one-retry-then-fallback path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.integrations.llm.base import CompletionRequest, CompletionResponse, TokenUsage


@dataclass
class FakeLLMProvider:
    responses: list[str] = field(default_factory=list)
    model_name: str = "fake-model"
    prompt_tokens_per_call: int = 10
    completion_tokens_per_call: int = 10
    calls: list[CompletionRequest] = field(default_factory=list)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.calls.append(request)
        if not self.responses:
            raise AssertionError("FakeLLMProvider ran out of scripted responses")
        content = self.responses.pop(0)
        return CompletionResponse(
            content=content,
            model=self.model_name,
            usage=TokenUsage(
                prompt_tokens=self.prompt_tokens_per_call,
                completion_tokens=self.completion_tokens_per_call,
            ),
        )


__all__ = ["FakeLLMProvider"]
