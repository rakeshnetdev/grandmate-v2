"""Object storage adapters (ADR-0015)."""

from app.core.config import StorageSettings
from app.integrations.storage.base import ObjectNotFoundError, StorageBackend, StorageError
from app.integrations.storage.local import LocalStorage


def build_storage(settings: StorageSettings) -> StorageBackend:
    """Construct the configured storage backend.

    One factory so callers depend on the Protocol rather than on a concrete class. When
    Phase 17 adds S3 or Supabase Storage, only this function and the new adapter change.
    """
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_local_path)

    # Unreachable while the setting is a Literal["local"], but an explicit failure beats
    # a silent None if that Literal is widened later.
    raise StorageError(f"Unknown storage backend: {settings.storage_backend!r}")


__all__ = [
    "LocalStorage",
    "ObjectNotFoundError",
    "StorageBackend",
    "StorageError",
    "build_storage",
]
