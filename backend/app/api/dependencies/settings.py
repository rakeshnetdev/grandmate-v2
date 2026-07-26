"""Settings injection for routes.

Routes resolve settings from ``request.app.state``, not from the module-level
``get_settings()`` singleton. That distinction matters: ``create_app(settings)`` accepts
an explicit settings object, and if routes read the global singleton instead, that
argument would be silently ignored — the app would claim one configuration and serve
another.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings


def get_request_settings(request: Request) -> Settings:
    """Return the settings the application was constructed with."""
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_request_settings)]

__all__ = ["SettingsDep", "get_request_settings"]
