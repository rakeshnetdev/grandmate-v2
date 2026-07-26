"""Object storage injection for routes.

Same rationale as `dependencies/db.py`: resolve from `app.state`, built once in the
application lifespan, rather than reconstructing (or worse, singleton-caching at module
scope) a backend per request.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.integrations.storage import StorageBackend


def get_storage(request: Request) -> StorageBackend:
    backend: StorageBackend = request.app.state.storage
    return backend


StorageDep = Annotated[StorageBackend, Depends(get_storage)]

__all__ = ["StorageDep", "get_storage"]
