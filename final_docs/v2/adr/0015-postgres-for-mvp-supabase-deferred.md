# ADR-0015 — Plain Postgres with pgvector for MVP, Supabase Deferred

- **Status**: Accepted — supersedes the *timing* of ADR-0002, not its direction
- **Date**: 2026-07-26
- **Phase**: 2
- **Deciders**: Project owner

## Context

ADR-0002 chose Supabase as the system of record. Phase 2 began by installing the Supabase
CLI and starting the local stack, and that is where the friction showed up:

- Homebrew could not install the CLI — it required updating Xcode Command Line Tools, a
  `sudo` and System Settings operation.
- The release tarball ships two co-located binaries (`supabase` and `supabase-go`);
  installing only the shim produced a confusing failure.
- The local stack runs roughly ten containers to provide what Phase 2 actually needs from
  it: one Postgres database.

Meanwhile ADR-0007 had already removed the main reason to adopt Supabase early. Supabase
Auth has no Lichess provider, so the backend owns the OAuth exchange and issues its own
session token. Of the four things Supabase offered — Postgres, Auth, Storage, Realtime —
Auth was already gone, Realtime was never needed, and Storage is one interface away from
being swappable.

The owner asked to skip Supabase setup for MVP and park it for a later phase.

## Decision

**MVP runs on plain Postgres 17 with pgvector, in a single container.**

```yaml
postgres:
  image: pgvector/pgvector:pg17
  ports: ['5433:5432']     # 5433 so a developer's existing Postgres keeps 5432
```

**Object storage goes behind an interface** (`app/integrations/storage/`) with a
filesystem implementation for MVP. Uploaded PGNs and generated reports write to a
gitignored local directory.

**Supabase is deferred, not abandoned.** ADR-0002's direction stands; only its timing
changes. Adoption moves to Phase 17, alongside the hosting decision, where choosing a
managed data platform is the actual question being answered.

## Rationale

The decisive point is that **Supabase's database *is* Postgres**. Running Postgres 17 with
pgvector locally means the SQL dialect, the migrations, the extension, the RLS policies,
and every line of repository code are identical to what Supabase would run. Adopting
Supabase later is a connection-string change plus a Storage adapter — not a migration, not
a rewrite, and not a schema change.

That makes the deferral nearly free, which is what distinguishes it from a normal
reversal. If the two options had different SQL semantics, deferring would be borrowing
against Phase 17. They do not, so it is not.

Choosing to defer rather than to reject also matters. Supabase remains the likely
production answer: managed backups, RLS tooling, Storage, and a hosting story are all real
value at deployment time. They are simply not value at Phase 2, where the only requirement
is a database that speaks Postgres and holds vectors.

Port 5433 rather than 5432 is deliberate: a developer with a local Postgres already
running should not have to stop it to work on this project.

pgvector is installed from the first migration rather than at Phase 7. Retrieval is a core
capability (ADR-0008), and discovering an extension problem at Phase 7 is worse than
paying for it now, which costs nothing.

## Alternatives considered

| Option | Why rejected |
|--------|-------------|
| Persist with the Supabase local stack | Ten containers and a CLI install requiring Xcode tooling, to obtain one Postgres database |
| SQLite | No pgvector, so Phase 7 retrieval would need a separate store; weak concurrent writes once background workers land in Phase 3; diverging SQL dialect would force migrations to be rewritten |
| Hosted Supabase directly, no local database | Tests would need network and credentials, making CI slow and non-hermetic |
| Drop Supabase permanently | Discards a good production answer over a local-tooling problem; managed backups, Storage, and hosting remain genuinely valuable |
| MinIO for storage | Another container for something MVP does not need; the interface makes the swap cheap whenever it does |

## Consequences

### Positive
- One container instead of ten; `docker compose up postgres` is the whole setup
- No Supabase CLI dependency, so no Xcode toolchain requirement
- Identical Postgres semantics, so nothing about the schema or queries is throwaway
- pgvector available from the first migration
- Hermetic tests — no network, no credentials
- Storage abstraction is useful regardless of which backend eventually wins

### Negative
- No Supabase Storage, dashboard, or Realtime during MVP
- RLS still available (a Postgres feature) but without Supabase's tooling around it
- A storage adapter must be written at Phase 17 for whatever backend is chosen
- Two data-layer configurations exist across the project's life, and Phase 17 has to do
  the switch rather than inheriting it

### Follow-up required
- Phase 2: `DATABASE_URL` pointing at local Postgres; migration pipeline; `StorageBackend`
  Protocol with a local implementation
- Phase 7: enable pgvector indexes for the corpus
- **Phase 17**: decide the managed platform alongside hosting; write the Storage adapter;
  migrate. ADR-0002 is the starting point for that decision.

## References
- ADR-0002 — Supabase as system of record (direction retained, timing deferred)
- ADR-0007 — identity, which already removed Supabase Auth from the picture
- ADR-0008 — agentic RAG, which requires pgvector
