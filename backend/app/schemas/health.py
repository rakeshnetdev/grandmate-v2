"""Response schemas for the health and readiness endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness. Answers "is the process up", nothing more."""

    status: Literal["ok"] = "ok"
    service: str = "grandmate-backend"
    version: str


class ReadinessResponse(BaseModel):
    """Readiness. Answers "can this process actually serve traffic".

    ``missing_configuration`` lists environment variable *names* only. Values are never
    included — the readiness endpoint is frequently exposed to monitoring systems that
    log their responses.
    """

    status: Literal["ready", "not_ready"]
    environment: str
    missing_configuration: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)


__all__ = ["HealthResponse", "ReadinessResponse"]
