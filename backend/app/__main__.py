"""Server entrypoint: ``uv run python -m app``.

The uvicorn CLI knows nothing about ``app.core.config``, so invoking it directly binds
uvicorn's own default port and silently ignores ``API_HOST`` / ``API_PORT``. This module
is the bridge: it reads the typed settings and passes them to the server, keeping ``.env``
the single source of truth for the bind address as required by the configuration contract.
"""

from __future__ import annotations

import uvicorn

from app.core.config import get_settings


def main() -> None:
    """Run the API server using the configured host and port."""
    settings = get_settings()

    # Reload is a development affordance, not a separate tunable: it is derived from the
    # environment so there is no way to accidentally ship a reloading production server.
    # It also forces the import-string form below, since the reloader re-imports the app
    # in a subprocess and cannot be handed an already-constructed instance.
    reload_enabled = settings.app.app_env == "development"

    uvicorn.run(
        "app.main:app",
        host=settings.app.api_host,
        port=settings.app.api_port,
        reload=reload_enabled,
        log_config=None,  # structlog is configured in create_app; do not let uvicorn reset it.
    )


if __name__ == "__main__":
    main()
