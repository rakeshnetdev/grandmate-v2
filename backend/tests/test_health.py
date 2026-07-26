"""API smoke tests for the health and readiness endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import __version__
from app.core.config import Settings
from app.main import create_app


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "grandmate-backend"
    assert body["version"] == __version__


def test_readiness_ok_in_development_without_secrets(client: TestClient) -> None:
    """Development must run without Supabase or an LLM key.

    Phase 1 has nothing that needs them, and requiring them would make local development
    impossible before Phase 2.
    """
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["environment"] == "development"
    assert body["missing_configuration"] == []


def test_readiness_reports_missing_config_in_production() -> None:
    """Production readiness names what is absent, and returns 503."""
    settings = Settings()
    settings.app.app_env = "production"

    app = create_app(settings)
    # TestClient's context manager runs lifespan, which intentionally raises in
    # production when configuration is missing. Call the route without lifespan here.
    client = TestClient(app)
    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    # DATABASE_URL appears because it still holds the development default, which in
    # production means "never overridden" rather than "set" — see ADR-0015.
    assert "DATABASE_URL" in body["missing_configuration"]
    assert "OPENAI_API_KEY" in body["missing_configuration"]


def test_readiness_never_leaks_secret_values(client: TestClient) -> None:
    """The readiness payload must contain names, never values.

    This endpoint is routinely scraped and logged by monitoring systems.
    """
    response = client.get("/ready")
    raw = response.text

    assert "SecretStr" not in raw
    for entry in response.json()["missing_configuration"]:
        # Entries are environment variable NAMES: uppercase, underscore-separated.
        assert entry.replace("_", "").isupper()


def test_openapi_docs_disabled_in_production() -> None:
    settings = Settings()
    settings.app.app_env = "production"

    app = create_app(settings)

    assert app.docs_url is None
