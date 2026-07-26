# User Journey Walkthrough

Phase 0 validation: every journey in `prd.md` walked end to end against the planned
architecture, checking that each step has a home in a phase and that nothing depends on a
component that does not exist yet.

Legend: ✅ covered · ⚠️ covered with a caveat · ❌ gap

---

## J1 — First login

| Step | Component | Phase | Status |
|------|-----------|-------|--------|
| User clicks "Log in with Lichess" | `features/auth` | 2 | ✅ |
| PKCE challenge generated, redirect to `lichess.org/oauth` | `integrations/lichess` | 2 | ✅ |
| Callback exchanges code at `lichess.org/api/token` | backend auth service | 2 | ✅ |
| `users` row created, self profile bootstrapped | `domain/profiles` | 2 | ✅ |
| Session JWT issued, user lands on empty dashboard | `features/auth`, `features/profiles` | 2 | ✅ |

⚠️ **Caveat**: a user with only a Chess.com account cannot complete J1. Open question Q-3.

## J2 — Import and analyse

| Step | Component | Phase | Status |
|------|-----------|-------|--------|
| User requests last 30 Lichess games | `features/imports` | 14 | ✅ |
| Import job created, token reused from login | `domain/imports` | 14 | ✅ |
| Games deduplicated on content hash | `domain/imports` | 3 | ✅ |
| Parsed into canonical objects with FEN/EPD per ply | `domain/games` | 4 | ✅ |
| Sweep analysis at depth 12, deep pass on critical moments | `domain/analysis` | 5 | ✅ |
| Openings tagged via EPD lookup | `domain/patterns` | 6 | ✅ |
| Motifs and themes detected | `domain/patterns` | 6 | ✅ |
| Aggregates computed over the window | `domain/aggregation` | 8 | ✅ |
| Job progress visible | `features/imports` | 3 | ✅ |

⚠️ **Ordering note**: J2 is only fully available at Phase 14. Phases 3–8 deliver the same
journey via manual PGN upload (J9), which is why manual ingestion precedes connectors.

## J3 — Single game review

| Step | Component | Phase | Status |
|------|-----------|-------|--------|
| Game list, then game detail | `features/games` | 3, 4 | ✅ |
| Move list with classifications | `features/analysis` | 5 | ✅ |
| Board position browser per ply | `features/games` | 4 | ✅ |
| Critical moments flagged with eval swings | `features/analysis` | 5 | ✅ |
| Detected motifs shown with confidence | `features/analysis` | 6 | ✅ |

## J4 — Ask about a game

| Step | Component | Phase | Status |
|------|-----------|-------|--------|
| Chat thread opened with active game context | `features/chat`, `domain/chat` | 10 | ✅ |
| Agent calls `get_game_analysis` for the game | `orchestration/tools` | 10 | ✅ |
| Agent calls `search_knowledge('tactics', …)` for the mechanism | `orchestration/tools` | 10 | ✅ |
| Answer drafted with citations | `domain/chat` | 10 | ✅ |
| Grounding guardrail checks moves and evaluations | `domain/chat` | 10 | ✅ |
| Thread state checkpointed | LangGraph checkpointer | 10 | ✅ |

## J5 — Ask about a habit

| Step | Component | Phase | Status |
|------|-----------|-------|--------|
| Agent recognises a profile-level rather than game-level question | supervisor / intent routing | 10 | ✅ |
| Agent calls `get_profile_aggregate` | `orchestration/tools` | 10 | ✅ |
| Thin-sample findings suppressed | `domain/aggregation` | 8 | ✅ |
| Answer cites frequency evidence | `domain/chat` | 10 | ✅ |

## J6 — Switch persona

| Step | Component | Phase | Status |
|------|-----------|-------|--------|
| Persona toggle in the UI | `features/profiles` | 9 | ✅ |
| Same analysis object re-rendered | `domain/reports` | 9 | ✅ |
| Fact-set invariance asserted | persona fidelity suite | 9 | ✅ |
| Kid persona suppresses low-confidence findings | `domain/reports` | 9 | ✅ |

## J7 — Coach views a student

| Step | Component | Phase | Status |
|------|-----------|-------|--------|
| Relationship row exists and is not revoked | `profile_relationships` | 2 | ✅ |
| Navigate to `/players/:profileId` | `features/profiles` | 9 | ✅ |
| Permission dependency validates access | API dependency | 2 | ✅ |
| Same analysis surfaces reused | `features/analysis` | 9 | ✅ |
| Audit event emitted | `audit_events` | 2 | ✅ |

❌ **Gap identified**: nothing in the plan creates the relationship row. A coach cannot
view a student until someone links them, and no invitation or linking flow exists in any
phase. **Added to Phase 2 scope** as a coach-student linking flow.

## J8 — Memory continuity

| Step | Component | Phase | Status |
|------|-----------|-------|--------|
| Preference captured from an explicit statement | `domain/memory` | 11 | ✅ |
| Written only above the confidence floor | memory write policy | 11 | ✅ |
| Retrieved on a later session, scoped by profile | LangGraph store | 11 | ✅ |
| Visible and deletable in the audit surface | `features/memory` | 11 | ✅ |

## J9 — Upload a PGN

| Step | Component | Phase | Status |
|------|-----------|-------|--------|
| Upload, paste, or batch | `features/imports` | 3 | ✅ |
| Validation with structured rejection reasons | `domain/imports` | 3 | ✅ |
| Raw PGN to Supabase Storage | repository | 3 | ✅ |
| Same canonical pipeline as imported games | `domain/games` | 4 | ✅ |

⚠️ **Note**: a PGN upload needs a profile to attach to. For a logged-in user this is their
self profile. Uploading games for a *student* requires that student's profile to exist —
which depends on the linking flow added to Phase 2 above.

---

## Findings

| # | Finding | Resolution |
|---|---------|-----------|
| F-1 | No flow creates `profile_relationships` rows, blocking J7 | Coach-student linking flow added to Phase 2 scope |
| F-2 | J9 for a student profile depends on F-1 | Resolved by the same addition |
| F-3 | Chess.com-only users cannot log in | Open question Q-3 raised to the owner |
| F-4 | J2 not fully available until Phase 14 | Accepted; J9 provides the same downstream journey from Phase 3 |

No other gaps found. Every remaining step maps to a component in a defined phase.
