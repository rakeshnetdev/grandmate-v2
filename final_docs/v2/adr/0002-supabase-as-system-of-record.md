# ADR-0002 — Supabase Postgres as System of Record

- **Status**: Accepted in direction, **deferred in timing by ADR-0015**
- **Note**: MVP runs on plain Postgres 17 with pgvector. Supabase adoption moves to
  Phase 17 alongside the hosting decision. Because Supabase *is* Postgres, nothing in
  the schema, migrations, or repository code changes as a result.
- **Date**: 2026-07-25
- **Phase**: 0
- **Deciders**: Project owner

## Context

The system needs relational storage for games, moves, evaluations, aggregates, and
memory; vector storage for the knowledge corpus; object storage for raw PGNs and reports;
and a development setup that does not require cloud credentials to run tests.

The owner has a Supabase account and asked for local Supabase during development.

## Decision

Supabase Postgres is the system of record. In development it runs locally via the Supabase
CLI. pgvector is enabled from the start. Supabase Storage holds raw PGNs and generated
reports.

The backend owns all application logic. Supabase is a data platform, not an application
platform: no complex chess logic in database functions, no business rules in triggers.

Supabase Auth is explicitly **not** used as the login provider — see ADR-0007.

## Rationale

Postgres with pgvector gives relational and vector storage in one system with one
transactional boundary. Keeping the corpus embeddings in the same database as the analysis
rows they describe matters more here than it might elsewhere, because the `analysis`
retrieval bucket is a projection of relational data and must stay consistent with it. A
separate vector database would introduce a synchronisation problem with no compensating
benefit at this scale.

Running locally via the CLI means tests need no cloud credentials and no network, which
keeps CI fast and hermetic.

The reference application used SQLite plus Chroma or Qdrant. That worked for a prototype
but splits the data across three systems with three consistency stories.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Plain Postgres, self-managed | Loses Storage and the managed operational path for no gain during development |
| Postgres + dedicated vector DB (Qdrant, Pinecone) | Synchronisation burden between analysis rows and their embeddings; unnecessary at this scale |
| SQLite + Chroma, as in the reference app | Does not survive concurrent workers; three systems, three consistency stories |
| Supabase as full application platform (edge functions, RPC) | Chess analysis, engine orchestration, and agent workflows do not belong in database functions |

## Consequences

### Positive
- One database for relational, vector, and full-text search
- Local development needs no cloud credentials
- Storage, backups, and RLS available when needed
- Migrations in code, reviewable, with rollback plans

### Negative
- Supabase CLI becomes a local development prerequisite (Docker required)
- pgvector performance at large corpus sizes needs monitoring; index tuning may be required
- Some coupling to Supabase conventions, though the underlying Postgres is portable

### Follow-up required
- Phase 2: owner supplies local project details; migration pipeline established
- Phase 7: pgvector index strategy and dimension pinned to `EMBED_DIMENSIONS`
- Phase 17: backup and restore drill

## References
- `project-plan.md` — Supabase Usage Plan
- `final_docs/v2/data-model.md`
