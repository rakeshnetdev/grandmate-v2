"""Shared test fixtures.

Tests run against a **hermetic** environment. Two things would otherwise leak in and make
results depend on the machine rather than the code:

1. Ambient environment variables. A developer with ``OPENAI_API_KEY`` exported would see
   different results from CI, which is exactly the class of bug this suite exists to
   catch.
2. A local ``.env`` file, once someone creates one from ``.env.example``.

The autouse fixture below removes both, so ``Settings()`` inside a test always yields
declared defaults.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic_settings import BaseSettings

from app.core.config import Settings, get_settings
from app.core.config import groups as config_groups
from app.main import create_app


def _settings_groups() -> list[type[BaseSettings]]:
    """Every settings group class, discovered rather than hand-listed.

    Hand-listing would silently miss a group added later, and the isolation would quietly
    stop covering it.
    """
    return [
        obj
        for obj in vars(config_groups).values()
        if isinstance(obj, type) and issubclass(obj, BaseSettings) and obj is not BaseSettings
    ]


@pytest.fixture(autouse=True)
def _hermetic_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate settings from the host environment and from any local .env file."""
    get_settings.cache_clear()

    for group in _settings_groups():
        # Strip any ambient value for every declared setting.
        for field_name in group.model_fields:
            monkeypatch.delenv(field_name.upper(), raising=False)
        # Ignore a local .env. monkeypatch restores the original mapping afterwards.
        monkeypatch.setitem(group.model_config, "env_file", None)  # type: ignore[typeddict-item]

    yield

    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    """Default development settings, independent of the host environment."""
    return Settings()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Test client over an app built with explicit settings."""
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


# Database fixtures live in their own module to keep this file focused; re-exported here
# so tests get them without importing from a helper path.
from tests.db_fixtures import database_url, db_engine, db_schema, db_session  # noqa: E402, F401
