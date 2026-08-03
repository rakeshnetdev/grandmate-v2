"""Configuration contract tests.

These enforce the owner's requirement that nothing is hardcoded and no secret leaks.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import (
    DEFAULT_DATABASE_URL,
    DatabaseSettings,
    EngineSettings,
    IdentitySettings,
    LLMSettings,
    Settings,
    get_settings,
)


def test_engine_defaults_match_the_locked_decision() -> None:
    """Baseline depth 12 with a deeper second pass, per ADR-0004 and decision D-010."""
    engine = EngineSettings()

    assert engine.engine_depth == 12
    assert engine.engine_deep_depth == 18
    assert engine.inaccuracy_cp == 50
    assert engine.mistake_cp == 100
    assert engine.blunder_cp == 300


def test_engine_threads_pinned_to_one_for_determinism() -> None:
    """Multi-threaded Stockfish is not reproducible; Phase 5 requires that it is."""
    assert EngineSettings().engine_threads == 1


def test_deep_depth_below_baseline_is_rejected() -> None:
    """A deep pass shallower than the sweep would make the tiering pointless."""
    with pytest.raises(ValidationError, match="ENGINE_DEEP_DEPTH"):
        EngineSettings(engine_depth=16, engine_deep_depth=12)


def test_llm_defaults_to_the_chosen_model() -> None:
    assert LLMSettings().llm_model == "gpt-4o-mini"


def test_secrets_are_not_exposed_in_repr() -> None:
    """SecretStr must hide values from reprs, logs, and tracebacks."""
    llm = LLMSettings(openai_api_key=SecretStr("sk-super-secret-value"))

    assert "sk-super-secret-value" not in repr(llm)
    assert "sk-super-secret-value" not in str(llm)
    assert "sk-super-secret-value" not in llm.model_dump_json()
    # Still retrievable deliberately, by the code that needs it.
    assert llm.openai_api_key.get_secret_value() == "sk-super-secret-value"


def test_llm_is_configured_reflects_key_presence() -> None:
    assert LLMSettings().is_configured is False
    assert LLMSettings(openai_api_key=SecretStr("sk-x")).is_configured is True


def test_missing_production_config_returns_names_only() -> None:
    """The production check reports variable names, never their values."""
    missing = Settings().missing_required_for_production()

    assert "DATABASE_URL" in missing
    assert "SESSION_JWT_SECRET" in missing
    assert "OPENAI_API_KEY" in missing
    assert all(name.replace("_", "").isupper() for name in missing)


class TestSessionCookiePolicy:
    """The SPA and the API are not on the same site once deployed (Vercel -> Fly), and
    `SameSite=Lax` silently breaks that: the browser accepts the cookie at login and then
    declines to send it, so `/auth/me` 401s forever with a clean 200 behind it."""

    def test_defaults_to_lax_for_a_same_site_deployment(self) -> None:
        assert IdentitySettings().session_cookie_samesite == "lax"

    def test_none_is_allowed_for_a_cross_site_deployment(self) -> None:
        assert IdentitySettings(session_cookie_samesite="none").session_cookie_samesite == "none"

    def test_an_unknown_policy_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IdentitySettings(session_cookie_samesite="sometimes")  # type: ignore[arg-type]

    def test_samesite_none_with_wildcard_cors_is_a_production_blocker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`SameSite=None` hands CSRF protection entirely to the CORS allow-list, so a
        wildcard there is no longer a lax default — it lets any origin make a credentialed
        request carrying the user's session cookie."""
        monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "none")
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

        assert "CORS_ALLOWED_ORIGINS" in Settings().missing_required_for_production()

    def test_named_origins_with_samesite_none_are_fine(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "none")
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://grandmate.vercel.app")

        assert "CORS_ALLOWED_ORIGINS" not in Settings().missing_required_for_production()


class TestDatabaseConfiguration:
    """ADR-0015: plain Postgres for MVP, Supabase deferred to Phase 17."""

    def test_defaults_to_local_postgres_on_5433(self) -> None:
        """5433, not 5432, so a developer's existing Postgres keeps the standard port."""
        assert Settings().database.url == DEFAULT_DATABASE_URL
        assert ":5433/" in Settings().database.url

    def test_blank_env_value_falls_back_to_the_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A leftover `DATABASE_URL=` must not yield an empty connection string.

        Regression: the Supabase-era .env shipped a blank DATABASE_URL, which silently
        overrode the code default and produced an empty URL that failed far from the
        cause.
        """
        monkeypatch.setenv("DATABASE_URL", "")

        assert DatabaseSettings().url == DEFAULT_DATABASE_URL

    def test_explicit_value_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db.example:5432/prod")

        assert DatabaseSettings().url == "postgresql+asyncpg://u:p@db.example:5432/prod"

    def test_sync_url_swaps_the_driver_for_alembic(self) -> None:
        """Alembic runs migrations synchronously, so asyncpg has to become psycopg."""
        settings = DatabaseSettings()

        assert "+asyncpg" in settings.url
        assert "+psycopg" in settings.sync_url
        # Everything except the driver must be identical, or the two would drift.
        assert settings.sync_url.replace("+psycopg", "+asyncpg") == settings.url

    def test_url_is_a_secret(self) -> None:
        """The URL carries credentials, so it must not appear in reprs or logs."""
        settings = DatabaseSettings(database_url=SecretStr("postgresql+asyncpg://u:hunter2@h/d"))

        assert "hunter2" not in repr(settings)
        assert "hunter2" not in settings.model_dump_json()

    def test_production_rejects_the_development_default(self) -> None:
        """The dangerous case is not "unset" — it is "never overridden".

        DATABASE_URL always resolves, so a production deploy that forgot to set it would
        start cleanly and talk to localhost:5433. That must be reported as missing.
        """
        assert "DATABASE_URL" in Settings().missing_required_for_production()

    def test_production_accepts_an_overridden_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@prod.internal:5432/grandmate")

        assert "DATABASE_URL" not in Settings().missing_required_for_production()


def test_bind_address_defaults_are_loopback_and_the_project_port() -> None:
    """Regression: `API_PORT` existed but nothing read it, so the server bound 8000.

    The entrypoint in `app/__main__.py` is what closes that gap; this asserts the values
    it reads.
    """
    app_settings = Settings().app

    assert app_settings.api_host == "127.0.0.1"
    assert app_settings.api_port == 7575


def test_bind_address_is_overridable_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Containers set API_HOST=0.0.0.0; without this the published port reaches nothing."""
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "9001")

    app_settings = Settings().app

    assert app_settings.api_host == "0.0.0.0"
    assert app_settings.api_port == 9001


def test_cors_origins_parse_from_comma_separated_string() -> None:
    settings = Settings()
    settings.app.cors_allowed_origins = "http://a.test, http://b.test ,"

    assert settings.app.cors_origins_list == ["http://a.test", "http://b.test"]


def test_blank_env_value_means_unset_for_optional_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`.env` cannot express null, so a present-but-empty key must mean "not set".

    Regression test: `LLM_DAILY_TOKEN_CEILING=` in .env.example crashed startup with an
    int-parsing error before this was handled.
    """
    monkeypatch.setenv("LLM_DAILY_TOKEN_CEILING", "")

    assert LLMSettings().llm_daily_token_ceiling is None


def test_blank_env_value_still_parses_a_real_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_DAILY_TOKEN_CEILING", "50000")

    assert LLMSettings().llm_daily_token_ceiling == 50_000


def test_settings_are_cached() -> None:
    assert get_settings() is get_settings()


def test_env_var_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Values come from the environment, which is the whole point of the module."""
    monkeypatch.setenv("ENGINE_DEPTH", "20")
    monkeypatch.setenv("ENGINE_DEEP_DEPTH", "24")

    assert EngineSettings().engine_depth == 20
