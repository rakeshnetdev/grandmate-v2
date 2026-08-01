"""The multi-agent supervisor graph (Phase 13, `rag-architecture.md` §7, D-016/D-029).

**This graph exists to be measured against Phase 10's single-agent graph
(`graphs/chat.py`), not to replace it yet.** Whether it becomes the live chat path is
Phase 13's own exit criterion: multi-agent must beat the single-agent baseline on the
evaluation set (`evals/harness/agent_trajectory_eval.py`), or the result is recorded and
`chat.py` keeps serving real traffic. Nothing here is wired into `ChatService` — that
would be promoting an unproven architecture ahead of the evidence the phase is supposed
to produce.

**Plan-once, not loop-and-return.** The supervisor classifies routing exactly once per
turn (`needs_retrieval`, `needs_analysis`) rather than repeatedly deciding "what next"
after every specialist — simpler to reason about, simpler to test, and suffices for the
roster `rag-architecture.md` §7 specifies. The one real cycle in the graph is
coach <-> critic, bounded by `_MAX_COACH_ATTEMPTS`, the same one-retry-then-fallback shape
`chat.py`'s single loop already uses for the identical reason: a second rejected attempt
in a row is a signal to degrade, not to keep spending budget hoping for a better one.

**The critic is `validate_answer`, unchanged from Phase 10 — not a new LLM judge.**
`rag-architecture.md` §7 lists the critic's tools as `validate_line`/`get_game_analysis`,
which is exactly what `domain/chat/guardrail.py`'s deterministic checks already reach.
Building a second, LLM-based critic would both duplicate a capability (`claude.md` rule
13) and contradict rule 8: chess truth is never asserted by an LLM alone, including an
LLM playing critic.

**Ceilings are a shared, cross-turn budget, not one guardrail owning it.** `steps_taken`
means the same thing `AgentSettings.agent_max_steps` means for the single agent — one LLM
completion call, anywhere in the turn — just threaded through five possible callers
(supervisor, retriever, chess analyst, coach x up to 2 attempts) instead of one loop's own
counter. Every node reads the running totals out of state and writes back the new sum;
there is deliberately no central "budget enforcer" node, because the enforcement has to
happen *before* each would-be LLM call, inside whichever node is about to make it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from app.core.config import LLMSettings, MultiAgentSettings
from app.core.devinsight import SpanKind, get_recorder
from app.db.models import Persona
from app.domain.chat.fallback import build_fallback_answer
from app.domain.chat.guardrail import validate_answer
from app.domain.chat.multi_agent_prompts import (
    build_chess_analyst_system_message,
    build_coach_system_message,
    build_retriever_system_message,
    build_supervisor_messages,
    parse_supervisor_plan,
)
from app.domain.llm_usage import LLMBudgetTracker
from app.integrations.llm.base import CompletionRequest, LLMProvider, Message, ToolCall
from app.orchestration.agents import CHESS_ANALYST, RETRIEVER
from app.orchestration.agents.specs import AgentSpec
from app.orchestration.tools import ToolContext
from app.orchestration.tools.registry import ToolFn

# Same ceiling `chat.py`'s single loop uses, same reason: one retry after a rejected
# answer, then degrade — a second ungrounded draft in a row means retrying is unlikely to
# help before the caller notices the delay.
_MAX_COACH_ATTEMPTS = 2


def _append(existing: list[Any], incoming: list[Any]) -> list[Any]:
    """Accumulates across node executions, same reducer shape as `graphs/chat.py`'s own
    `_append` — redefined locally rather than imported so this module has no dependency
    on `chat.py`'s internals, which are private to that graph."""
    return [*existing, *incoming]


class MultiAgentState(TypedDict, total=False):
    """Shared state, the "handoff contract" between agents.

    `retrieval_context`/`analysis_context` are exactly what they sound like: read-only
    facts a specialist gathered, for the coach to phrase from. The coach never mutates
    them and never fetches its own — that boundary *is* the handoff contract.
    """

    # Inbound, set fresh on every invocation.
    question: str
    active_game_id: str | None
    persona: str

    # Accumulated across the graph run.
    trace: Annotated[list[str], _append]
    # `dict[str, Any]`, matching `graphs/chat.py`: a persisted message carries
    # `citations` (a list) and `grounded` (a bool) beside its text, so the narrower
    # `dict[str, str]` this used to claim never described what is actually written.
    messages: Annotated[list[dict[str, Any]], _append]

    # Supervisor's routing decision, this turn only.
    needs_retrieval: bool | None
    needs_analysis: bool | None

    # Specialist output, this turn only — read-only input to the coach.
    retrieval_context: list[dict[str, Any]]
    analysis_context: list[dict[str, Any]]

    # Coach/critic cycle state.
    draft_raw: str | None
    coach_attempts: int
    skip_critic: bool
    violations: list[str]

    # Final answer, set once by whichever node accepts it (critic, or a budget-exhausted
    # fallback from coach directly).
    answer: str | None
    citations: list[dict[str, Any]]
    grounded: bool | None

    # Shared cross-turn ceilings — see module docstring.
    steps_taken: int
    tokens_used: int
    tool_call_count: int


@dataclass
class MultiAgentGraphDeps:
    """Everything the graph's nodes need beyond checkpointed state: request-scoped
    resources plus the settings that bound the whole turn."""

    llm: LLMProvider
    llm_settings: LLMSettings
    multi_agent_settings: MultiAgentSettings
    budget: LLMBudgetTracker
    tool_context: ToolContext


def _combined_context(state: MultiAgentState) -> list[dict[str, Any]]:
    return [*state.get("retrieval_context", []), *state.get("analysis_context", [])]


async def _ceilings_exceeded(steps_taken: int, tokens_used: int, deps: MultiAgentGraphDeps) -> bool:
    """Whether any shared, cross-turn ceiling is already spent — checked before every
    would-be LLM call, never after. `has_budget()` is the same daily-spend guard
    `chat.py` checks; the other two are this turn's own step/token ceilings."""
    if steps_taken >= deps.multi_agent_settings.multi_agent_max_steps:
        return True
    if tokens_used >= deps.multi_agent_settings.multi_agent_token_budget:
        return True
    return not await deps.budget.has_budget()


async def _ceiling_exceeded(state: MultiAgentState, deps: MultiAgentGraphDeps) -> bool:
    """`_ceilings_exceeded` reading its two numeric inputs out of graph state — the
    entry point every node checks at its own start, before state has been mutated for
    the current call."""
    return await _ceilings_exceeded(state.get("steps_taken", 0), state.get("tokens_used", 0), deps)


async def _dispatch_tool(
    ctx: ToolContext, call: ToolCall, dispatch: dict[str, ToolFn]
) -> dict[str, Any]:
    """Same never-raises contract as `chat.py`'s `_dispatch_tool`, parameterised over a
    specialist's own tool subset rather than the global registry — a retriever call for
    `get_game_analysis` is exactly as invalid as a call to a tool that does not exist at
    all, since that tool was never offered to it in the first place."""
    fn = dispatch.get(call.name)
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


async def _supervisor(state: MultiAgentState, deps: MultiAgentGraphDeps) -> MultiAgentState:
    with get_recorder().span(SpanKind.GRAPH_NODE, "supervisor") as span:
        # Reset turn-level ceilings on the very first node of the new turn
        # to prevent leakage from previous turns stored in the checkpoint.
        state = {**state, "steps_taken": 0, "tokens_used": 0, "tool_call_count": 0}
        steps_taken = 0

        if await _ceiling_exceeded(state, deps):
            # No budget left even to classify — route straight to the coach with
            # whatever context exists (none, this early), matching `chat.py`'s
            # `_classify_intent` skip-on-exhaustion posture.
            if span:
                span.set(skipped="budget_exhausted")
            return {
                "trace": ["supervisor"],
                "steps_taken": 0,
                "tokens_used": 0,
                "tool_call_count": 0,
                "needs_retrieval": False,
                "needs_analysis": False,
                # Seeded here because the supervisor always runs first — a specialist
                # that routing never visits at all (as opposed to one that ran and
                # found nothing) must still leave its context key present, not absent,
                # so every caller can read `result["retrieval_context"]` unconditionally
                # rather than needing `.get(..., [])` to guard against a skipped agent.
                "retrieval_context": [],
                "analysis_context": [],
            }

        response = await deps.llm.complete(
            CompletionRequest(
                messages=build_supervisor_messages(state["question"]),
                model=deps.llm_settings.llm_model,
                response_format="json_object",
            )
        )
        await deps.budget.record_usage(
            response.usage.prompt_tokens, response.usage.completion_tokens
        )
        plan = parse_supervisor_plan(response.content)
        if span:
            span.set(**plan)
        return {
            "trace": ["supervisor"],
            "steps_taken": steps_taken + 1,
            "tokens_used": state.get("tokens_used", 0) + response.usage.total,
            "retrieval_context": [],
            "analysis_context": [],
            "needs_retrieval": plan["needs_retrieval"],
            "needs_analysis": plan["needs_analysis"],
        }


async def _run_specialist(
    state: MultiAgentState,
    deps: MultiAgentGraphDeps,
    spec: AgentSpec,
    system_message: Message,
) -> tuple[int, int, int, list[dict[str, Any]]]:
    """The bounded tool-calling loop shared by the retriever and chess-analyst nodes —
    identical shape to `chat.py`'s single agent loop, restricted to `spec`'s own tool
    subset and sharing this turn's ceilings with every other agent rather than owning a
    private budget.

    Returns `(steps_taken, tokens_used, tool_call_count, gathered_context)` — the
    specialist's own contribution to the turn's running totals, for the caller to fold
    back into state exactly once.
    """
    steps_taken = state.get("steps_taken", 0)
    tokens_used = state.get("tokens_used", 0)
    tool_call_count = state.get("tool_call_count", 0)
    context: list[dict[str, Any]] = []

    working_messages = [system_message, Message(role="user", content=state["question"])]

    while not await _ceilings_exceeded(steps_taken, tokens_used, deps):
        response = await deps.llm.complete(
            CompletionRequest(
                messages=working_messages,
                model=deps.llm_settings.llm_model,
                response_format="json_object",
                tools=list(spec.tool_specs),
            )
        )
        steps_taken += 1
        tokens_used += response.usage.total
        await deps.budget.record_usage(
            response.usage.prompt_tokens, response.usage.completion_tokens
        )

        if not response.tool_calls:
            break

        working_messages.append(Message(role="assistant", tool_calls=response.tool_calls))
        for call in response.tool_calls:
            if tool_call_count >= deps.multi_agent_settings.multi_agent_max_tool_calls:
                result: dict[str, Any] = {"error": "tool call budget exhausted this turn"}
            else:
                result = await _dispatch_tool(deps.tool_context, call, spec.tool_dispatch)
                tool_call_count += 1
            context.append({"tool": call.name, "arguments": call.arguments, "result": result})
            working_messages.append(
                Message(role="tool", tool_call_id=call.id, content=json.dumps(result))
            )

    return steps_taken, tokens_used, tool_call_count, context


async def _retriever(state: MultiAgentState, deps: MultiAgentGraphDeps) -> MultiAgentState:
    with get_recorder().span(SpanKind.AGENT, "retriever") as span:
        if await _ceiling_exceeded(state, deps):
            if span:
                span.set(skipped="budget_exhausted")
            return {"trace": ["retriever"], "retrieval_context": []}

        steps_taken, tokens_used, tool_call_count, context = await _run_specialist(
            state, deps, RETRIEVER, build_retriever_system_message()
        )
        if span:
            span.set(tool_call_count=len(context))
        return {
            "trace": ["retriever"],
            "steps_taken": steps_taken,
            "tokens_used": tokens_used,
            "tool_call_count": tool_call_count,
            "retrieval_context": context,
        }


async def _chess_analyst(state: MultiAgentState, deps: MultiAgentGraphDeps) -> MultiAgentState:
    with get_recorder().span(SpanKind.AGENT, "chess_analyst") as span:
        if await _ceiling_exceeded(state, deps):
            if span:
                span.set(skipped="budget_exhausted")
            return {"trace": ["chess_analyst"], "analysis_context": []}

        steps_taken, tokens_used, tool_call_count, context = await _run_specialist(
            state, deps, CHESS_ANALYST, build_chess_analyst_system_message()
        )
        if span:
            span.set(tool_call_count=len(context))
        return {
            "trace": ["chess_analyst"],
            "steps_taken": steps_taken,
            "tokens_used": tokens_used,
            "tool_call_count": tool_call_count,
            "analysis_context": context,
        }


async def _coach(state: MultiAgentState, deps: MultiAgentGraphDeps) -> MultiAgentState:
    with get_recorder().span(SpanKind.AGENT, "coach") as span:
        coach_attempts = state.get("coach_attempts", 0) + 1
        context = _combined_context(state)

        if await _ceiling_exceeded(state, deps):
            # No budget left to phrase anything further — degrade to the deterministic,
            # tautologically-grounded fallback directly, same as `chat.py`s own
            # `_run_agent` does when its loop exhausts without a grounded answer.
            # `skip_critic` is set because a fallback built entirely from tool results
            # already shown to be real needs no further verification.
            fallback = build_fallback_answer(context)
            if span:
                span.set(skipped="budget_exhausted")
            return {
                "trace": ["coach"],
                "coach_attempts": coach_attempts,
                "answer": fallback["answer"],
                "citations": fallback.get("citations", []),
                "grounded": True,
                "skip_critic": True,
                "messages": [
                    {"role": "user", "content": state["question"]},
                    {
                        "role": "assistant",
                        "content": fallback["answer"],
                        "citations": fallback.get("citations", []),
                        "grounded": True,
                    },
                ],
            }

        persona = Persona(state["persona"])
        system_message = build_coach_system_message(
            persona, active_game_id=state.get("active_game_id"), context=context
        )
        violations = state.get("violations")
        follow_up = (
            Message(
                role="user",
                content=(
                    f"Your previous answer failed grounding checks: {violations}. Correct "
                    "it using only the context already provided; do not invent new facts."
                ),
            )
            if violations
            else Message(role="user", content=state["question"])
        )

        response = await deps.llm.complete(
            CompletionRequest(
                messages=[system_message, follow_up],
                model=deps.llm_settings.llm_model,
                response_format="json_object",
            )
        )
        await deps.budget.record_usage(
            response.usage.prompt_tokens, response.usage.completion_tokens
        )
        if span:
            span.set(attempt=coach_attempts)
        return {
            "trace": ["coach"],
            "steps_taken": state.get("steps_taken", 0) + 1,
            "tokens_used": state.get("tokens_used", 0) + response.usage.total,
            "coach_attempts": coach_attempts,
            "draft_raw": response.content,
            "skip_critic": False,
        }


async def _critic(state: MultiAgentState, deps: MultiAgentGraphDeps) -> MultiAgentState:
    """Verifies the coach's draft against deterministic analysis via `validate_answer`
    (Phase 10, unchanged) — see the module docstring for why this is not a second LLM
    judge. Makes no LLM call and needs no budget check of its own."""
    with get_recorder().span(SpanKind.GROUNDING, "critic") as span:
        parsed, violations = await validate_answer(deps.tool_context, state.get("draft_raw") or "")
        if span:
            span.set(violation_count=len(violations))

        if not violations and parsed is not None:
            return {
                "trace": ["critic"],
                "answer": parsed["answer"],
                "citations": parsed.get("citations", []),
                "grounded": True,
                "messages": [
                    {"role": "user", "content": state["question"]},
                    {
                        "role": "assistant",
                        "content": parsed["answer"],
                        "citations": parsed.get("citations", []),
                        "grounded": True,
                    },
                ],
            }

        if state.get("coach_attempts", 0) >= _MAX_COACH_ATTEMPTS:
            fallback = build_fallback_answer(_combined_context(state))
            return {
                "trace": ["critic"],
                "answer": fallback["answer"],
                "citations": fallback.get("citations", []),
                "grounded": True,
                "messages": [
                    {"role": "user", "content": state["question"]},
                    {
                        "role": "assistant",
                        "content": fallback["answer"],
                        "citations": fallback.get("citations", []),
                        "grounded": True,
                    },
                ],
            }

        return {"trace": ["critic"], "grounded": False, "violations": violations}


def _route_after_supervisor(state: MultiAgentState) -> str:
    if state.get("needs_retrieval"):
        return "retriever"
    if state.get("needs_analysis"):
        return "chess_analyst"
    return "coach"


def _route_after_retriever(state: MultiAgentState) -> str:
    return "chess_analyst" if state.get("needs_analysis") else "coach"


def _route_after_coach(state: MultiAgentState) -> str | Any:
    return END if state.get("skip_critic") else "critic"


def _route_after_critic(state: MultiAgentState) -> str | Any:
    return END if state.get("grounded") else "coach"


def build_multi_agent_graph(deps: MultiAgentGraphDeps, checkpointer: Any) -> Any:
    """Compile the supervisor graph bound to `deps` and `checkpointer` — same
    compiled-not-builder return convention as `build_chat_graph`."""
    builder = StateGraph(MultiAgentState)

    async def _supervisor_node(state: MultiAgentState) -> MultiAgentState:
        return await _supervisor(state, deps)

    async def _retriever_node(state: MultiAgentState) -> MultiAgentState:
        return await _retriever(state, deps)

    async def _chess_analyst_node(state: MultiAgentState) -> MultiAgentState:
        return await _chess_analyst(state, deps)

    async def _coach_node(state: MultiAgentState) -> MultiAgentState:
        return await _coach(state, deps)

    async def _critic_node(state: MultiAgentState) -> MultiAgentState:
        return await _critic(state, deps)

    builder.add_node("supervisor", _supervisor_node)
    builder.add_node("retriever", _retriever_node)
    builder.add_node("chess_analyst", _chess_analyst_node)
    builder.add_node("coach", _coach_node)
    builder.add_node("critic", _critic_node)

    builder.set_entry_point("supervisor")
    builder.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {"retriever": "retriever", "chess_analyst": "chess_analyst", "coach": "coach"},
    )
    builder.add_conditional_edges(
        "retriever", _route_after_retriever, {"chess_analyst": "chess_analyst", "coach": "coach"}
    )
    builder.add_edge("chess_analyst", "coach")
    builder.add_conditional_edges("coach", _route_after_coach, {"critic": "critic", END: END})
    builder.add_conditional_edges("critic", _route_after_critic, {"coach": "coach", END: END})

    return builder.compile(checkpointer=checkpointer)


__all__ = ["MultiAgentGraphDeps", "MultiAgentState", "build_multi_agent_graph"]
