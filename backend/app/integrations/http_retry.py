"""Rate-limit-aware GET with backoff (Phase 14).

Shared by the Lichess and Chess.com game connectors, which — unlike
`integrations/platforms.py`'s single login lookup — may issue several requests in one
sync (Chess.com paginates by month) and are the first callers in this project to hit a
third-party API repeatedly enough that a transient 429/5xx is worth retrying rather than
failing the whole sync outright.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

import httpx


async def get_with_backoff(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    params: Mapping[str, int | str] | None = None,
    rate_limit_rps: float,
    max_attempts: int = 3,
) -> httpx.Response:
    """GET `url`, retrying a 429 or 5xx up to `max_attempts` times with a backoff based
    on `rate_limit_rps` (attempt N waits `N / rate_limit_rps` seconds) — a deliberately
    simple linear backoff, not exponential: these are bulk-import syncs bounded at a few
    dozen requests at most (`max_games_per_import`), not a high-volume client where
    exponential backoff's faster initial retry matters.

    Returns the last response received (even a non-2xx one) once attempts are
    exhausted, rather than raising — callers already have their own status-code
    handling (404 means "no such account", not a transient failure) and should not have
    to unwrap an exception to reach it.
    """
    response: httpx.Response | None = None
    for attempt in range(1, max_attempts + 1):
        response = await client.get(url, headers=headers, params=params)
        if response.status_code != 429 and response.status_code < 500:
            return response
        if attempt < max_attempts:
            await asyncio.sleep(attempt / rate_limit_rps)
    assert response is not None  # the loop always runs at least once
    return response


__all__ = ["get_with_backoff"]
