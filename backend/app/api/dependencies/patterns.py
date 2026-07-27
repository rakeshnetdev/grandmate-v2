"""Opening index injection for routes.

Same rationale as `dependencies/storage.py`: the vendored dataset is parsed once in the
application lifespan (`app/main.py`) and reused for every request — re-parsing a
~3,800-row TSV per request would be wasted work for data that only changes on a manual
re-vendor (`data/openings/PROVENANCE.md`).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.domain.patterns import OpeningIndex


def get_opening_index(request: Request) -> OpeningIndex:
    index: OpeningIndex = request.app.state.opening_index
    return index


OpeningIndexDep = Annotated[OpeningIndex, Depends(get_opening_index)]

__all__ = ["OpeningIndexDep", "get_opening_index"]
