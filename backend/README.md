# GrandMate Backend

FastAPI application. Managed with `uv`.

## Setup

```bash
cp .env.example .env
uv sync --extra dev
uv run python -m app
```

Endpoints: `/health`, `/ready`, and `/docs` (development only).

Start the server with `python -m app`, not the `uvicorn` CLI. The CLI cannot see
`app/core/config`, so it ignores `API_HOST` / `API_PORT` and binds uvicorn's own default
port instead. `app/__main__.py` reads the settings and passes them to the server, which is
what keeps `.env` authoritative for the bind address. Reload is enabled when
`APP_ENV=development`.

## Layout

```
app/
  api/
    routes/          Thin HTTP handlers. They delegate; they do not decide.
    dependencies/    FastAPI providers (settings, later auth and permissions)
  core/
    config/          The ONLY place environment variables are read
    logging.py       structlog setup
  domain/            Business rules, one module per bounded concern (see domain/README.md)
  services/          Application services orchestrating domain + repositories
  repositories/      Persistence. All database access lives here.
  workers/           Background jobs. Idempotent by contract.
  integrations/      Adapters: llm, engine, lichess, chesscom, vectorstore
  orchestration/
    graphs/          LangGraph state graphs
    agents/          Agent definitions (Phase 13)
    tools/           Tool implementations shared by agents AND the MCP server
    jobs/            Job definitions
  mcp/               MCP server (Phase 12)
  schemas/           Pydantic schemas for the API boundary
tests/
```

`orchestration/tools/` is shared between the LangGraph agents and the MCP server on
purpose. One capability, one implementation, two surfaces — see
[ADR-0010](../final_docs/v2/adr/0010-mcp-tool-interface.md).

## Configuration

Every setting is read through `app/core/config`. Domain code receives a settings object
or one of its groups; it never touches `os.environ`.

```python
from app.core.config import get_settings

settings = get_settings()
settings.engine.engine_depth  # 12
settings.llm.llm_model  # "gpt-4o-mini"
```

Secrets are `SecretStr`, so they do not appear in reprs, logs, or tracebacks. There is a
test asserting exactly that.

Two defaults that look arbitrary but are not:

- `ENGINE_THREADS=1` — multi-threaded Stockfish is not reproducible across runs, and
  Phase 5 requires identical classifications on repeated runs. Parallelism comes from
  running several games at once.
- `LLM_TEMPERATURE=0.2` — this is an explanation system over already-computed facts, not
  a creative one.

Full contract: [configuration.md](../final_docs/v2/configuration.md).

## Testing

```bash
uv run pytest                          # all
uv run pytest --cov=app                # with coverage
uv run pytest tests/test_config.py -v  # one file
```

Tests are **hermetic**: `conftest.py` strips every GrandMate environment variable and
disables `.env` loading, so results do not depend on what a developer happens to have
exported. That isolation is not incidental — it caught a real bug during Phase 1, where an
ambient `OPENAI_API_KEY` made a configuration test pass that should have failed.

## Developer insight

In-process request tracing for debugging (ADR-0013). Instrument any code path — no
`if enabled` guard needed, because the recorder is a no-op object when disabled:

```python
from app.core.devinsight import SpanKind, get_recorder

with get_recorder().span(SpanKind.ENGINE, "evaluate", ply=23) as span:
    result = engine.analyse(position)
    if span:
        span.set(eval_cp=result.score)
```

Read traces at `GET /api/v1/dev/traces` and `/api/v1/dev/traces/{id}`, or open the panel
at the bottom of the frontend. Responses carry an `X-Trace-Id` header; the trace itself is
never embedded in the response body.

Two guarantees, both requested explicitly:

- **No LLM cost.** Token counts come from the provider's own `usage` field on a response
  already paid for. Never a tokenizer, never a count-tokens call. A test asserts the
  recorder module has no provider import at all.
- **No meaningful latency.** A span is a `perf_counter()` read and a list append. Traces
  are serialised only when someone fetches one.

Production is hard-gated: the routes are not mounted, the middleware is not installed, and
`DEV_INSIGHT_CAPTURE_PROMPTS` is forced off regardless of configuration.

## Architectural boundary

`tests/test_layer_boundaries.py` fails the build if the deterministic chess core
(`domain/games`, `analysis`, `patterns`, `aggregation`) imports LLM or orchestration code.

The rule is easy to agree with and easy to erode one convenient import at a time, so it is
checked mechanically. The checker has its own self-tests, because until Phase 4 there are
no core modules to scan and the check would otherwise pass vacuously while broken.

See [ADR-0003](../final_docs/v2/adr/0003-deterministic-core-vs-llm-layer.md).

## Quality gate

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest
```

mypy runs in strict mode. CI runs each step separately so a lint failure still reports the
test result.
