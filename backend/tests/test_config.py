"""Configuration contract tests.

These enforce the owner's requirement that nothing is hardcoded and no secret leaks.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import EngineSettings, LLMSettings, Settings, get_settings


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

    assert "SUPABASE_URL" in missing
    assert "SESSION_JWT_SECRET" in missing
    assert "OPENAI_API_KEY" in missing
    assert all(name.isupper() for name in missing)


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


def test_lichess_scopes_parse_and_stay_minimal() -> None:
    """Minimal scopes by default. Widening them is a deliberate act, not a default."""
    scopes = Settings().identity.lichess_scopes_list

    assert scopes == ["email:read", "preference:read"]


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
