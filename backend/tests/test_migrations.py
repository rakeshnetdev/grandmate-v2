"""Migration reversibility tests.

`definition-of-done.md` requires every migration to have a rollback plan. These assert
that the rollback actually works, which is a different claim from "a downgrade function
exists".

**These run against their own database.** They call `alembic downgrade base`, which drops
every table — including the ones the model tests are using. Sharing a database made the
model tests fail depending on execution order, which is exactly the kind of flake that
gets a suite ignored. A dedicated database removes the coupling rather than papering over
it with ordering markers.

Three real defects were caught here during Phase 2:

1. Alembic creates Postgres enum types implicitly inside ``create_table``, but
   ``drop_table`` does not remove them. The downgrade left six types behind and a
   subsequent upgrade failed with ``type "audit_action" already exists``.
2. SQLAlchemy persists ``Enum.name`` by default, so ``AuditAction.USER_LOGIN`` was stored
   as ``'USER_LOGIN'`` while the Python ``StrEnum`` compares equal to ``'user_login'``.
   Invisible through the ORM; immediately wrong in raw SQL.
3. ``TimestampMixin`` produced ``TIMESTAMP WITHOUT TIME ZONE`` columns while the Python
   defaults were timezone-aware, which asyncpg refuses outright.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import DatabaseSettings
from tests.db_fixtures import database_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Separate from the model-test database, because these tests destroy the schema.
MIGRATION_DB_NAME = "grandmate_migration_tests"

EXPECTED_TABLES = {
    "users",
    "user_identities",
    "profiles",
    "profile_sources",
    "profile_relationships",
    "audit_events",
    "jobs",
    "games",
}

EXPECTED_ENUMS = {
    "auth_provider",
    "profile_kind",
    "persona",
    "relationship_role",
    "game_source",
    "audit_action",
    "job_kind",
    "job_status",
    "game_color",
}


def _with_database(url: str, database: str) -> str:
    """Return ``url`` pointing at a different database on the same server."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _alembic(*args: str, url: str) -> subprocess.CompletedProcess[str]:
    """Run Alembic against an explicit database.

    ``DATABASE_URL`` is passed through the environment because ``alembic/env.py`` reads
    the URL from settings — so overriding the environment is the supported way to point
    it somewhere else, with no second configuration path to keep in sync.
    """
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DATABASE_URL": url},
    )


@pytest.fixture(scope="module")
def migration_db() -> Iterator[str]:
    """Create a dedicated database for these tests, and drop it afterwards.

    Yields the async URL; ``_alembic`` converts to the sync driver via settings.
    """
    base_url = database_url()
    admin_sync_url = DatabaseSettings(database_url=base_url).sync_url  # type: ignore[arg-type]

    admin = create_engine(admin_sync_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        admin.dispose()
        pytest.skip("Postgres not reachable — start it with `docker compose up -d postgres`")

    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{MIGRATION_DB_NAME}"'))
        connection.execute(text(f'CREATE DATABASE "{MIGRATION_DB_NAME}"'))

    yield _with_database(base_url, MIGRATION_DB_NAME)

    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{MIGRATION_DB_NAME}"'))
    admin.dispose()


@pytest.fixture
def engine(migration_db: str) -> Iterator[Engine]:
    """Synchronous engine on the migration database — Alembic runs synchronously."""
    sync_url = DatabaseSettings(database_url=migration_db).sync_url  # type: ignore[arg-type]
    sync_engine = create_engine(sync_url)
    yield sync_engine
    sync_engine.dispose()


def _tables(engine: Engine) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
        return {row[0] for row in rows}


def _enums(engine: Engine) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT typname FROM pg_type WHERE typtype='e'"))
        return {row[0] for row in rows}


class TestMigrationCycle:
    def test_upgrade_creates_every_expected_table(self, engine: Engine, migration_db: str) -> None:
        result = _alembic("upgrade", "head", url=migration_db)

        assert result.returncode == 0, result.stderr
        assert _tables(engine) >= EXPECTED_TABLES

    def test_downgrade_removes_tables_and_enum_types(
        self, engine: Engine, migration_db: str
    ) -> None:
        """The enum half is the part that was broken.

        Dropping the tables while leaving the types behind looks like a clean downgrade
        right up until the next upgrade fails.
        """
        _alembic("upgrade", "head", url=migration_db)
        result = _alembic("downgrade", "base", url=migration_db)

        assert result.returncode == 0, result.stderr
        assert _tables(engine) - {"alembic_version"} == set()
        assert _enums(engine) & EXPECTED_ENUMS == set()

    def test_migration_is_repeatable(self, engine: Engine, migration_db: str) -> None:
        """up → down → up must succeed. This is what failed before the enum drops."""
        _alembic("upgrade", "head", url=migration_db)
        _alembic("downgrade", "base", url=migration_db)
        result = _alembic("upgrade", "head", url=migration_db)

        assert result.returncode == 0, result.stderr
        assert _tables(engine) >= EXPECTED_TABLES

    def test_enum_values_are_stored_lowercase(self, engine: Engine, migration_db: str) -> None:
        """The database must hold the StrEnum *values*, not the member names.

        Otherwise `SELECT ... WHERE action = 'user_login'` silently matches nothing.
        """
        _alembic("upgrade", "head", url=migration_db)

        with engine.connect() as connection:
            labels = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT e.enumlabel FROM pg_enum e "
                        "JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = 'audit_action'"
                    )
                )
            }

        assert "user_login" in labels
        assert "USER_LOGIN" not in labels

    def test_timestamps_are_timezone_aware(self, engine: Engine, migration_db: str) -> None:
        """Naive timestamp columns break asyncpg and are wrong across time zones."""
        _alembic("upgrade", "head", url=migration_db)

        with engine.connect() as connection:
            data_type = connection.execute(
                text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name='users' AND column_name='created_at'"
                )
            ).scalar_one()

        assert data_type == "timestamp with time zone"

    def test_no_pending_model_changes(self, engine: Engine, migration_db: str) -> None:
        """The migration must fully describe the models.

        `alembic check` fails when autogenerate would produce a non-empty diff, meaning a
        model changed without a migration — the usual cause of schema drift between a
        developer's database and production.
        """
        _alembic("upgrade", "head", url=migration_db)
        result = _alembic("check", url=migration_db)

        assert result.returncode == 0, f"Models drifted from migrations:\n{result.stdout}"
