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
from app.api.middleware import (
    TRACE_HEADER,
    CorrelationMiddleware,
    DevInsightMiddleware,
    RateLimitMiddleware,
)
from app.api.routes import build_root_router, build_v1_router
from app.core.config import Settings, get_settings
from app.core.devinsight import TraceStore
from app.core.logging import configure_logging, get_logger
from app.db.session import create_engine, create_session_factory
from app.domain.patterns import load_opening_index
from app.integrations.llm import build_embedding_provider, build_llm_provider
from app.integrations.storage import build_storage

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown.

    Production startup fails fast on missing configuration rather than deferring the
    error to the first request that needs a key. Development is permissive, because
    Phase 1 has nothing that requires Supabase or an LLM.

    The database engine is built here rather than at import time so each application
    instance (one per test, plus the real process one) gets its own connection pool that
    is disposed on shutdown instead of leaking across instances.
    """
    settings: Settings = app.state.settings

    if settings.app.is_production:
        missing = settings.missing_required_for_production()
        if missing:
            # Names only. Never values.
            raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")

    engine = create_engine(settings.database)
    app.state.db_engine = engine
    app.state.db_session_factory = create_session_factory(engine)
    app.state.storage = build_storage(settings.storage)
    # Parsed once at startup, not per request — see OpeningIndexDep's docstring. A
    # missing/malformed vendored dataset fails startup loudly (OpeningDatasetError),
    # same "fail fast, not on first request" principle as the production config check
    # above, just unconditional since this data is required in every environment.
    app.state.opening_index = load_opening_index(settings.patterns)
    # `build_llm_provider` returns a stand-in when OPENAI_API_KEY is blank, so startup
    # never depends on a key existing — an unconfigured key only fails the first actual
    # completion call, not every route, matching development's permissive posture noted
    # above (see UnconfiguredLLMProvider's own docstring for why this matters).
    app.state.llm_provider = build_llm_provider(settings.llm)
    # Same reasoning, same stand-in shape, for the embedding provider Phase 10's chat
    # tools (`search_knowledge`, `search_analysis`) need on every graph invocation.
    app.state.embedding_provider = build_embedding_provider(settings.llm, settings.retrieval)

    from app.domain.analysis.dispatch import startup_analysis_sweep

    await startup_analysis_sweep(app.state.db_session_factory, settings)

    logger.info(
        "application_started",
        environment=settings.app.app_env,
        version=__version__,
        engine_depth=settings.engine.engine_depth,
        llm_model=settings.llm.llm_model,
        dev_insight=settings.dev_insight_active,
        opening_index_size=len(app.state.opening_index),
    )
    yield
    await app.state.llm_provider.aclose()
    await app.state.embedding_provider.aclose()
    await engine.dispose()
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

    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        limit_per_minute=settings.observability.rate_limit_per_minute,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # The browser cannot read a custom response header unless it is exposed. Without
        # this the devinsight panel would never see the trace id.
        expose_headers=[TRACE_HEADER, "X-Request-Id", "X-Trace-Id"],
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
