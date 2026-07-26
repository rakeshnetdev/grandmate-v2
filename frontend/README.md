# GrandMate Frontend

Vite + React 19 + TypeScript + Tailwind v4 + shadcn/ui.

## Setup

```bash
cp .env.example .env
npm install
npm run dev        # http://localhost:5173
```

Requires the backend on `http://localhost:8000` (configurable via `VITE_API_BASE_URL`).

## Layout

```
src/
  app/
    layouts/       Application shell
    providers/     TanStack Query and other context
    router/        Route table — one file, so permission boundaries stay visible
  shared/
    components/ui/ shadcn/ui primitives (Button, Card, ...)
    lib/           api-client, cn utility
    config/        Zod-validated environment
    hooks/         Cross-feature hooks
    types/         Shared types
  features/
    health/        Backend connectivity — the template to copy
      api/         Zod schemas + fetch functions
      hooks/       TanStack Query hooks
      components/  Presentational components
      index.ts     Public surface
  pages/           Route-level compositions
  test/            setup + renderWithProviders helper
```

## Feature module convention

Copy `features/health/` when adding a feature. The layering is:

```
component  →  hook  →  api module  →  shared api-client  →  backend
```

Rules that make this worth following:

- **Presentation components never call `fetch`.** They call a hook. Network concerns
  (base URL, credentials, error shaping, auth headers) stay in one place.
- **Every response is validated with Zod at the boundary.** Types are inferred from the
  schema, so the TypeScript type and the runtime check cannot disagree. A backend that
  changes shape fails loudly in the API client rather than rendering `undefined` three
  components deep.
- **Other features import from `index.ts` only.** Internal reorganisation should not break
  consumers.
- **Query keys are centralised** per feature, so invalidation cannot drift from
  subscription.

## Developer insight panel

`features/devinsight` renders a collapsible trace inspector at the bottom of the app,
bundled only in development (`import.meta.env.DEV`, so it is tree-shaken from production
builds).

It fetches **nothing while closed** — that is the point of the backend's separate trace
endpoint (ADR-0013). Opening it lists recent requests; selecting one shows a span timeline
and per-kind detail with token usage.

Spans are grouped by kind rather than shown in fixed tabs, so Engine, Retrieval, LLM, and
Agent sections appear automatically as the phases that emit them land — no tab has to be
declared in advance and sit empty.

If the backend has tracing disabled the endpoints 404, and the panel says so instead of
showing a broken state.

## Styling

Tailwind v4, CSS-first — the theme lives in `src/index.css`, not a JS config.

Tokens are declared twice on purpose: plain CSS variables on `:root` hold the values so a
media query can override them at runtime, and `@theme inline` maps them into Tailwind's
colour namespace to generate `bg-background` and friends. The `inline` keyword is what
makes the generated utilities reference `var(--background)` rather than baking in the
resolved value — without it, the dark-mode override would have no effect.

Components reference semantics (`bg-primary`), never literal palette values.

Adding shadcn components:

```bash
npx shadcn@latest add dialog
```

`components.json` points at `@/shared/components/ui`.

## Configuration

`src/shared/config/env.ts` validates `import.meta.env` with Zod at module load, so a
misconfigured deployment fails immediately with a clear message rather than surfacing as
a confusing 404 on the first API call.

Only `VITE_`-prefixed values reach the browser, and only non-secret values belong there.
The Lichess client id is public by design — Lichess is a public OAuth client with no
secret ([ADR-0007](../final_docs/v2/adr/0007-identity-and-oauth-strategy.md)).

## Testing

```bash
npm test               # run once
npm run test:watch     # watch
npm run test:coverage  # with coverage
```

Vitest + React Testing Library. Use `renderWithProviders` from `src/test/render.tsx` so
tests exercise the real provider context rather than an approximation of it.

## Quality gate

```bash
npm run lint && npm run format:check && npm run build && npm test
```

## Note on dependencies

`react-router-dom` is pinned to `7.11.0`. Every release from 7.12 onward is inside the
range of [GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2) and no
patched version exists yet. The advisory concerns RSC mode, which this SPA does not use,
so we are not exposed — but pinning keeps `npm audit` clean so CI can gate on it. Revisit
when a patched release ships.
