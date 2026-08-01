"""Observability and production tracing utilities (ADR-0017, D-033)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

import structlog
from langchain_core.tracers.context import tracing_v2_enabled
from langsmith import Client

from app.core.config import Settings
from app.core.devinsight.recorder import MAX_ATTRIBUTE_CHARS, SENSITIVE_ATTRIBUTE_HINTS

logger = structlog.get_logger(__name__)


def sanitize_data(data: Any, capture_sensitive: bool = False) -> Any:
    """Recursively redact sensitive text fields and truncate long values.

    Reuses dev-insight's constants to ensure identical data protection rules.
    """
    if isinstance(data, dict):
        clean: dict[str, Any] = {}
        for k, v in data.items():
            lowered_k = k.lower()
            is_sensitive = any(hint in lowered_k for hint in SENSITIVE_ATTRIBUTE_HINTS)
            if not capture_sensitive and is_sensitive:
                if isinstance(v, str):
                    clean[k] = f"<redacted, {len(v)} chars>"
                elif isinstance(v, list):
                    clean[k] = f"<redacted, {len(v)} items>"
                else:
                    clean[k] = "<redacted>"
            else:
                clean[k] = sanitize_data(v, capture_sensitive)
        return clean
    elif isinstance(data, list):
        return [sanitize_data(item, capture_sensitive) for item in data]
    elif isinstance(data, str):
        if len(data) > MAX_ATTRIBUTE_CHARS:
            return f"{data[:MAX_ATTRIBUTE_CHARS]}… <truncated>"
        return data
    else:
        return data


@contextmanager
def get_tracing_context(settings: Settings) -> Iterator[None]:
    """Context manager to enable LangSmith tracing for a block of code,
    attaching a customized Client that sanitizes egress payloads.
    """
    obs = settings.observability
    if not obs.langsmith_tracing:
        yield
        return

    api_key = obs.langsmith_api_key.get_secret_value()
    if not api_key:
        logger.warning("langsmith_tracing_enabled_but_key_missing")
        yield
        return

    keys = [
        "LANGCHAIN_TRACING_V2",
        "LANGCHAIN_API_KEY",
        "LANGCHAIN_PROJECT",
        "LANGCHAIN_ENDPOINT",
        "LANGSMITH_TRACING_SAMPLING_RATE",
    ]
    backup = {k: os.environ.get(k) for k in keys}

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGCHAIN_PROJECT"] = obs.langsmith_project
    os.environ["LANGCHAIN_ENDPOINT"] = obs.langsmith_endpoint
    os.environ["LANGSMITH_TRACING_SAMPLING_RATE"] = str(obs.langsmith_sample_rate)

    def sanitize(data: dict[str, Any]) -> dict[str, Any]:
        # `sanitize_data` is `Any -> Any` on purpose: it recurses over arbitrary
        # structures (dicts, lists, scalars), so it cannot name one return type. A dict
        # in always produces a dict out, so the narrowing belongs here — at the one
        # boundary where the input type is known — rather than in its signature or in a
        # set of overloads that would have to mirror every branch of the recursion.
        cleaned = sanitize_data(data, capture_sensitive=obs.langsmith_capture_prompts)
        return cast("dict[str, Any]", cleaned)

    client = Client(
        api_key=api_key,
        api_url=obs.langsmith_endpoint,
        hide_inputs=sanitize,
        hide_outputs=sanitize,
    )

    with tracing_v2_enabled(project_name=obs.langsmith_project, client=client):
        try:
            yield
        finally:
            # Restore environment variables
            for k in keys:
                val = backup[k]
                if val is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = val


__all__ = ["get_tracing_context", "sanitize_data"]
