"""The chat agent graph (Phase 10, ADR-0008 §"agentic retrieval"; +write_memory Phase 11).

Replaces `graphs/skeleton.py`'s placeholder nodes (Phase 1) with the real thing: intent
classification, then a tool-calling agent loop bounded by `AgentSettings`, with a
grounding guardrail gating every answer before it leaves the loop, then a best-effort
long-term-memory extraction step.

**Two nodes, not one-node-per-tool-call.** `_run_agent` runs its own bounded `while`
loop internally rather than modelling each tool call as a separate graph node with
conditional edges. LangGraph is doing real work here regardless — it is what makes the
Postgres checkpointer persist thread state across turns (project-plan.md's actual
deliverable) — but a tool call within one turn is transient scratch work the next turn
has no need to replay node-by-node, so it is simpler and no less correct to keep it as
plain control flow inside one node. `messages` only ever grows by one user turn and one
assistant turn per invocation; intra-turn tool exchanges live in a local list, never in
checkpointed state, so a long conversation's persisted size stays proportional to turn
count, not tool-call count.

**`write_memory` runs after the answer is final, as its own node.** Long-term memory
extraction is a separate concern from answering — it reads the completed (question,
answer) pair and may write to `long_term_memory`/the memory store, but it can never
change what the user was already told, and a failure there does not fail the turn. That
independence is exactly why it is its own graph node rather than folded into
`_run_agent`: two responsibilities that must never entangle get two places to change
independently.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from app.core.config import AgentSettings, LLMSettings
from app.core.devinsight import SpanKind, get_recorder
from app.db.models import Persona

# Shifted chat domain imports to function local scopes to break circular dependency chain
from app.domain.llm_usage import LLMBudgetTracker
from app.domain.memory import MemoryService
from app.domain.memory.prompts import build_extraction_messages, parse_candidate_memories
from app.integrations.llm.base import CompletionRequest, LLMProvider, Message, ToolCall
from app.orchestration.tools import TOOL_DISPATCH, TOOL_SPECS, ToolContext

# One initial attempt plus one retry if the guardrail rejects the first — same ceiling
# Phase 9's report critic uses, for the same reason: a second ungrounded attempt in a row
# is a signal to fall back, not to keep trying.
_MAX_ANSWER_ATTEMPTS = 2


def _append(existing: list[Any], incoming: list[Any]) -> list[Any]:
    """Reducer that accumulates across node executions (and, with a checkpointer,
    across separate turns) rather than overwriting — see `graphs/skeleton.py`'s original
    docstring for why this matters for `trace`, which this graph still uses unchanged."""
    return [*existing, *incoming]


class GraphState(TypedDict, total=False):
    """Shared state, checkpointed per thread.

    Only `messages` and `trace` accumulate across turns (`Annotated` reducer). Everything
    else — `context`, `citations`, `answer`, `grounded` — describes the *most recent*
    turn only and is overwritten each time: keeping every past turn's raw tool output
    forever would grow the checkpoint without bound for no benefit, since the guardrail
    and the fallback answer only ever need this turn's own findings.
    """

    # Inbound, set fresh on every invocation.
    question: str
    profile_id: str
    active_game_id: str | None
    persona: str

    # Accumulated across the thread's lifetime. An assistant entry's `citations`/
    # `grounded` (Phase 16a) ride along in the same dict as `role`/`content` rather than
    # a separate keyed structure — `dict[str, Any]`, not `dict[str, str]`, to allow it;
    # a user entry simply omits those keys.
    trace: Annotated[list[str], _append]
    messages: Annotated[list[dict[str, Any]], _append]

    # This turn only.
    intent: str | None
    context: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    answer: str | None
    grounded: bool | None


@dataclass
class ChatGraphDeps:
    """Everything the graph's nodes need beyond the checkpointed state itself:
    request-scoped resources (DB session, tool context) plus the settings that bound the
    loop."""

    llm: LLMProvider
    llm_settings: LLMSettings
    agent_settings: AgentSettings
    budget: LLMBudgetTracker
    tool_context: ToolContext
    memory: MemoryService


async def _classify_intent(state: GraphState, deps: ChatGraphDeps) -> GraphState:
    from app.domain.chat.prompts import build_intent_messages, parse_intent

    with get_recorder().span(SpanKind.GRAPH_NODE, "classify_intent") as span:
        if not await deps.budget.has_budget():
            # Loop protection doubles as the daily spend guard here too: with no budget,
            # skip classification rather than fail the turn — "explain" is a safe
            # default and the agent step still runs (and will hit the same budget check
            # again, falling back deterministically).
            if span:
                span.set(skipped="budget_exhausted")
            return {"trace": ["classify_intent"], "intent": "explain"}

        response = await deps.llm.complete(
            CompletionRequest(
                messages=build_intent_messages(state["question"]),
                model=deps.llm_settings.llm_model,
                response_format="json_object",
            )
        )
        await deps.budget.record_usage(
            response.usage.prompt_tokens, response.usage.completion_tokens
        )
        intent = parse_intent(response.content)
        if span:
            span.set(intent=intent)
        return {"trace": ["classify_intent"], "intent": intent}


async def _dispatch_tool(ctx: ToolContext, call: ToolCall) -> dict[str, Any]:
    """Never raises — a malformed or unknown tool call becomes a `{"error": ...}` result
    fed back to the model, the same "models invent plausible-looking things" posture
    `validate_line` exists for at the move-legality level."""
    fn = TOOL_DISPATCH.get(call.name)
    if fn is None:
        return {"error": f"unknown tool {call.name!r}"}
    try:
        arguments = json.loads(call.arguments) if call.arguments else {}
    except json.JSONDecodeError:
        return {"error": f"tool arguments were not valid JSON: {call.arguments!r}"}
    if not isinstance(arguments, dict):
        return {"error": "tool arguments must be a JSON object"}
    try:
        return await fn(ctx, **arguments)
    except TypeError as exc:
        return {"error": f"invalid arguments for {call.name}: {exc}"}


async def _run_agent(state: GraphState, deps: ChatGraphDeps) -> GraphState:
    from app.domain.chat.fallback import build_fallback_answer
    from app.domain.chat.guardrail import validate_answer
    from app.domain.chat.prompts import build_agent_system_message

    with get_recorder().span(SpanKind.AGENT, "run_agent", intent=state.get("intent")) as outer_span:
        persona = Persona(state["persona"])
        system_message = build_agent_system_message(
            persona, active_game_id=state.get("active_game_id")
        )
        history = [Message(role=m["role"], content=m["content"]) for m in state.get("messages", [])]
        working_messages: list[Message] = [
            system_message,
            *history,
            Message(role="user", content=state["question"]),
        ]

        turn_context: list[dict[str, Any]] = []
        tool_call_count = 0
        answer_attempts = 0
        tokens_used = 0
        final_parsed: dict[str, Any] | None = None
        grounded = False

        for _step in range(deps.agent_settings.agent_max_steps):
            if tokens_used >= deps.agent_settings.agent_token_budget:
                break
            if not await deps.budget.has_budget():
                break

            response = await deps.llm.complete(
                CompletionRequest(
                    messages=working_messages,
                    model=deps.llm_settings.llm_model,
                    response_format="json_object",
                    tools=TOOL_SPECS,
                )
            )
            tokens_used += response.usage.total
            await deps.budget.record_usage(
                response.usage.prompt_tokens, response.usage.completion_tokens
            )

            if response.tool_calls:
                working_messages.append(Message(role="assistant", tool_calls=response.tool_calls))
                for call in response.tool_calls:
                    if tool_call_count >= deps.agent_settings.agent_max_tool_calls:
                        result: dict[str, Any] = {"error": "tool call budget exhausted this turn"}
                    else:
                        result = await _dispatch_tool(deps.tool_context, call)
                        tool_call_count += 1
                    turn_context.append(
                        {"tool": call.name, "arguments": call.arguments, "result": result}
                    )
                    working_messages.append(
                        Message(role="tool", tool_call_id=call.id, content=json.dumps(result))
                    )
                continue

            answer_attempts += 1
            with get_recorder().span(SpanKind.GROUNDING, "chat.guardrail") as grounding_span:
                parsed, violations = await validate_answer(deps.tool_context, response.content)
                if grounding_span:
                    grounding_span.set(violation_count=len(violations))
            if not violations and parsed is not None:
                final_parsed = parsed
                grounded = True
                break
            if answer_attempts >= _MAX_ANSWER_ATTEMPTS:
                break
            working_messages.append(Message(role="assistant", content=response.content))
            working_messages.append(
                Message(
                    role="user",
                    content=(
                        "That answer failed grounding checks: "
                        f"{violations}. Correct it using only tool-verified facts."
                    ),
                )
            )

        if final_parsed is None:
            final_parsed = build_fallback_answer(turn_context)
            grounded = True

        if outer_span:
            outer_span.set(
                tool_call_count=tool_call_count, answer_attempts=answer_attempts, grounded=grounded
            )

        return {
            "trace": ["run_agent"],
            "messages": [
                {"role": "user", "content": state["question"]},
                {
                    "role": "assistant",
                    "content": final_parsed["answer"],
                    # Persisted alongside the message (Phase 16a) so a reloaded thread
                    # keeps citation/grounding data — previously only the live turn's
                    # `ChatTurnResponse` carried it, lost the moment history was refetched.
                    "citations": final_parsed.get("citations", []),
                    "grounded": grounded,
                },
            ],
            "context": turn_context,
            "citations": final_parsed.get("citations", []),
            "answer": final_parsed["answer"],
            "grounded": grounded,
        }


async def _write_memory(
    state: GraphState, deps: ChatGraphDeps, thread_id: str | None
) -> GraphState:
    """A best-effort side channel, never the user-visible path: a failure or an empty
    result here changes nothing about the answer already returned by `_run_agent`. Runs
    after the answer is decided, not before, so extraction judges the actual completed
    exchange rather than an in-progress one.

    Reads `profile_id` from `deps.tool_context` — the one bound, never-model-suppliable
    value (rule 14) — rather than `state["profile_id"]`, which nothing else in this graph
    actually enforces is set. `thread_id` comes from the graph's own invocation config
    (LangGraph's checkpointer thread id), the single source of truth for which
    conversation this is, instead of duplicating it into checkpointed state too.
    """
    with get_recorder().span(SpanKind.GRAPH_NODE, "write_memory") as span:
        if not await deps.budget.has_budget():
            if span:
                span.set(skipped="budget_exhausted")
            return {"trace": ["write_memory"]}

        response = await deps.llm.complete(
            CompletionRequest(
                messages=build_extraction_messages(state["question"], state.get("answer") or ""),
                model=deps.llm_settings.llm_model,
                response_format="json_object",
            )
        )
        await deps.budget.record_usage(
            response.usage.prompt_tokens, response.usage.completion_tokens
        )
        candidates = parse_candidate_memories(response.content)

        written_count = 0
        if candidates:
            written = await deps.memory.write_candidate_memories(
                deps.tool_context.profile_id,
                candidates,
                source_thread_id=uuid.UUID(thread_id) if thread_id else None,
            )
            written_count = len(written)

        if span:
            span.set(candidate_count=len(candidates), written_count=written_count)
        return {"trace": ["write_memory"]}


def build_chat_graph(deps: ChatGraphDeps, checkpointer: Any) -> Any:
    """Compile the chat graph bound to `deps` and `checkpointer`.

    Returns the compiled graph, not the builder — same reasoning as the Phase 1
    skeleton: callers should not be able to mutate wiring post-construction.
    """
    builder = StateGraph(GraphState)

    # Plain closures, not lambdas: LangGraph decides sync-vs-async dispatch from
    # `inspect.iscoroutinefunction`, which a `lambda: await_something()` fails (it is a
    # regular function that *returns* a coroutine, not itself a coroutine function) —
    # these `async def`s are the real thing.
    async def _classify_intent_node(state: GraphState) -> GraphState:
        return await _classify_intent(state, deps)

    async def _run_agent_node(state: GraphState) -> GraphState:
        return await _run_agent(state, deps)

    async def _write_memory_node(state: GraphState, config: RunnableConfig) -> GraphState:
        thread_id = config.get("configurable", {}).get("thread_id")
        return await _write_memory(state, deps, thread_id)

    builder.add_node("classify_intent", _classify_intent_node)
    builder.add_node("run_agent", _run_agent_node)
    builder.add_node("write_memory", _write_memory_node)

    builder.set_entry_point("classify_intent")
    builder.add_edge("classify_intent", "run_agent")
    builder.add_edge("run_agent", "write_memory")
    builder.add_edge("write_memory", END)

    return builder.compile(checkpointer=checkpointer)


__all__ = ["ChatGraphDeps", "GraphState", "build_chat_graph"]
