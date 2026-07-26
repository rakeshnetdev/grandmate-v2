"""Filesystem storage backend (ADR-0015).

MVP implementation. Writes under ``STORAGE_LOCAL_PATH``, which is gitignored.

Two properties worth noting:

- **Path traversal is rejected.** Keys come from request data, so a key like
  ``../../etc/passwd`` must not escape the root. Every resolved path is checked to be
  inside the root before any I/O happens.
- **Writes are atomic.** Data is written to a temporary file and then renamed, so a
  crash mid-write cannot leave a truncated object that later reads as valid. Rename is
  atomic within a filesystem.

File I/O runs in a thread so it does not block the event loop. That matters once batch
PGN upload lands in Phase 3.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from app.integrations.storage.base import ObjectNotFoundError, StorageError


class LocalStorage:
    """Stores objects as files beneath a root directory."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        """Map a key to a path, refusing anything that escapes the root.

        Keys are attacker-influenced. ``Path.resolve()`` collapses ``..`` segments, so
        comparing the resolved path against the root catches traversal attempts before
        any file is opened.
        """
        if not key or key.startswith("/"):
            raise StorageError(f"Invalid storage key: {key!r}")

        candidate = (self._root / key).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise StorageError(f"Storage key escapes the storage root: {key!r}")
        return candidate

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        """Store bytes atomically. ``content_type`` is accepted for interface parity and
        ignored — the filesystem has nowhere to record it."""
        path = self._resolve(key)
        await asyncio.to_thread(self._write_atomic, path, data)
        return key

    @staticmethod
    def _write_atomic(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Temp file in the same directory guarantees the rename stays on one filesystem,
        # which is what makes it atomic.
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    async def get(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(f"No object stored under {key!r}") from exc

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._resolve(key).is_file)

    async def delete(self, key: str) -> None:
        """Idempotent: deleting an absent key is not an error, so retries are safe."""
        path = self._resolve(key)
        await asyncio.to_thread(path.unlink, True)


__all__ = ["LocalStorage"]
