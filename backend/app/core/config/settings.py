"""Root settings object and its cached accessor.

This is the **only** place the application reads environment variables. Domain code takes
a settings object (or one of its groups) as an argument; it never calls ``os.environ``.
That rule exists so a value cannot end up being read in two places with two defaults —
the failure mode where the same game gets two different blunder classifications depending
on which code path ran.

See ``final_docs/v2/configuration.md``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field

from app.core.config.groups import (
    DEFAULT_DATABASE_URL,
    AgentSettings,
    AnalyticsSettings,
    AppSettings,
    DatabaseSettings,
    DevInsightSettings,
    EngineSettings,
    EvaluationSettings,
    IdentitySettings,
    IngestionSettings,
    LLMSettings,
    PatternSettings,
    ReportSettings,
    RetrievalSettings,
    StorageSettings,
)


class Settings(BaseModel):
    """Composed application settings.

    Each group instantiates itself from the environment, so constructing ``Settings()``
    loads everything. Groups are exposed as attributes rather than flattened so callers
    can depend on a narrow slice.
    """

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    engine: EngineSettings = Field(default_factory=EngineSettings)
    patterns: PatternSettings = Field(default_factory=PatternSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    agents: AgentSettings = Field(default_factory=AgentSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    analytics: AnalyticsSettings = Field(default_factory=AnalyticsSettings)
    reports: ReportSettings = Field(default_factory=ReportSettings)
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)
    dev_insight: DevInsightSettings = Field(default_factory=DevInsightSettings)

    @property
    def dev_insight_active(self) -> bool:
        """Whether trace recording runs.

        Disabled in production even if the environment enables it. The trace-reading
        routes are unauthenticated until Phase 2 adds an auth layer, and an
        unauthenticated endpoint exposing request internals has no business being
        reachable in production. Phase 17 revisits this behind proper auth.
        """
        return self.dev_insight.dev_insight_enabled and not self.app.is_production

    @property
    def dev_insight_capture_sensitive(self) -> bool:
        """Whether prompt and context *text* is captured.

        Forced off in production regardless of configuration. This data can contain a
        user's game history, so the environment is not permitted to opt into it.
        """
        return self.dev_insight.dev_insight_capture_prompts and not self.app.is_production

    def missing_required_for_production(self) -> list[str]:
        """Names of settings that must be populated before running in production.

        Returned as names only — never values. Used by the readiness endpoint and by
        startup validation so a misconfigured deployment fails loudly and early rather
        than at the first request that happens to need a key.
        """
        missing: list[str] = []
        # Not merely "is it set" — DATABASE_URL always resolves, because a blank value
        # falls back to the local development default. So the real production failure is
        # a URL that was never overridden: the process would start cleanly and quietly
        # talk to a database that does not exist, or worse, to a developer's.
        if not self.database.url or self.database.url == DEFAULT_DATABASE_URL:
            missing.append("DATABASE_URL")
        if not self.identity.session_jwt_secret.get_secret_value():
            missing.append("SESSION_JWT_SECRET")
        if not self.llm.is_configured:
            missing.append("OPENAI_API_KEY")
        return missing


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached because reading and validating the environment on every request is wasted
    work. Tests that need different values should call ``get_settings.cache_clear()``
    after patching the environment — see ``tests/conftest.py``.
    """
    return Settings()


__all__ = ["Settings", "get_settings"]
