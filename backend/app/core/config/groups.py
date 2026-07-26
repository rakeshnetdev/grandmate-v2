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
    """

    model_config = _BASE_CONFIG

    stockfish_path: str = "/usr/local/bin/stockfish"
    engine_depth: int = 12
    engine_deep_depth: int = 18
    engine_threads: int = 1
    engine_hash_mb: int = 128
    engine_timeout_s: int = 30

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


class AgentSettings(BaseSettings):
    """Agent loop guardrails. Ceilings are hard limits, not hints."""

    model_config = _BASE_CONFIG

    agent_max_steps: int = 8
    agent_max_tool_calls: int = 12
    agent_token_budget: int = 20_000


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


class EvaluationSettings(BaseSettings):
    """RAGAS thresholds and the score-ledger location (see evaluation-strategy.md)."""

    model_config = _BASE_CONFIG

    ragas_faithfulness_threshold: float = 0.85
    ragas_answer_accuracy_threshold: float = 0.80
    ragas_context_precision_threshold: float = 0.75
    ragas_context_recall_threshold: float = 0.75
    eval_run_dir: str = "evals/runs"


__all__ = [
    "AgentSettings",
    "AppSettings",
    "DatabaseSettings",
    "DevInsightSettings",
    "EngineSettings",
    "EvaluationSettings",
    "IdentitySettings",
    "IngestionSettings",
    "LLMSettings",
    "RetrievalSettings",
    "StorageSettings",
]
