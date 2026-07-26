"""Configuration package. Import ``get_settings`` from here, not from submodules."""

from app.core.config.groups import (
    AgentSettings,
    AppSettings,
    EngineSettings,
    EvaluationSettings,
    IdentitySettings,
    IngestionSettings,
    LLMSettings,
    RetrievalSettings,
    SupabaseSettings,
)
from app.core.config.settings import Settings, get_settings

__all__ = [
    "AgentSettings",
    "AppSettings",
    "EngineSettings",
    "EvaluationSettings",
    "IdentitySettings",
    "IngestionSettings",
    "LLMSettings",
    "RetrievalSettings",
    "Settings",
    "SupabaseSettings",
    "get_settings",
]
