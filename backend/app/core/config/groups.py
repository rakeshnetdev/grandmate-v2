"""Grouped settings models.

Each group is its own ``BaseSettings`` subclass reading the same ``.env`` file with
flat, uppercase variable names (``ENGINE_DEPTH``, ``LLM_MODEL``, ...). Grouping keeps
related configuration together without producing one oversized settings class, and it
lets a caller depend on just the slice it needs — the engine adapter takes
``EngineSettings``, not the whole world.

Secrets are typed ``SecretStr`` so they do not appear in reprs, logs, or tracebacks.
See ``final_docs/v2/configuration.md`` for the full contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BeforeValidator, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _empty_string_as_none(value: object) -> object:
    """Treat a blank .env value as "not set".

    ``.env`` files have no way to express null: a key that is present but unset reads as
    an empty string. Without this, `FOO=` on an optional int field raises a parse error
    rather than meaning "no value", which is what a reader of the file plainly intends.
    """
    if isinstance(value, str) and not value.strip():
        return None
    return value


# An optional integer that accepts a blank .env entry as "unset".
OptionalInt = Annotated[int | None, BeforeValidator(_empty_string_as_none)]

# Local development database. Port 5433 rather than 5432 so a developer's existing
# Postgres keeps the standard port (ADR-0015).
DEFAULT_DATABASE_URL = "postgresql+asyncpg://grandmate:grandmate@localhost:5433/grandmate"


def _blank_falls_back_to_default(value: object) -> object:
    """Treat a blank ``DATABASE_URL`` in ``.env`` as "not set", so the default applies.

    Without this, a leftover ``DATABASE_URL=`` line silently produces an *empty*
    connection string rather than falling back — which fails later, far from the cause,
    as an unhelpful driver error. Same reasoning as ``_empty_string_as_none``: ``.env``
    cannot express "unset" except by being blank.
    """
    if isinstance(value, str) and not value.strip():
        return DEFAULT_DATABASE_URL
    if isinstance(value, SecretStr) and not value.get_secret_value().strip():
        return DEFAULT_DATABASE_URL
    return value


# A connection URL where a blank .env entry means "use the default".
DatabaseUrl = Annotated[SecretStr, BeforeValidator(_blank_falls_back_to_default)]

# Resolve .env relative to the backend package root rather than the process working
# directory, so `uv run` from any directory picks up the same file.
BACKEND_ROOT = Path(__file__).resolve().parents[3]

_BASE_CONFIG = SettingsConfigDict(
    env_file=BACKEND_ROOT / ".env",
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
)


class AppSettings(BaseSettings):
    """Process-level application settings."""

    model_config = _BASE_CONFIG

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    # Bind address for the dev server entrypoint (`python -m app`). Loopback by default so
    # a development machine does not expose the API to its network; containers override it
    # to 0.0.0.0, which is required for published ports to reach the process.
    api_host: str = "127.0.0.1"
    api_port: int = 7575
    cors_allowed_origins: str = "http://localhost:3535"

    @property
    def cors_origins_list(self) -> list[str]:
        """Split the comma-separated origins into a list for the CORS middleware."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


class DatabaseSettings(BaseSettings):
    """Postgres connection and pool sizing (ADR-0015).

    MVP runs plain Postgres 17 with pgvector in one container. Supabase is deferred to
    Phase 17, and because Supabase *is* Postgres, adopting it later changes this URL and
    nothing else.

    The default points at port 5433, not 5432: a developer with a local Postgres already
    running should not have to stop it to work on this project.
    """

    model_config = _BASE_CONFIG

    database_url: DatabaseUrl = SecretStr(DEFAULT_DATABASE_URL)
    # Sized for a single dev machine. Revisited at Phase 17 against real concurrency.
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo_sql: bool = False

    @property
    def url(self) -> str:
        """The connection URL. Kept behind a property so the secret is read deliberately."""
        return self.database_url.get_secret_value()

    @property
    def sync_url(self) -> str:
        """Synchronous driver URL, for Alembic migrations.

        Alembic runs migrations synchronously, so the asyncpg driver in the application
        URL has to be swapped for psycopg. Deriving it here keeps one URL in ``.env``
        rather than two that could drift apart.
        """
        return self.url.replace("+asyncpg", "+psycopg")

    @property
    def psycopg_conninfo(self) -> str:
        """Plain libpq connection string — no SQLAlchemy driver prefix.

        For the one consumer that talks to psycopg directly rather than through
        SQLAlchemy: the LangGraph Postgres checkpointer (Phase 10, ADR-0005 short-term
        store), whose ``AsyncConnection.connect`` expects a bare ``postgresql://`` URL.
        Derived from ``sync_url`` for the same one-URL-in-.env reason as ``sync_url``
        itself.
        """
        return self.sync_url.replace("postgresql+psycopg://", "postgresql://")


class StorageSettings(BaseSettings):
    """Object storage for uploaded PGNs and generated reports (ADR-0015).

    MVP writes to the local filesystem behind a ``StorageBackend`` interface. Swapping to
    S3, R2, or Supabase Storage later means writing one adapter, with no change to
    calling code.
    """

    model_config = _BASE_CONFIG

    storage_backend: Literal["local"] = "local"
    storage_local_path: str = ".storage"


class IdentitySettings(BaseSettings):
    """Session token settings for MVP username-claim login (ADR-0014).

    Real Lichess OAuth2 PKCE (ADR-0007) is deferred; there is no client id, redirect URI,
    or scope list to configure until that lands, since login goes through
    ``PlatformClient`` instead of an OAuth exchange. Only the session signing secret is
    sensitive here.
    """

    model_config = _BASE_CONFIG

    session_jwt_secret: SecretStr = SecretStr("")
    session_ttl_seconds: int = 604_800


class EngineSettings(BaseSettings):
    """Stockfish and move-classification policy (ADR-0004).

    ``engine_threads`` defaults to 1 deliberately: multi-threaded Stockfish is not
    reproducible across runs because thread scheduling perturbs the search, and Phase 5
    requires identical classifications on repeated runs. Throughput comes from analysing
    several games in parallel workers, not several threads per position.

    That reproducibility guarantee is between independent, freshly-started engine
    processes — which is what every analysis job actually gets (`dispatch.py` starts one
    engine per job). It does **not** extend to re-querying the identical position twice
    on one already-warm engine: the hash table carries state between calls, and a repeat
    query can return a slightly different eval/PV as a result. Verified in
    `tests/test_engine_stockfish.py`.
    """

    model_config = _BASE_CONFIG

    stockfish_path: str = "/usr/local/bin/stockfish"
    engine_depth: int = 12
    engine_deep_depth: int = 18
    engine_threads: int = 1
    engine_hash_mb: int = 128
    engine_timeout_s: int = 30
    # How many games' analysis jobs run at once in the background. Parallelism lives here,
    # one Stockfish process per game, rather than in engine_threads — see the class
    # docstring for why.
    engine_max_concurrent_games: int = 4

    inaccuracy_cp: int = 50
    mistake_cp: int = 100
    blunder_cp: int = 300
    critical_swing_cp: int = 150

    @field_validator("engine_deep_depth")
    @classmethod
    def deep_depth_must_exceed_baseline(cls, value: int, info: ValidationInfo) -> int:
        """A deep pass shallower than the sweep would make the tiering pointless."""
        # `info.data` holds fields validated so far; engine_depth is declared first.
        baseline = info.data.get("engine_depth")
        if baseline is not None and value < baseline:
            raise ValueError(f"ENGINE_DEEP_DEPTH ({value}) must be >= ENGINE_DEPTH ({baseline})")
        return value


class LLMSettings(BaseSettings):
    """LLM provider configuration (ADR-0006).

    Temperature defaults low because this is an explanation system over facts that have
    already been computed, not a creative one.
    """

    model_config = _BASE_CONFIG

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: SecretStr = SecretStr("")
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2000
    llm_request_timeout_s: int = 60
    # None means "no ceiling configured yet" — pending owner decision (Q-4).
    llm_daily_token_ceiling: OptionalInt = None

    @property
    def is_configured(self) -> bool:
        """Whether a usable API key is present. Never logs or returns the key itself."""
        return bool(self.openai_api_key.get_secret_value())


class RetrievalSettings(BaseSettings):
    """Embedding and retrieval parameters (ADR-0008). Used from Phase 7."""

    model_config = _BASE_CONFIG

    embed_model: str = "text-embedding-3-small"
    embed_dimensions: int = 1536
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    retrieval_top_k: int = 8
    # Reciprocal rank fusion constant. Rank-based fusion avoids calibrating dense and
    # sparse scores against each other, which drifts as the corpus grows.
    retrieval_fusion_k: int = 60
    retrieval_min_score: float = 0.0
    # Resolved relative to BACKEND_ROOT by the knowledge ingestion pipeline, same
    # convention as PatternSettings.openings_data_dir.
    corpus_data_dir: str = "data/corpus"
    # BM25 (Okapi) parameters for the sparse retriever. Standard textbook defaults —
    # k1 controls term-frequency saturation, b controls length normalisation.
    retrieval_bm25_k1: float = 1.5
    retrieval_bm25_b: float = 0.75


class AgentSettings(BaseSettings):
    """Agent loop guardrails. Ceilings are hard limits, not hints."""

    model_config = _BASE_CONFIG

    agent_max_steps: int = 8
    agent_max_tool_calls: int = 12
    agent_token_budget: int = 20_000


class MultiAgentSettings(BaseSettings):
    """Multi-agent supervisor graph guardrails (Phase 13, ADR-0008 §7, D-029).

    A **separate** ceiling from `AgentSettings`, not a reuse of it. Phase 10's single
    agent loop shares one `AgentSettings` budget across its own tool-calling turn; the
    Phase 13 supervisor graph spends that same kind of budget five times over — once
    per specialist (retriever, chess analyst, coach, critic) plus the supervisor's own
    routing calls — inside one user-facing turn. Reusing `AgentSettings` unchanged would
    starve the multi-agent path before it could do enough work to fairly test Phase 13's
    exit criterion (does multi-agent beat the Phase 10 baseline); these values are sized
    with real headroom for that instead, confirmed with the owner before implementation.
    """

    model_config = _BASE_CONFIG

    # Total supervisor-routed hops across the whole turn (supervisor decision points
    # plus every specialist node visited) — roughly 2.5x AgentSettings.agent_max_steps,
    # enough for supervisor -> retriever -> chess_analyst -> coach -> critic -> coach
    # (one retry) with room to spare, not per-specialist.
    multi_agent_max_steps: int = 20
    # Total tool calls across every specialist in the turn combined (retriever and chess
    # analyst are the only tool-calling specialists) — matches AgentSettings.agent_max_tool_calls'
    # per-call generosity, scaled for two specialists instead of one.
    multi_agent_max_tool_calls: int = 20
    # Total token spend across the whole turn (supervisor + up to 4 specialists), roughly
    # 3x AgentSettings.agent_token_budget's single-agent figure.
    multi_agent_token_budget: int = 60_000


class IngestionSettings(BaseSettings):
    """Upload limits and external API rate limits.

    Rate limits are deliberately conservative — being a good API citizen costs a few
    seconds per import and avoids getting blocked.
    """

    model_config = _BASE_CONFIG

    max_pgn_upload_mb: int = 10
    max_games_per_import: int = 60
    lichess_rate_limit_rps: float = 1.0
    chesscom_rate_limit_rps: float = 1.0


class DevInsightSettings(BaseSettings):
    """Developer insight tracing (ADR-0013).

    Two separate switches, because they carry very different risk:

    - ``dev_insight_enabled`` controls recording of names, timings, counts, and token
      usage. That data is safe.
    - ``dev_insight_capture_prompts`` controls capture of prompt and retrieved-context
      *text*. That data may contain a user's game history and is off by default
      everywhere. ``Settings.dev_insight_active`` forces it off in production regardless
      of what the environment says.
    """

    model_config = _BASE_CONFIG

    dev_insight_enabled: bool = True
    dev_insight_capture_prompts: bool = False
    dev_insight_max_traces: int = 50
    dev_insight_max_spans_per_trace: int = 200


class PatternSettings(BaseSettings):
    """Opening lookup and tactical/strategic detector policy (Phase 6, D-011/D-012, ADR-0009).

    Thresholds here are the difference between "flag it" and "stay quiet" for a detector,
    which is exactly the kind of policy call rule 11 requires in configuration rather than
    as a literal buried in a detector module. Piece values (pawn/knight/bishop/rook/queen)
    are *not* here — those are standard chess facts, not a product policy, and live as a
    documented constant in ``domain/patterns``.
    """

    model_config = _BASE_CONFIG

    # Resolved relative to BACKEND_ROOT by the opening-index loader, so `uv run` from any
    # directory finds the vendored dataset the same way `.env` itself is resolved. The
    # loader reads "<dir>/all.tsv" specifically — see data/openings/PROVENANCE.md for why
    # that file, not the five per-ECO-volume ones alongside it, is the validated source.
    openings_data_dir: str = "data/openings/dist"

    # Motifs: a hanging piece or fork target below this value is real but rarely
    # coaching-worthy (a hanging pawn is common and often intentional). 300cp is a
    # minor piece — the smallest target worth flagging by default.
    motif_hanging_piece_min_value_cp: int = 300
    motif_fork_min_target_value_cp: int = 300

    # Strategic themes, each a span-of-plies judgement call rather than a single-position
    # fact, so each gets its own explicit cutoff:
    # "Past the opening" for development-lag purposes. 20 plies = 10 full moves.
    theme_opening_phase_ply_cutoff: int = 20
    # A bishop needs at least this many of its own fixed pawns on its colour to be "bad".
    theme_bad_bishop_min_fixed_pawns: int = 3
    # A passed pawn must survive this many plies to count as "created" rather than a
    # one-move blip immediately traded off.
    theme_passed_pawn_persist_plies: int = 4
    # Window for averaging mobility differential — one ply's activity swing is noise, a
    # sustained one across this many plies is a pattern.
    theme_piece_activity_window_plies: int = 10
    # Minimum sustained rank advancement differential to call it a space advantage.
    theme_space_advantage_min_rank_differential: int = 2
    # Clock remaining (ms) below which a position counts as "time trouble".
    theme_time_trouble_clock_ms_threshold: int = 30_000
    # Accuracy-percentage-point drop, time-trouble phase vs. the rest of the game, to call
    # it a "collapse" rather than ordinary variance.
    theme_time_trouble_accuracy_drop_pct: float = 20.0

    # Findings below this confidence are still computed (visible to evaluation/review) but
    # not persisted to the findings tables — a floor against flooding coaching output with
    # noise, same principle as D-013's memory-write confidence floor. 0.0 stores everything;
    # raise once real precision/recall data justifies it.
    pattern_min_confidence_to_persist: float = 0.0


class AnalyticsSettings(BaseSettings):
    """Multi-game aggregation policy (Phase 8).

    `window_sizes` and `default_window` are configuration rather than a hardcoded
    `{10, 30, 60}` set, per rule 11 — the owner's own scope note ("start with 10 games to
    decrease the complexity") is exactly the kind of product decision that belongs here,
    not buried as a literal in a route.
    """

    model_config = _BASE_CONFIG

    analytics_window_sizes: str = "10,30,60"
    analytics_default_window: int = 10

    @property
    def window_sizes_list(self) -> list[int]:
        """Parsed, ordered window sizes a caller may request."""
        return [
            int(size.strip()) for size in self.analytics_window_sizes.split(",") if size.strip()
        ]

    # Below this many analyzed games in a window, trend deltas and recurring-weakness
    # claims are computed but flagged `sufficient_sample=False` rather than asserted —
    # an accuracy "trend" from 2 games is noise, not signal.
    analytics_min_games_for_trend: int = 5

    # A motif/theme counts as a "recurring weakness" once it appears, on the player's own
    # side and at a mistake-or-worse ply, in at least this share of the window's games.
    analytics_weakness_min_occurrence_rate: float = 0.3

    # Estimated-game-duration thresholds (seconds) for bucketing a PGN TimeControl header
    # into bullet/blitz/rapid/classical — the standard "base + 40 * increment" estimate,
    # same buckets Lichess and Chess.com use, so a profile's segmentation reads familiar.
    time_control_bullet_max_s: int = 180
    time_control_blitz_max_s: int = 480
    time_control_rapid_max_s: int = 1500


class ReportSettings(BaseSettings):
    """Persona report generation policy (Phase 9, `persona-matrix.md`).

    Only the *numeric* parts of the matrix live here — how many findings a persona sees,
    and how confident a finding must be before the kid persona is shown it at all. The
    qualitative parts (whether centipawn values appear, tone, wording) are the matrix's
    own structural rules and stay in `domain/reports` code, the same split rule 11 already
    draws elsewhere (e.g. `PatternSettings`'s thresholds vs. `MotifType`'s fixed taxonomy).
    Coach has no cap — `persona-matrix.md` states it as "Unbounded" — so there is no
    setting for it; a settings field with no ceiling to express would be a magic
    non-value, not configuration.
    """

    model_config = _BASE_CONFIG

    report_self_learner_max_findings: int = 5
    report_kid_max_findings: int = 3
    # Below this confidence, a finding is not merely under-detailed for the kid persona —
    # per persona-matrix.md's safety rules, it is suppressed entirely. A young player
    # acting on a false pattern is a real harm, not a cosmetic simplification choice.
    report_kid_min_confidence_to_show: float = 0.6
    # Training plans (Phase 15, D-032): how many retrieved knowledge chunks ground one
    # weakness. Capped independently of `retrieval_top_k` — a training plan cites study
    # material for several weaknesses at once, so each one needs a small slice, not the
    # full per-query top_k.
    report_training_chunks_per_weakness: int = 2


class MemorySettings(BaseSettings):
    """Long-term memory write policy (Phase 11, ADR-0005, D-013, D-026).

    The confidence floor is the entire enforcement mechanism for ADR-0005's "only
    durable facts persist" principle — set high enough that an offhand remark doesn't
    become a permanent memory, but not so high that genuine preferences/goals never
    clear it. Silent, confidence-gated writes were confirmed with the owner (D-026)
    specifically because this floor, not a confirmation prompt, is what stands between a
    real preference and chat noise.
    """

    model_config = _BASE_CONFIG

    memory_write_confidence_floor: float = 0.7


class EvaluationSettings(BaseSettings):
    """RAGAS thresholds and the score-ledger location (see evaluation-strategy.md)."""

    model_config = _BASE_CONFIG

    ragas_faithfulness_threshold: float = 0.85
    ragas_answer_accuracy_threshold: float = 0.80
    ragas_context_precision_threshold: float = 0.75
    ragas_context_recall_threshold: float = 0.75
    eval_run_dir: str = "evals/runs"
    # Score ledger (Phase 16): a metric that drops by more than this between consecutive
    # runs of the same suite is flagged as a regression, even if its absolute value still
    # clears its own threshold — see evaluation-strategy.md's own 0.94-to-0.86 example.
    eval_regression_tolerance: float = 0.05
    # Move-classifier accuracy eval (Phase 16, D-033): ground-truth depth for the
    # independent re-analysis pass. Deliberately its own setting, not a reuse of
    # `EngineSettings.engine_deep_depth` (18, already part of production's own tiered
    # pass) — D-033's whole point is ground truth from a depth production never runs at.
    classifier_eval_ground_truth_depth: int = 24
    # How many real (position, production-classification) pairs to sample per run. Two
    # engine calls per move (before/after) at a materially deeper depth are slow; this
    # keeps a single run's wall-clock time bounded rather than scaling with corpus size.
    classifier_eval_sample_size: int = 24


__all__ = [
    "AgentSettings",
    "AnalyticsSettings",
    "AppSettings",
    "DatabaseSettings",
    "DevInsightSettings",
    "EngineSettings",
    "EvaluationSettings",
    "IdentitySettings",
    "IngestionSettings",
    "LLMSettings",
    "MemorySettings",
    "MultiAgentSettings",
    "PatternSettings",
    "ReportSettings",
    "RetrievalSettings",
    "StorageSettings",
]
