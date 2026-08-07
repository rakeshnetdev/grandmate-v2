# Component architecture

Referenced from [`ARCHITECTURE.md` §2](../ARCHITECTURE.md#2-component-architecture).

Module-level view. The boundary between the deterministic core and the generative layer is
the one that is enforced by a CI check rather than by convention.

```mermaid
flowchart TB
    subgraph Client["Browser"]
      UI["React 19 SPA — 11 features<br/>auth · imports · games · analytics · reports<br/>chat · memory · training · profiles · devinsight · health"]
    end

    subgraph Api["FastAPI — routes stay thin, delegate to services"]
      RT["12 route modules"]
      DP["Dependencies<br/>DbSession · ScopedProfileId · LLM · Embeddings · OpeningIndex"]
    end

    subgraph Core["Deterministic core — imports no LLM, no orchestration"]
      IMP["domain/imports"]
      GAM["domain/games"]
      ANA["domain/analysis"]
      PAT["domain/patterns"]
      ANL["domain/analytics"]
    end

    subgraph Gen["Generative layer — every output grounded before delivery"]
      REP["domain/reports"]
      CHT["domain/chat"]
      MEM["domain/memory"]
      ORC["orchestration/<br/>graphs · tools · checkpointer · store"]
      USG["domain/llm_usage"]
    end

    subgraph Rag["Retrieval"]
      KNW["domain/knowledge"]
      RET["domain/retrieval"]
    end

    subgraph Int["Integrations — adapters, one per external dependency"]
      ENG["engine/ — Stockfish UCI"]
      LLMI["llm/ — OpenAI behind a Protocol"]
      VEC["vectorstore/ — pgvector"]
      STOI["storage/ — StorageBackend"]
      LIC["lichess/ · chesscom/"]
    end

    DB[("Postgres 17 + pgvector")]

    UI --> RT --> DP
    RT --> Core
    RT --> Gen
    Gen --> Rag
    Gen --> ORC
    Core --> ENG
    Gen --> LLMI
    Rag --> LLMI
    Rag --> VEC
    IMP --> STOI
    IMP --> LIC
    Core --> DB
    Gen --> DB
    VEC --> DB

    Core -. "❌ forbidden — CI enforced" .-x Gen

    classDef core fill:#e8f5e9,stroke:#2e7d32;
    classDef gen fill:#e3f2fd,stroke:#1565c0;
    class IMP,GAM,ANA,PAT,ANL core
    class REP,CHT,MEM,ORC,USG gen
```

## The one edge that is a rule

`tests/test_layer_boundaries.py` runs as its own CI step and fails the build if any module
in the green cluster acquires an import from the blue cluster or from an LLM package. It
was written before there was any deterministic core to check — its own six
self-tests ran against a synthetic fixture until there were real modules for it to
police.

The dependency in the other direction is allowed and deliberate: `domain/imports` imports
`domain/games` because ingestion needs canonicalization. One-directional, documented, and
the reverse would be the design error.
