# ADR-0006 — LLM Provider Abstraction, `gpt-4o-mini` Default

- **Status**: Accepted
- **Date**: 2026-07-25
- **Phase**: 0
- **Deciders**: Project owner

## Context

The system needs an LLM for explanation, persona rendering, agent orchestration, and
evaluation judging. The owner has an OpenAI API key and chose `gpt-4o-mini` as the
default. Model capability and pricing move quickly, and the project spans 19 phases, so
the model chosen today will very likely not be the model running at Phase 18.

## Decision

All model access goes through a provider interface in `integrations/llm/`. Domain code
never imports a vendor SDK.

Default configuration: `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini`, temperature 0.2.
The API key lives in `.env` and is supplied by the owner at Phase 1.

Separate model slots are configurable so roles can diverge without code changes:
- `LLM_MODEL` — chat and explanation
- `EMBED_MODEL` — embeddings
- a judge model for evaluation, configured independently

Guardrails at the interface, not at call sites: request timeout, max tokens, retry with
backoff, token accounting, and a daily ceiling.

## Rationale

`gpt-4o-mini` is a reasonable default for this workload. Most model calls are explanation
and rephrasing over context that has already been assembled deterministically — the hard
reasoning is done by Stockfish and the detectors. Paying frontier-model prices for
"describe this fork in kid-friendly language" would be poor value.

The abstraction matters more than the choice. Nineteen phases is long enough that the
default will change, and possibly the vendor too. Putting the interface in on day one
costs almost nothing; retrofitting it at Phase 13 across agents, personas, reports, and
evaluation judges would be expensive.

The separate judge model slot is deliberate. Using the same model to generate and to judge
measures self-consistency rather than correctness, so the evaluation harness needs to be
able to point at a different model.

One note for the record: the request specified "gpt-40-min", read as `gpt-4o-mini`.
Confirmation is tracked as open question Q-1 and must be resolved before the Phase 1 key
setup.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Direct OpenAI SDK calls in domain code | Vendor lock-in; a model change becomes a refactor |
| LiteLLM as the abstraction, as in the reference app | Viable, but a thin owned interface is easier to test and reason about; can be adopted later behind the same interface |
| A frontier model as default | Cost not justified when deterministic components do the reasoning |
| Multiple providers with automatic fallback | Premature; adds failure modes before there is a reliability problem to solve |

## Consequences

### Positive
- Model swap is a configuration change
- Guardrails enforced in one place
- Evaluation can judge with a different model than it evaluates
- Token accounting is centralised

### Negative
- A thin layer of indirection over the vendor SDK
- Provider-specific capabilities need explicit interface support to be usable

### Follow-up required
- Phase 1: confirm the model id with the owner; owner adds `OPENAI_API_KEY` to `.env`; set `LLM_DAILY_TOKEN_CEILING` (Q-4)
- Phase 16: select and pin the judge model

## References
- `final_docs/v2/configuration.md` — LLM variables
- Decision D-005
