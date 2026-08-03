# GrandMate v2

A chess analysis and coaching platform. Ingests games from PGN files, Lichess, and
Chess.com; enriches each one with deterministic engine-backed analysis; aggregates
patterns across many games; and explains the results differently depending on who is
asking.

Architecturally it is an **agentic RAG system built on a deterministic chess core**. The
core computes what is true about a game. The agent layer decides what to retrieve and how
to say it. Neither does the other's job — see
[ADR-0003](final_docs/v2/adr/0003-deterministic-core-vs-llm-layer.md).

**Status**: Phase 1 complete (engineering foundation). Phase 2 next.

## Layout

```
grandmate-v2/
  backend/      FastAPI + uv. Analysis core, retrieval, agents, MCP server.
  frontend/     Vite + React + Tailwind + shadcn/ui. Feature-driven.
  final_docs/   Architecture decisions, phase reports, evaluation strategy.
                A git submodule -> rakeshnetdev/grandmate_final_docs (private).
  .github/      Path-scoped CI, issue and PR templates.
```

Backend and frontend are independently toolchained with no shared dependency graph. The
only coupling is a typed API contract. See
[ADR-0001](final_docs/v2/adr/0001-monorepo-with-hard-boundaries.md).

## Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| Python | 3.11+ | Backend |
| [uv](https://docs.astral.sh/uv/) | 0.11+ | Python dependency and script running |
| Node | 22+ | Frontend |
| Stockfish | any recent | Engine analysis (Phase 5 onward) |
| Docker | optional | Containerised dev, Supabase CLI |

```bash
brew install uv node stockfish
```

## Getting started

```bash
# Backend
cd backend
cp .env.example .env
uv sync --extra dev
uv run python -m app                      # http://localhost:7575

# Frontend, in a second terminal
cd frontend
cp .env.example .env
npm install
npm run dev                               # http://localhost:3535
```

The home page shows a backend connectivity card. If it reads "Unreachable", the backend
is not running.

`.env` files are gitignored. **No secret or tunable is hardcoded anywhere in the
codebase** — engine depth, model names, thresholds, and keys all come from `.env` through
a typed settings module. See [configuration.md](final_docs/v2/configuration.md).

## Commands

### Backend (`cd backend`)

```bash
uv run python -m app                   # dev server (host/port from .env)
uv run pytest                          # tests
uv run pytest --cov=app                # tests with coverage
uv run ruff check .                    # lint
uv run ruff format .                   # format
uv run mypy app                        # type check (strict)
```

### Frontend (`cd frontend`)

```bash
npm run dev            # dev server
npm test               # tests
npm run test:coverage  # tests with coverage
npm run lint           # oxlint
npm run format         # prettier
npm run typecheck      # tsc
npm run build          # typecheck + production build
```

### Both

```bash
docker compose up                      # containerised dev environment
uv tool install pre-commit && pre-commit install   # secret scanning + lint on commit
```

## Architecture in brief

**Three truth levels.** A canonical object per game, aggregates across a window of games,
and persona views over both. Personas change wording, never chess facts — and that
invariant is enforced by test.

**Two engineering halves.** The deterministic core (`domain/games`, `analysis`,
`patterns`, `aggregation`) is reproducible and asserted exactly. The agent layer
(`domain/chat`, `orchestration/`) is stochastic and evaluated statistically. A CI check
fails the build if the first ever imports the second.

**Retrieval is first-class.** A five-bucket corpus with per-bucket chunking and hybrid
dense + sparse search, exposed to the agent as tools rather than run as a fixed prefix
step. See [rag-architecture.md](final_docs/v2/rag-architecture.md).

**Identity comes from chess platforms.** Log in with Lichess via OAuth2 PKCE; link a
Chess.com username. See [ADR-0007](final_docs/v2/adr/0007-identity-and-oauth-strategy.md).

## Documentation

`final_docs/` is a **git submodule** pointing at the private repository
`rakeshnetdev/grandmate_final_docs`. A plain `git clone` leaves the directory empty and
every `final_docs/...` link below dead. Populate it with:

```bash
git clone --recurse-submodules https://github.com/rakeshnetdev/grandmate-v2.git
# or, in an existing checkout:
git submodule update --init
```

Because the documentation repository is private, those links also do not resolve on
github.com for anyone without access to it — they are paths into a local checkout, not
browsable URLs.

Start at [`final_docs/v2/README.md`](final_docs/v2/README.md).

| Document | What it answers |
|----------|----------------|
| [prd.md](final_docs/v2/prd.md) | What is being built and for whom |
| [project-plan.md](project-plan.md) | The 19-phase delivery plan |
| [decisions-log.md](final_docs/v2/decisions-log.md) | What has been decided, and what is open |
| [configuration.md](final_docs/v2/configuration.md) | Every environment variable |
| [evaluation-strategy.md](final_docs/v2/evaluation-strategy.md) | How quality is measured and gated |
| [definition-of-done.md](final_docs/v2/definition-of-done.md) | When a phase is finished |

## Development process

Delivery is phase-gated. Each phase ships implementation, tests, evaluation, and
documentation, and does not begin until the previous one is signed off. `claude.md` is the
execution contract; `project-plan.md` is the blueprint.

The sibling `grandmate/` directory is a **read-only reference implementation**. Anything
adapted from it is recorded in
[the reuse ledger](final_docs/v2/changes/0001-reuse-ledger.md).
