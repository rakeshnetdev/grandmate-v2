"""API route registration.

Routers are **built per application** rather than defined as module-level singletons.
That matters because ``create_app`` mounts the developer-insight routes conditionally: a
shared module-level router would be mutated by the first app that enabled them and would
then leak those routes into every app created afterwards, including a production one.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    analysis,
    analytics,
    auth,
    chat,
    dev,
    games,
    health,
    imports,
    memory,
    patterns,
    profiles,
    reports,
)

API_V1_PREFIX = "/api/v1"


def build_root_router() -> APIRouter:
    """Unversioned routes.

    Health probes live here deliberately: a probe should not have to track API versions,
    and an unversioned ``/health`` is the near-universal convention.
    """
    router = APIRouter()
    router.include_router(health.router)
    return router


def build_v1_router(*, include_dev_routes: bool = False) -> APIRouter:
    """Versioned API routes.

    ``include_dev_routes`` is driven by ``Settings.dev_insight_active``, which is forced
    off in production.
    """
    router = APIRouter(prefix=API_V1_PREFIX)
    router.include_router(auth.router)
    router.include_router(profiles.router)
    router.include_router(imports.router)
    router.include_router(games.router)
    router.include_router(analysis.router)
    router.include_router(patterns.router)
    router.include_router(analytics.router)
    router.include_router(reports.router)
    router.include_router(chat.router)
    router.include_router(memory.router)

    if include_dev_routes:
        router.include_router(dev.router)

    return router


__all__ = ["API_V1_PREFIX", "build_root_router", "build_v1_router"]
