"""Platform game-source connector interface (Phase 14, D-030/D-031).

Behind one `Protocol`, not two concrete classes wired in by name — `ImportService`'s
platform-sync path depends on "something that can fetch recent PGN for a username,"
never on Lichess or Chess.com specifically. Same reasoning `integrations/llm/base.py`'s
`LLMProvider`/`EmbeddingProvider` are Protocols rather than a hardcoded provider.

Both connectors return **PGN text** (D-031), never a structured/NDJSON shape — the
entire point being that `ImportService` hands the result to the exact same
`parse_pgn_text`/`ingest` pipeline a manual paste or upload already uses, with zero new
parsing logic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class ConnectorError(RuntimeError):
    """A platform connector could not fetch what was asked of it — the account does not
    exist, the platform is unreachable, or it returned something unusable. Mirrors
    `integrations.platforms.PlatformError`'s role for the login lookup, kept as a
    separate type because a sync failure and a login failure are handled at different
    call sites with different fallbacks (job `FAILED` vs. a 4xx login response)."""


@runtime_checkable
class PlatformGameConnector(Protocol):
    """What `ImportService.ingest_into_job` may assume about a game-source connector."""

    async def fetch_recent_games_pgn(self, username: str, max_games: int) -> str:
        """PGN text covering up to `max_games` of `username`'s most recent games,
        newest-inclusive — possibly containing several games back to back, exactly as
        `parse_pgn_text` already expects from a multi-game upload. Empty string if the
        account has played no games. Raises `ConnectorError` on any failure to fetch."""
        ...


__all__ = ["ConnectorError", "PlatformGameConnector"]
