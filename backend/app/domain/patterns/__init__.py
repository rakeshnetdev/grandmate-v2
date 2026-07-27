"""Pattern intelligence: opening identification, tactical motifs, strategic themes
(Phase 6, D-011/D-012, ADR-0009).

See `service.py` for the orchestrating `PatternDetectionService` and
`app/db/models/patterns.py` for why opening lookup and motif/theme detection have
different trigger points.
"""

from app.domain.patterns.opening_lookup import (
    OpeningDatasetError,
    OpeningEntry,
    OpeningIndex,
    OpeningMatchResult,
    load_opening_index,
)
from app.domain.patterns.service import PatternDetectionService

__all__ = [
    "OpeningDatasetError",
    "OpeningEntry",
    "OpeningIndex",
    "OpeningMatchResult",
    "PatternDetectionService",
    "load_opening_index",
]
