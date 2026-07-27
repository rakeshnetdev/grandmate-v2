# Claude Implementation Instructions for GrandMate

## Purpose

This document instructs Claude to implement GrandMate phase by phase using the accompanying `project-plan.md`. GrandMate is a modular chess analysis and coaching platform with separate frontend and backend, deterministic chess analysis, multi-source ingestion, persona-aware reporting, and memory-aware chat.

Claude must use this file as the execution contract and `project-plan.md` as the architecture and delivery blueprint.

## Primary Instruction

Implement the project **one phase at a time**. Do not skip ahead. Do not silently make major product or architecture decisions that the plan lists as unresolved. When required inputs, corpus, thresholds, or policy decisions are missing, stop and ask the user before implementation continues.

## Non-Negotiable Rules

1. Backend and frontend must remain separate.
2. Architecture must stay modular, distributed-friendly, loosely coupled, and easy to debug.
3. Use feature-driven, component-based structure on the frontend.
4. Avoid single-file implementations for complex features.
5. All generated code must include proper comments for non-obvious behavior.
6. Every phase must include implementation, tests, evaluation, and documentation updates.
7. Do not proceed to the next phase until the current phase is complete and the user explicitly approves continuation.
8. Keep deterministic chess analysis separate from LLM explanation logic.
9. Personas must not alter chess truth; they may only alter framing, depth, tone, and recommendations.
10. Chat memory must distinguish short-term thread state from long-term profile memory.
11. No secret and no tunable constant may be hardcoded. Everything comes from `.env` through a typed settings module.
12. Retrieval is a first-class capability, not a helper. It gets its own domain modules, its own tests, and its own recorded evaluation scores.
13. Agent tools, the MCP server, and internal callers must share one implementation per capability. Never two code paths with two behaviours.
14. The `analysis` retrieval bucket is profile-scoped. A retrieval that crosses a profile boundary without an explicit permission grant is a defect, not a feature.

## Default Technical Stack

Use `uv` for all Python-related commands whenever possible.
- Prefer `uv run` instead of calling `python` directly.
- Prefer `uv sync` / `uv pip install` for dependency management if needed.
- Use `python` directly only when a task cannot be done with `uv`.
- Use the existing project environment conventions in the repo.

### Frontend
- TypeScript
- React
- Vite
- Tailwind CSS
- shadcn/ui
- Component-based, feature-driven architecture
- Clean reusable hooks and shared UI primitives

### Backend
- Python
- FastAPI
- LangGraph
- python-chess
- Stockfish via UCI adapter
- Background workers for async analysis jobs

### Data Layer
- Supabase Postgres as primary database, run locally via the Supabase CLI in development
- pgvector for the knowledge corpus
- Supabase Storage
- Redis for caching/queues/rate limiting if needed

Supabase Auth is **not** the login provider. Identity comes from Lichess OAuth2 PKCE, with
the backend owning the exchange and issuing its own session token. See ADR-0007.

### AI Layer
- Agentic RAG: retrieval is exposed to the agent as tools, not run as a fixed prefix step
- Multi-bucket corpus (`rules`, `openings`, `tactics`, `strategy`, `analysis`) with per-bucket chunking and retrieval strategy
- Hybrid retrieval: pgvector dense + BM25 sparse, fused with reciprocal rank fusion
- LangGraph for agent orchestration, checkpointers, and long-term stores
- Multi-agent supervisor pattern with a critic that verifies claims against deterministic analysis
- MCP server exposing the same tool implementations the internal agents use
- `gpt-4o-mini` by default, behind a provider abstraction
- RAGAS for retrieval and answer quality, with synthetic datasets and human-reviewed golden sets

## Required Architectural Style

### Frontend
- Use a feature-driven structure.
- Keep domain logic out of presentational components.
- Use shared types and schema validation.
- Use modular components with clear props and responsibility.
- Keep components small and composable.
- Organize code so debugging a feature does not require scanning unrelated files.

### Backend
- Use explicit domain modules.
- Separate routes, services, repositories, workers, schemas, integrations, and orchestration.
- Avoid monolithic service files.
- Design adapters for external APIs and LLM providers.
- Keep infrastructure details behind interfaces where practical.

## Development Workflow

For each phase in `project-plan.md`, Claude must execute the following sequence:

1. Read the relevant phase requirements.
2. Summarize the implementation plan for that phase.
3. Identify missing decisions, corpus, credentials, or policy inputs.
4. Ask the user for unresolved inputs before coding if anything critical is missing.
5. Implement only the approved phase scope.
6. Add or update tests.
7. Run validation steps conceptually and, where possible, practically.
8. Update documentation for that phase.
9. Present what was built, what was tested, what remains, and any risks.
10. Ask for sign-off before proceeding.

## Decisions Already Locked

These were answered by the user in Phase 0 and must **not** be re-litigated or silently
changed. The authoritative record is `final_docs/v2/decisions-log.md`.

| Topic | Locked decision |
|-------|-----------------|
| Repo layout | Monorepo `grandmate-v2/{backend,frontend}` with hard boundaries |
| Identity | Lichess OAuth2 PKCE login; Chess.com linked by username |
| MVP personas | self-learner, coach, kid |
| Other-player views | Separate page reusing self-view logic, permission gated |
| LLM | `gpt-4o-mini` default, behind a provider abstraction |
| Engine | Baseline depth 12, configurable, tiered deep pass |
| Opening data | `lichess-org/chess-openings` dist TSVs, matched on EPD |
| Config | Everything from `.env`; no hardcoded keys or constants |
| Reports | In-app HTML in MVP; PDF deferred |
| Hosting | Deferred to Phase 17 |
| RAG | Agentic, multi-bucket, hybrid retrieval |
| Fine-tuning | Considered at Phase 16, scoped to persona tone only |

If implementation reveals that a locked decision is wrong, Claude must say so explicitly
and ask before changing it. Silently working around a locked decision is not acceptable.

## Remaining Ask-Before-Decide Topics

Claude must still ask the user before deciding any of the following:

- Supabase project credentials and local setup details (needed at Phase 2)
- when to place the OpenAI API key into `.env` (Claude must prompt the user at Phase 1)
- exact memory retention windows and deletion rules (Phase 11)
- MCP tool surface beyond the proposed list (Phase 12)
- whether multi-agent orchestration ships or is deferred (Phase 13, decided on evidence)
- fine-tuning go/no-go (Phase 16)
- hosting and deployment topology (Phase 17)
- rate limits, ingestion quotas, and LLM spend ceilings
- any corpus document whose licence or provenance is unclear

Claude may propose defaults, but must clearly label them as proposals and wait for approval before locking them in.

## Git Workflow — One Branch and One PR Per Phase

Every phase lives on its own branch and lands through its own pull request. No phase work
is committed directly to `main`.

### Branch naming

`P{phase}-{short-slug}`, lowercase kebab-case slug.

```
P0-discovery-baseline
P1-engineering-foundation
P2-supabase-identity
P3-ingestion-mvp
```

Sub-phases append a letter: `P1a-developer-insight`.

### Sequence for every phase

1. **Ask before branching.** Confirm with the user first: *"Pull latest from `main` and
   create `P{N}-{slug}`?"* Then `git checkout main && git pull`, and branch from there.
   **Always branch from an up-to-date `main`, never from another phase branch.** Never
   start work on `main` itself.
2. **Implement** the approved scope.
3. **Test and validate.** All suites pass; evaluation run and scores recorded where the
   phase requires it.
4. **Write the phase report** into `final_docs/v2/phase-reports/`.
5. **Ask for check-in approval**, using exactly this form:

   > Phase N: {name} completed. Shall we check in?

   Include the test results, what was built, known gaps, and any open questions. Then
   **stop and wait**. Do not commit before the user answers.
6. **On approval**: commit, push the branch, and open a PR with `gh pr create`.
7. **The user merges the PR manually.** Claude never merges. Wait for confirmation that
   it is merged.
8. **Next phase**: return to step 1 — ask, pull `main`, branch again. Do not start the
   next phase before the current PR is merged and the user has signed off.

### Why branching from `main` matters

Phases 0 and 1 were split retroactively: both branches were created from the initial
commit before either was merged, so neither contained the other's files and a checkout of
one showed only half the project. Branching from an up-to-date `main` each time is what
prevents that.

### Commit rules

- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`.
- Scope by phase where useful: `feat(phase-1): add typed settings module`.
- Never commit `.env`, keys, or any secret value.
- Never commit with failing tests. If something fails, report it rather than committing
  around it.

### PR rules

- Title: `P{N} — {Phase name}`.
- Body follows `.github/pull_request_template.md`, and links the phase report.
- State test results, known gaps, and any deviation from `project-plan.md` explicitly.
- Every PR body ends with the Claude Code attribution line.

### Hard rules

- Committing, pushing, or opening a PR happens **only after the user approves check-in**.
- Merging happens **only when the user asks**.
- If work has already begun on `main` by mistake, stop and ask how to reorganise it
  rather than force-pushing or rewriting history unilaterally.

## Phase Gate Rule

At the end of each phase, Claude must produce a phase report containing:
- completed tasks,
- files/modules created or changed,
- tests added and test results,
- evaluation performed,
- known gaps,
- recommendation on whether the phase is ready for sign-off.

Claude must then stop and ask the user to approve or request changes. No next-phase implementation is allowed until approval is received.

## Coding Standards

### General
- Prefer readability over cleverness.
- Use descriptive names.
- Add comments for reasoning-heavy code paths, orchestration logic, parsing policies, and non-obvious UI state behavior.
- Add docstrings to public classes, functions, and modules where helpful.
- Keep functions focused.
- Avoid hidden side effects.

### Frontend
- No API calls directly inside deeply nested presentation components.
- Prefer feature hooks or API service modules.
- Use shared UI primitives consistently.
- Keep Tailwind usage readable and refactor repeated class patterns into components.
- Use typed API contracts.

### Backend
- Validate all inputs and outputs with schemas.
- Keep business logic out of routes.
- Make jobs idempotent where possible.
- Log structured context for failures.
- Separate deterministic chess logic from prompt building.

## Testing Requirements

**MVP scope discipline.** This project builds an MVP first and scales later — it is not
building a production-hardened system on the first pass. Test coverage must be
proportionate to that: enough to trust the phase's core logic and catch real regressions,
not exhaustive permutation coverage. As a rough guide, one focused unit (a function, a
service method, a route) needs the happy path plus the one or two edge cases that would
actually bite in practice — not a test per theoretically-possible branch. If a phase's
test count is climbing past what its own scope obviously calls for, that is a signal to
stop and ask whether the *scope* has quietly grown beyond MVP needs, not a reason to add
more tests to match. When genuinely unsure whether a case is worth a test, ask rather than
defaulting to "add it to be safe."

Each implemented phase must include a suitable test mix:

### Unit tests
- core logic
- schema validation
- detectors
- aggregators
- transformations

### Integration tests
- API + DB
- API + worker
- external connector adapters with mocks
- LangGraph flows where relevant

### End-to-end tests
Add or extend E2E coverage when the phase introduces a user-visible workflow.

### Evaluation requirements
For any phase involving chess reasoning, LLM behavior, or memory:
- define evaluation criteria,
- create at least a small deterministic evaluation set,
- verify outputs against underlying analysis truth,
- document known limitations.

## Memory Rules

Claude must preserve the architectural distinction between:
- short-term thread memory,
- long-term profile memory,
- analysis database truth.

Claude must not collapse these into one storage model.

## Persona Rules

Claude must preserve the distinction between:
- profile relationship or role, and
- persona presentation mode.

The same analysis core must support self, coach, parent, kid-friendly, and analyst-style outputs without duplicating chess logic.

## Ingestion Rules

Claude must support these sources in the planned roadmap:
- uploaded PGN file,
- pasted PGN,
- batch PGN upload,
- Lichess imports using the logged-in user's OAuth token,
- Chess.com imports from the linked username via public monthly archives.

All sources must normalize into the same canonical game analysis pipeline.

## Configuration and Secrets Rules

The user was explicit: no hardcoded keys, no hardcoded constants.

- Every secret and every tunable is defined in `.env` and read through a typed
  `pydantic-settings` module on the backend and typed `import.meta.env` access on the frontend.
- `.env.example` is committed with every key present and every secret blanked.
- `.env` is gitignored and never committed.
- Engine depth, severity thresholds, retrieval `top_k`, chunk sizes, model names, token
  ceilings, and rate limits are all configuration, not literals in code.
- A magic number in a code path is a review failure. If a value needs a comment explaining
  why it is that number, it belongs in configuration with that comment attached.
- Claude must never print a real secret value into the terminal, logs, or documentation.
- When a key is needed, Claude asks the user to add it to `.env` and waits, rather than
  inventing a placeholder that silently fails later.

## RAG and Agent Rules

RAG is central to this product, not an add-on. Claude must hold these boundaries.

- Retrieval lives in `domain/retrieval` and `domain/knowledge`, behind interfaces. It is
  never inlined into a route, a prompt builder, or an agent node.
- Corpus buckets have distinct chunking and retrieval strategies. Do not collapse them
  into one undifferentiated index.
- Every corpus document records provenance: source, URL, licence, retrieval date, and who
  reviewed it. A document without provenance does not enter a bucket.
- Retrieval is exposed to agents as tools so the agent chooses strategy per query. A fixed
  retrieve-then-generate chain is not sufficient for this product.
- The `analysis` bucket is profile-scoped at the retriever interface, not at the caller.
  Isolation is enforced in one place and tested.
- Agent tools, the MCP server, and internal services share one implementation per
  capability.
- Every agent path has a step ceiling and a token budget.
- The critic pass verifies claims against deterministic analysis before delivery. Chess
  truth is never asserted by an LLM alone.
- Prompt construction stays separate from chess computation, per rule 8.

## Documentation Rules

For each major architectural step, Claude should add or update:
- README sections,
- architecture notes,
- ADRs where decisions are significant,
- setup instructions,
- test instructions.

If implementation choices differ from the original project plan, Claude must explicitly document the reason and ask for approval before locking in the deviation.

## When Claude Should Pause and Ask Questions

Claude must pause immediately and ask the user when:
- a required external credential or key is missing,
- a phase depends on undefined product policy,
- the project plan leaves a major taxonomy unresolved,
- data corpus is needed for validation,
- a proposed design may materially impact cost, privacy, or future extensibility,
- a requested feature appears to conflict with earlier signed-off decisions.

## Definition of Done Per Phase

A phase is done only when:
- implementation is complete for the approved scope,
- tests are written and pass,
- evaluation is performed and documented,
- code structure matches modular architecture expectations,
- docs are updated,
- the result is explained clearly,
- and the user signs off.

## Final Execution Mindset

Claude should behave like a disciplined senior engineer and technical lead, not a code generator that rushes ahead. The project should remain explainable, maintainable, and auditable at every stage. When uncertain, Claude should ask instead of guessing.

## Required Project Structure Discipline

Claude must follow the project structure described in `project-plan.md`.

### File placement rules
- UI components belong inside their feature unless they are truly reusable.
- Shared UI primitives belong in `frontend/src/shared/components/ui/`.
- API wrappers belong inside feature `api/` folders or shared API client modules.
- Backend routes must stay thin and should delegate to services.
- Domain rules must live in domain modules, not in routes or worker task files.
- Repositories must encapsulate persistence logic.
- Integrations must be isolated behind adapters.
- Tests must be added close to the layer they validate, with broader integration/e2e coverage in centralized test folders.

### Structure review requirement
At the end of each phase, Claude must review whether any file is becoming too large or taking on too many responsibilities. If so, Claude must refactor before asking for sign-off.

### Commenting expectation
Claude should add meaningful comments to:
- orchestration flows,
- engine analysis policies,
- detector heuristics,
- memory write rules,
- permission-sensitive code,
- complex React hooks,
- any code that would otherwise be hard to explain during review.

Claude should avoid useless comments that restate obvious code.

## RAGAS Evaluation Requirements

Claude must include RAGAS-based evaluation in phases where retrieval and LLM answer quality matter. RAGAS provides metrics such as Context Precision, Context Recall, Response Relevancy, Faithfulness, Answer Accuracy, and Response Groundedness, which should be used where appropriate for chat and explanation quality assessment.[cite:447][cite:448]

### Claude must do the following
- Build the RAGAS retrieval harness at **Phase 7**, not at the end. Extend it at Phases 10, 11, 13, and 16.
- Create versioned evaluation datasets for retrieval, single-game chat, profile chat, memory-aware chat, and persona/report explanations.
- Generate synthetic datasets where coverage is thin, but mark them as synthetic and have a human spot-check a sample before they gate anything.
- Maintain human-reviewed golden sets separately from synthetic ones. Never let a synthetic set silently become the golden set.
- Record scores for every evaluation run under `evals/runs/`.
- Compare current scores to previous runs.
- Flag regressions and threshold failures.
- Include evaluation summaries in phase sign-off reports.

### Evaluation cadence
Evaluation is continuous from Phase 7 onward. The per-phase metric map is in
`project-plan.md` under "Evaluation cadence" and must be kept in sync.

### Score recording rule
Claude must not run evaluation informally and discard the results. Every evaluation run should record:
- dataset version,
- model version,
- prompt/retriever versions,
- run timestamp,
- metric-level scores,
- pass/fail against thresholds.

### Threshold rule
If critical thresholds such as faithfulness or answer accuracy fail, Claude must stop and present the failure instead of pretending the phase is complete.

### Structure rule for evaluation files
Claude must place RAGAS and evaluation-related code, fixtures, docs, and scripts according to the project structure defined in `project-plan.md`.


## Repository Scope

- `grandmate/` is the existing reference application.
- `grandmate-v2/` is the new application being built from scratch.
- Claude must not modify `grandmate/` unless the user explicitly asks.
- Claude may read `grandmate/` to understand logic, structure, prompts, schemas, tests, and patterns.
- Claude must implement all new work inside `grandmate-v2/`.
- If code is reused from `grandmate/`, Claude must document that reuse in `final_docs/v2/changes/`.

## Reference Usage Rules

- Treat `grandmate/` as a sibling reference repo, not as part of the new codebase.
- Use it only for inspiration, comparison, and selective porting.
- Do not couple the new architecture to old folder names or old deployment assumptions.
- If the old implementation conflicts with the new plan, prefer the new plan.

## Migration Rule

- Rebuild the new application cleanly.
- Reuse logic intentionally, not accidentally.
- Any copied or adapted module must be reviewed and renamed to match the new architecture.
- Preserve the new architecture’s boundaries even if the old app was more monolithic.

## Approval Rule

- Before each phase, present the plan and wait for approval.
- Create the phase branch `P{N}-{slug}` before writing any code.
- When the phase is complete, tested, and validated, ask
  **"Phase N: {name} completed. Shall we check in?"** and wait.
- Commit, push, and raise the PR only after that approval.
- Do not begin the next phase until the user signs off on the completed phase and its PR
  is settled.