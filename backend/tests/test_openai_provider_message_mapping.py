"""`_to_openai_message`: the provider-agnostic `Message` -> OpenAI chat-completions dict
mapping (Phase 10, tool calling).

Pure and network-free, unlike the rest of `OpenAIChatProvider` — this project does not
otherwise unit-test the OpenAI SDK wrapper itself (see the lack of any
`OpenAIChatProvider`/`build_llm_provider` test from Phase 9: real-provider correctness is
verified live, not mocked), but the shape this function builds is new logic with no other
coverage at all once `FakeLLMProvider` stands in everywhere else, so it is worth checking
directly rather than trusting it untested until the first real tool-calling API call.
"""

from __future__ import annotations

from app.integrations.llm.base import Message, ToolCall
from app.integrations.llm.openai_provider import _to_openai_message


def test_a_plain_message_carries_role_and_content() -> None:
    result = _to_openai_message(Message(role="user", content="hello"))

    assert result == {"role": "user", "content": "hello"}


def test_an_assistant_message_with_tool_calls_has_no_text_but_carries_the_calls() -> None:
    call = ToolCall(id="call-1", name="lookup_opening", arguments='{"epd": "x"}')

    result = _to_openai_message(Message(role="assistant", tool_calls=[call]))

    assert result["content"] is None
    assert result["tool_calls"] == [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "lookup_opening", "arguments": '{"epd": "x"}'},
        }
    ]


def test_a_tool_result_message_carries_its_call_id() -> None:
    result = _to_openai_message(
        Message(role="tool", content='{"result": null}', tool_call_id="call-1")
    )

    assert result["tool_call_id"] == "call-1"
    assert result["content"] == '{"result": null}'
