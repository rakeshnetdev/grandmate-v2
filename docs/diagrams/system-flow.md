# System flow — deterministic vs LLM, end to end

One diagram covering every feature: what happens deterministically, where the LLM is
invoked, and which prompt builder each LLM call uses.

**The rule this diagram exists to make visible:** chess truth is computed, never
generated. Stockfish and the detectors produce facts; the LLM only words them. No LLM
call decides whether a move was a blunder (`claude.md` rule 8).

## Legend

| Style | Meaning |
|---|---|
| **Deterministic** | Engine, parsing, detectors, aggregation, SQL. Same input → same output. No API key needed. |
| **LLM** | An OpenAI completion. Labelled with the prompt builder that constructs its messages. |
| **Retrieval** | pgvector dense + BM25 sparse, fused by RRF. Embeddings are an API call; fusion is deterministic. |

```mermaid
flowchart TD
    subgraph INGEST["1 · Ingestion — deterministic"]
        SRC["PGN upload / paste<br/>Lichess · Chess.com import"]
        NORM["Parse + canonicalise<br/>domain/games"]
        JOB["Job row queued<br/>db/models/Job"]
        SRC --> NORM --> JOB
    end

    subgraph ENGINE["2 · Analysis — deterministic, NO LLM"]
        SF["Stockfish UCI<br/>depth 12, deep pass 18"]
        CLS["Move classification<br/>best/good/inaccuracy/mistake/blunder<br/>centipawn thresholds from config"]
        PAT["Pattern + motif detection<br/>domain/patterns"]
        OPEN["Opening detection<br/>EPD match, Lichess TSV"]
        JOB --> SF --> CLS --> PAT
        NORM --> OPEN
    end

    subgraph AGG["3 · Aggregation — deterministic"]
        ANALYTICS["Profile analytics<br/>accuracy, recurring weaknesses,<br/>opening families, colour splits"]
        CLS --> ANALYTICS
        PAT --> ANALYTICS
        OPEN --> ANALYTICS
    end

    DB[("Postgres + pgvector<br/>analysis truth")]
    CLS --> DB
    PAT --> DB
    ANALYTICS --> DB

    subgraph RAG["4 · Retrieval"]
        EMB["Embed query<br/>text-embedding-3-small"]
        DENSE["pgvector dense"]
        SPARSE["BM25 sparse"]
        RRF["Reciprocal rank fusion<br/>deterministic"]
        EMB --> DENSE --> RRF
        EMB --> SPARSE --> RRF
    end

    CORPUS[("Corpus buckets<br/>rules · openings · tactics<br/>strategy · analysis")]
    CORPUS --> DENSE
    CORPUS --> SPARSE
    DB -.->|"profile-scoped only"| RRF

    subgraph REPORTS["5 · Reports — facts computed, prose generated"]
        FACTS["Select findings deterministically<br/>domain/reports/selection.py<br/>caps + confidence per persona"]
        PERSONA["LLM · persona report<br/>prompts.build_messages"]
        STORY["LLM · full game story<br/>story_prompts.build_story_messages"]
        TRAIN_F["Training facts selected<br/>training_selection.py"]
        TRAIN["LLM · training plan<br/>training_prompts.build_training_analysis_messages"]
        FALLBACK["Deterministic fallback<br/>training_fallback.py"]
        DB --> FACTS --> PERSONA
        FACTS --> STORY
        DB --> TRAIN_F --> TRAIN
        RRF --> TRAIN
        TRAIN -. "no key / failure" .-> FALLBACK
    end

    subgraph CHAT["6 · Chat — agentic"]
        INTENT["LLM · intent classify<br/>prompts.build_intent_messages"]
        AGENT["LLM · coaching agent<br/>prompts.build_agent_system_message"]
        TOOLS["Agent tools — deterministic lookups<br/>analysis_tools · knowledge_tools<br/>memory_tools · validation_tools"]
        INTENT --> AGENT
        AGENT <--> TOOLS
        TOOLS --> DB
        TOOLS --> RRF
    end

    subgraph MULTI["7 · Multi-agent — supervisor + critic"]
        SUP["LLM · supervisor routes<br/>multi_agent_prompts.build_supervisor_messages"]
        SPEC["LLM · specialists<br/>build_retriever_system_message<br/>build_chess_analyst_system_message<br/>build_clarifier_system_message"]
        COACH["LLM · coach composes<br/>build_coach_system_message"]
        CRITIC["Critic verifies claims<br/>against analysis truth<br/>graphs/multi_agent.py::_critic"]
        SUP --> SPEC --> COACH --> CRITIC
        CRITIC -->|"claim unsupported"| COACH
        SPEC <--> TOOLS
    end

    subgraph MEM["8 · Memory"]
        SHORT["Short-term thread state<br/>LangGraph checkpointer"]
        LONG["Long-term profile memory<br/>LangGraph store"]
        AGENT <--> SHORT
        AGENT <--> LONG
        COACH <--> SHORT
    end

    OUT["Delivered to user"]
    PERSONA --> OUT
    STORY --> OUT
    TRAIN --> OUT
    FALLBACK --> OUT
    AGENT --> OUT
    CRITIC --> OUT
    ANALYTICS --> OUT

    classDef det fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20
    classDef llm fill:#ede7f6,stroke:#5e35b1,color:#311b92
    classDef store fill:#eceff1,stroke:#546e7a,color:#263238
    classDef out fill:#fff8e1,stroke:#f9a825,color:#f57f17

    class SRC,NORM,JOB,SF,CLS,PAT,OPEN,ANALYTICS,RRF,DENSE,SPARSE,FACTS,TRAIN_F,FALLBACK,TOOLS,CRITIC,SHORT,LONG det
    class PERSONA,STORY,TRAIN,INTENT,AGENT,SUP,SPEC,COACH,EMB llm
    class DB,CORPUS store
    class OUT out
```

## Every LLM call, and its prompt

| # | Feature | Prompt builder | Module |
|---|---------|----------------|--------|
| 1 | Persona report | `build_messages` | `domain/reports/prompts.py` |
| 2 | Full game story | `build_story_messages` | `domain/reports/story_prompts.py` |
| 3 | Training plan | `build_training_analysis_messages` | `domain/reports/training_prompts.py` |
| 4 | Chat intent classification | `build_intent_messages` | `domain/chat/prompts.py` |
| 5 | Chat coaching agent | `build_agent_system_message` | `domain/chat/prompts.py` |
| 6 | Multi-agent supervisor | `build_supervisor_messages` | `domain/chat/multi_agent_prompts.py` |
| 7 | Retriever specialist | `build_retriever_system_message` | `domain/chat/multi_agent_prompts.py` |
| 8 | Chess-analyst specialist | `build_chess_analyst_system_message` | `domain/chat/multi_agent_prompts.py` |
| 9 | Clarifier specialist | `build_clarifier_system_message` | `domain/chat/multi_agent_prompts.py` |
| 10 | Coach composer | `build_coach_system_message` | `domain/chat/multi_agent_prompts.py` |

Each of these files also defines a `BASE_SYSTEM_PROMPT` / `_*_SYSTEM_PROMPT` constant
holding the role and guardrail text the builder wraps around per-request content.

Embeddings (`text-embedding-3-small`) are the eleventh API call, made during corpus
ingestion and on every retrieval query.

## What needs no API key

Everything in green: ingestion, Stockfish analysis, move classification, motif and theme
detection, opening detection, profile analytics, RRF fusion, the agent's tool lookups,
and the critic's verification. With a blank `OPENAI_API_KEY` the app starts and every
number it shows is still real — only generated prose is unavailable, because
`build_llm_provider` returns a stand-in that fails on the first completion call rather
than at startup.

## The boundary that matters

Reports and chat never assert chess truth on their own authority:

- Report prose is built from findings already selected deterministically from the
  database (`selection.py`, `training_selection.py`).
- Chat answers are grounded in tool results, which read the same analysis tables.
- The multi-agent path adds a critic that checks claims against deterministic analysis
  before delivery, looping back to the coach when a claim is unsupported.

The `analysis` retrieval bucket is profile-scoped at the retriever interface, so a
retrieval cannot cross a profile boundary without an explicit permission grant.
