"""Storage backend tests.

Path traversal is the one that matters most: keys are derived from request data, so a
backend that lets a key escape its root is an arbitrary-file-write primitive.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import StorageSettings
from app.integrations.storage import LocalStorage, ObjectNotFoundError, StorageError, build_storage


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "objects")


async def test_put_then_get_roundtrip(storage: LocalStorage) -> None:
    await storage.put("pgn/abc/game.pgn", b"[Event 'Test']")

    assert await storage.get("pgn/abc/game.pgn") == b"[Event 'Test']"


async def test_put_returns_the_key(storage: LocalStorage) -> None:
    assert await storage.put("a/b.txt", b"x") == "a/b.txt"


async def test_put_creates_nested_directories(storage: LocalStorage, tmp_path: Path) -> None:
    await storage.put("deeply/nested/path/file.pgn", b"data")

    assert (tmp_path / "objects" / "deeply" / "nested" / "path" / "file.pgn").is_file()


async def test_put_overwrites(storage: LocalStorage) -> None:
    await storage.put("k", b"first")
    await storage.put("k", b"second")

    assert await storage.get("k") == b"second"


async def test_get_missing_raises_object_not_found(storage: LocalStorage) -> None:
    with pytest.raises(ObjectNotFoundError, match="nope"):
        await storage.get("nope")


async def test_exists(storage: LocalStorage) -> None:
    assert await storage.exists("k") is False
    await storage.put("k", b"x")
    assert await storage.exists("k") is True


async def test_delete_is_idempotent(storage: LocalStorage) -> None:
    """Deleting an absent key must not raise, so retried jobs are safe."""
    await storage.put("k", b"x")
    await storage.delete("k")
    await storage.delete("k")

    assert await storage.exists("k") is False


async def test_no_temp_files_left_behind(storage: LocalStorage, tmp_path: Path) -> None:
    """Atomic writes use a temp file; it must not survive a successful write."""
    await storage.put("k", b"x")

    assert list((tmp_path / "objects").glob("**/*.tmp")) == []


class TestPathTraversal:
    """Keys come from request data and must never escape the storage root."""

    @pytest.mark.parametrize(
        "key",
        [
            "../escape.txt",
            "../../etc/passwd",
            "pgn/../../escape.txt",
            "a/b/../../../escape.txt",
        ],
    )
    async def test_traversal_is_rejected(self, storage: LocalStorage, key: str) -> None:
        with pytest.raises(StorageError, match="escapes the storage root"):
            await storage.put(key, b"malicious")

    @pytest.mark.parametrize("key", ["", "/absolute/path"])
    async def test_empty_and_absolute_keys_are_rejected(
        self, storage: LocalStorage, key: str
    ) -> None:
        with pytest.raises(StorageError, match="Invalid storage key"):
            await storage.put(key, b"x")

    async def test_traversal_is_rejected_on_read_too(self, storage: LocalStorage) -> None:
        """Rejection must cover every operation, not only writes."""
        with pytest.raises(StorageError, match="escapes the storage root"):
            await storage.get("../../etc/passwd")

    async def test_interior_dots_are_fine(self, storage: LocalStorage) -> None:
        """Rejection must not be so broad that legitimate keys break."""
        await storage.put("pgn/game.v2.pgn", b"x")

        assert await storage.exists("pgn/game.v2.pgn") is True


def test_factory_builds_the_configured_backend(tmp_path: Path) -> None:
    settings = StorageSettings(storage_local_path=str(tmp_path / "s"))

    assert isinstance(build_storage(settings), LocalStorage)
