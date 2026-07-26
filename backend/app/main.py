"""FastAPI application factory.

``create_app`` builds a fully wired application. Using a factory rather than a
module-level ``app`` object means tests can construct isolated instances with different
settings, which matters as soon as Phase 2 introduces auth state.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.middleware import TRACE_HEADER, DevInsightMiddleware
from app.api.routes import build_root_router, build_v1_router
from app.core.config import Settings, get_settings
from app.core.devinsight import TraceStore
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown.

    Production startup fails fast on missing configuration rather than deferring the
    error to the first request that needs a key. Development is permissive, because
    Phase 1 has nothing that requires Supabase or an LLM.
    """
    settings: Settings = app.state.settings

    if settings.app.is_production:
        missing = settings.missing_required_for_production()
        if missing:
            # Names only. Never values.
            raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")

    logger.info(
        "application_started",
        environment=settings.app.app_env,
        version=__version__,
        engine_depth=settings.engine.engine_depth,
        llm_model=settings.llm.llm_model,
        dev_insight=settings.dev_insight_active,
    )
    yield
    logger.info("application_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Pass ``settings`` to override environment configuration."""
    settings = settings or get_settings()
    configure_logging(settings.app)

    app = FastAPI(
        title="GrandMate API",
        description="Chess analysis and coaching platform",
        version=__version__,
        lifespan=lifespan,
        # Interactive docs are a development convenience, not a production surface.
        docs_url=None if settings.app.is_production else "/docs",
        redoc_url=None,
    )
    app.state.settings = settings

    # The trace store always exists so routes and tests can reference it unconditionally;
    # it simply stays empty when tracing is off.
    app.state.trace_store = TraceStore(max_traces=settings.dev_insight.dev_insight_max_traces)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # The browser cannot read a custom response header unless it is exposed. Without
        # this the devinsight panel would never see the trace id.
        expose_headers=[TRACE_HEADER],
    )

    # Developer insight is off in production regardless of configuration: these routes
    # expose request internals and are unauthenticated until Phase 2 (ADR-0013).
    dev_insight_on = settings.dev_insight_active
    if dev_insight_on:
        app.add_middleware(
            DevInsightMiddleware,
            store=app.state.trace_store,
            max_spans=settings.dev_insight.dev_insight_max_spans_per_trace,
            capture_sensitive=settings.dev_insight_capture_sensitive,
        )

    app.include_router(build_root_router())
    app.include_router(build_v1_router(include_dev_routes=dev_insight_on))

    return app


app = create_app()

__all__ = ["app", "create_app"]
