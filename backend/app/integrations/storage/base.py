"""Object storage interface (ADR-0015).

Uploaded PGNs and generated reports go through this Protocol rather than touching a
filesystem or an SDK directly. MVP writes to local disk; Phase 17 swaps in S3, R2, or
Supabase Storage by writing one adapter, with no change to calling code.

Keys are opaque strings using ``/`` as a separator, chosen to map cleanly onto both
filesystem paths and object-store keys, e.g. ``pgn/{profile_id}/{content_hash}.pgn``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class StorageError(RuntimeError):
    """Raised when a storage operation fails."""


class ObjectNotFoundError(StorageError):
    """Raised when a key does not exist."""


@runtime_checkable
class StorageBackend(Protocol):
    """What the application may assume about object storage."""

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        """Store ``data`` under ``key``. Returns the key. Overwrites if present."""
        ...

    async def get(self, key: str) -> bytes:
        """Retrieve the object. Raises :class:`ObjectNotFoundError` if absent."""
        ...

    async def exists(self, key: str) -> bool:
        """Whether the key exists."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the object. Succeeds silently if already absent, so deletes are
        idempotent and safe to retry."""
        ...


__all__ = ["ObjectNotFoundError", "StorageBackend", "StorageError"]
