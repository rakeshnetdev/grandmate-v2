"""Alembic environment.

The connection URL comes from ``app.core.config``, never from ``alembic.ini``. Putting a
URL in the ini file would mean credentials in version control and a second source of
truth that could drift from ``.env`` — both of which the configuration contract forbids.

Migrations run against the *synchronous* driver (``DatabaseSettings.sync_url``). Alembic's
migration runner is synchronous while the application uses asyncpg, so the driver is
swapped in one place rather than requiring two URLs in ``.env``.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.db.models  # noqa: F401  — registers every table on Base.metadata
from alembic import context
from app.core.config import get_settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing app.db.models above is load-bearing: autogenerate compares Base.metadata
# against the database, so a model that is never imported looks like a table to drop.
target_metadata = Base.metadata

# Injected here rather than stored in alembic.ini, so the URL lives only in .env.
config.set_main_option("sqlalchemy.url", get_settings().database.sync_url)


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting.

    Useful for reviewing what a migration will do to production before running it.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Without these, autogenerate misses column type and server-default changes,
            # which is how a schema silently drifts from the models.
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
