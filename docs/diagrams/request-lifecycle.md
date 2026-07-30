# Request lifecycle — PGN to coaching answer

Referenced from [`ARCHITECTURE.md` §5](../ARCHITECTURE.md#5-request-lifecycle--pgn-to-coaching-answer).

What one `POST /api/v1/imports` actually triggers, across a synchronous request, a
background job, and a later interactive turn.

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as React SPA
    participant API as FastAPI
    participant IMP as ImportService
    participant GP as GameParsingService
    participant OI as OpeningIndex
    participant BG as BackgroundTasks
    participant SF as Stockfish
    participant PD as PatternDetectionService
    participant DB as Postgres

    U->>FE: paste / upload PGN
    FE->>API: POST /api/v1/imports
    API->>IMP: ingest(sources, self + study profiles)

    rect rgb(232,245,233)
    note over IMP,DB: Synchronous — sub-second
    IMP->>IMP: parse headers + mainline, content-hash
    IMP->>DB: dedup on (profile_id, content_hash)
    IMP->>IMP: route per game — header match ? self : study
    IMP->>GP: canonicalize
    GP->>GP: replay — SAN, UCI, FEN before/after, EPD, clock
    GP->>DB: game_moves (one row per ply)
    IMP->>OI: match by EPD, deepest wins
    OI->>DB: game_openings
    IMP->>DB: queue ENGINE_ANALYSIS job
    end

    API->>DB: COMMIT
    note right of API: Commit BEFORE scheduling.<br/>The background task opens its own<br/>session and would not otherwise<br/>see the uncommitted job row.
    API->>BG: schedule run_pending_analysis_jobs
    API-->>FE: 201 + {imported, duplicates, rejected[]}
    FE-->>U: "1 imported · 0 duplicates · 0 rejected"

    rect rgb(255,248,225)
    note over BG,DB: Background — ~7s/game, ENGINE_MAX_CONCURRENT_GAMES=4
    BG->>SF: shallow sweep — depth 12, every ply
    SF-->>BG: eval · best move · principal variation
    BG->>BG: classify — best/good/inaccuracy/mistake/blunder
    BG->>SF: deep pass — depth 18, critical moments only
    BG->>DB: game_analysis + move_evaluations (versioned run)
    BG->>PD: detect_patterns
    PD->>DB: game_tactics + game_strategy_tags
    end

    U->>FE: open the game, ask a question
    FE->>API: POST /api/v1/chat/threads/{id}/messages
    API->>API: classify_intent → run_agent → guardrail → write_memory
    API-->>FE: {answer, citations[], grounded: true}
```

## Why the commit annotation is there

That step is a real defect that shipped in Phase 5 and was fixed in Phase 7.

The route created the `Job` row on the *request's* session, then handed the id to
`BackgroundTasks`, which opens a **separate** session. Under normal read-committed
isolation that second session ran `session.get(Job, job_id)` before the first had
committed, got `None`, and a defensive "job vanished" guard treated the race as a no-op.
No exception, no log, no Stockfish process — every job stayed `pending` forever.

It reproduced 100% of the time and was invisible to the test suite, because the automated
tests called the dispatcher directly and never exercised the real HTTP →
`BackgroundTasks` → dual-session path. It was found by manual browser testing during a
later phase. The regression test now exercises that real path specifically.
