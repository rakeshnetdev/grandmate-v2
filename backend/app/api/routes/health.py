"""Health and readiness routes.

Kept deliberately thin per the "routes delegate, they do not decide" rule. The only
logic here is assembling the readiness verdict from the settings object.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Response, status

from app import __version__
from app.api.dependencies.settings import SettingsDep
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe. Must stay dependency-free so it answers even when misconfigured."""
    return HealthResponse(version=__version__)


@router.get("/ready", response_model=ReadinessResponse)
async def ready(settings: SettingsDep, response: Response) -> ReadinessResponse:
    """Readiness probe.

    Reports which required configuration is absent and whether the Stockfish binary is
    present at the configured path. Returns 503 when not ready so orchestrators do not
    route traffic to a process that cannot serve it.

    Configuration is only *required* in production: development runs happily without
    Supabase or an LLM key, since Phase 1 has nothing that needs them.
    """
    checks = {
        "stockfish_binary": Path(settings.engine.stockfish_path).exists(),
        "llm_configured": settings.llm.is_configured,
    }

    in_production = settings.app.is_production
    missing = settings.missing_required_for_production() if in_production else []
    # Warnings do not affect the verdict. A placeholder CORS origin means the frontend
    # cannot talk to this process yet, not that the process cannot serve — and reporting
    # it as not-ready would take an otherwise healthy container out of rotation.
    warnings = settings.deployment_warnings() if in_production else []
    is_ready = not missing

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        environment=settings.app.app_env,
        missing_configuration=missing,
        warnings=warnings,
        checks=checks,
    )


__all__ = ["router"]
