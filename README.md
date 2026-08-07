# GrandMate v2

A chess analysis and coaching platform that finds a player's **long-term habits**, not just
their single blunders. Ingests games from PGN files, Lichess, and Chess.com; enriches each
one with deterministic engine-backed analysis; aggregates patterns across many games; and
explains the results differently depending on who is asking.

Architecturally it is an **agentic RAG system built on a deterministic chess core**. The
core computes what is true about a game. The agent layer decides what to retrieve and how
to say it. Neither does the other's job, and a CI check fails the build if the first ever
imports the second.

**Live**: [grandmate.vercel.app](https://grandmate.vercel.app) — frontend on Vercel,
backend on [Fly.io](https://grandmate-v2-backend.fly.dev), Neon Postgres 17 + pgvector
behind it. Deployment steps, and the seven problems that stood in the way, are in
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

**Start with [`docs/production_and_experiments.md`](docs/production_and_experiments.md)**
if you want the short version: what runs live, what was built and deliberately not shipped
(multi-agent orchestration, fine-tuning, an MCP server), and how to read the evaluation
numbers.

## Layout

```
grandmate-v2/
  backend/      FastAPI + uv. Analysis core, retrieval, agents.
  frontend/     Vite + React + Tailwind + shadcn/ui. Feature-driven.
  docs/         Architecture, deliverables, evaluation results, deployment, diagrams.
  .github/      Path-scoped CI, issue and PR templates.
```

Backend and frontend are independently toolchained with no shared dependency graph. The
only coupling is a typed API contract.

## Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| Python | 3.11+ | Backend |
| [uv](https://docs.astral.sh/uv/) | 0.11+ | Python dependency and script running |
| Node | 22+ | Frontend |
| Stockfish | any recent | Engine analysis |
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
a typed settings module (`backend/app/core/config/`). Every variable is documented in
`backend/.env.example` and `frontend/.env.example`.

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
and persona views over both. Personas change wording, never chess facts — that invariant
is measured, and it is currently **failing at 94.4%** against a zero-tolerance target,
reported as a failure rather than rounded up.

**Two engineering halves.** The deterministic core (`domain/games`, `analysis`,
`patterns`, `aggregation`) is reproducible and asserted exactly. The agent layer
(`domain/chat`, `orchestration/`) is stochastic and evaluated statistically. A CI check
fails the build if the first ever imports the second.

**Retrieval is first-class.** A five-bucket corpus with per-bucket chunking and hybrid
dense + sparse search, exposed to the agent as tools rather than run as a fixed prefix
step.

**One agent, not five.** A multi-agent supervisor graph was built and evaluated
head-to-head against the single-agent baseline, lost on both pre-declared metrics, and is
not routed. The reasoning and the numbers are in
[`docs/production_and_experiments.md`](docs/production_and_experiments.md) §2.1.

## Documentation

Everything needed to review this project is in [`docs/`](docs/).

| Document | What it answers |
|----------|----------------|
| [production_and_experiments.md](docs/production_and_experiments.md) | What runs live, what was tried and dropped, how to read the eval numbers |
| [Deliverables.md](docs/Deliverables.md) | The full submission: problem, solution, data, prototype, evals, next steps |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the system is built — invariants, graphs, request lifecycle, memory, RAG |
| [evaluation_report.md](docs/evaluation_report.md) | Measured results, generated from recorded runs |
| [evaluation_data_design.md](docs/evaluation_data_design.md) | What data each suite uses and what it cannot prove |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | How the live deployment was built, and the seven problems in the way |
| [diagrams/](docs/diagrams/) | Every diagram standalone, with reading notes |

The internal engineering record — ADRs, the decisions log, and delivery reports — lives in a
separate private repository and is not required to review the system. Nothing in `docs/`
depends on it.

> **`final_docs/` is a submodule on that private repository.** `git clone
> --recurse-submodules` will fail to fetch it without access, and a plain `git clone` leaves
> the directory empty. Both are expected and neither affects the application or its
> documentation — clone normally and ignore it.

## Development process

Delivery is incremental and gated: each increment ships implementation, tests, evaluation,
and documentation together, and does not begin until the previous one is signed off.
Nothing is committed with failing tests, and no evaluation result is discarded because it
was inconvenient — negative results are recorded and acted on.
